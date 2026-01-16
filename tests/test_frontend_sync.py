import pytest
import os
import json
from playwright.sync_api import Page, expect

# --- Mock Data ---
DEFAULT_CONFIG = {
    "synthesis": {
        "speed_scale": 1.0,
        "pitch_scale": 0.0,
        "intonation_scale": 1.0,
        "volume_scale": 1.0,
        "pre_phoneme_length": 0.1,
        "post_phoneme_length": 0.1,
        "pause_length_scale": 1.0,
        "timing": "immediate",
    },
    "transcription": {
        "model_size": "base",
        "device": "cpu",
        "compute_type": "int8",
        "input_device": "",
        "model_path": "",
        "beam_size": 5,
        "language": "ja",
    },
    "resolve": {
        "audio_track_index": 1,
        "video_track_index": 2,
        "target_bin": "root",
        "template_name": "Auto",
        "enabled": True,
    },
    "system": {"output_dir": "C:/mock/output"},
}

MOCK_SPEAKERS = [
    {
        "name": "SpeakerA",
        "styles": [{"name": "Normal", "id": 0}, {"name": "Joy", "id": 1}],
    },
    {"name": "SpeakerB", "styles": [{"name": "Normal", "id": 2}]},
]


# --- Helper ---
def setup_mock_routes(page: Page, config_state=None):
    if config_state is None:
        config_state = DEFAULT_CONFIG.copy()

    # Static Files Mocking
    static_root = os.path.abspath(os.path.join(os.getcwd(), "static"))
    templates_root = os.path.abspath(os.path.join(os.getcwd(), "templates"))

    def handle_static(route):
        url = route.request.url
        start_idx = url.find("/static/")
        if start_idx != -1:
            rel_path = url[start_idx + 1 :]
            local_path = os.path.join(os.getcwd(), rel_path.replace("/", os.sep))
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    content = f.read()
                ct = (
                    "application/javascript"
                    if local_path.endswith(".js")
                    else ("text/css" if local_path.endswith(".css") else "text/plain")
                )
                route.fulfill(status=200, body=content, headers={"Content-Type": ct})
                return
        route.continue_()

    page.route("**/static/**", handle_static)

    # Main Page
    def handle_index(route):
        index_path = os.path.join(templates_root, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        route.fulfill(status=200, body=html, headers={"Content-Type": "text/html"})

    page.route("http://app.test/", handle_index)

    # API Mocks
    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "config": config_state,
                "outputDir": config_state["system"]["output_dir"],
                "resolve_available": False,
                "voicevox_available": True,
            },
        ),
    )

    page.route(
        "**/api/speakers", lambda route: route.fulfill(status=200, json=MOCK_SPEAKERS)
    )

    page.route("**/api/logs", lambda route: route.fulfill(status=200, json=[]))

    page.route(
        "**/api/control/state",
        lambda route: route.fulfill(
            status=200,
            json={
                "enabled": True,
                "playback": False,
                "resolve_available": False,
                "voicevox_available": True,
            },
        ),
    )

    page.route(
        "**/api/stream",
        lambda route: route.fulfill(
            status=200,
            body="retry: 10000\n\n",
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    return config_state


@pytest.fixture
def mock_page(page: Page):
    setup_mock_routes(page)
    page.goto("http://app.test/")
    return page


def test_l_sync_slider_ui(page: Page):
    """L-Sync: スライダー操作時に即座に数値表示が更新され、正しいAPIリクエストが飛ぶか"""
    setup_mock_routes(page)
    page.goto("http://app.test/")
    page.click('button[data-tab="tab-voicevox"]')

    request_payloads = []

    def handle_synthesis_update(route):
        try:
            data = route.request.post_data_json
            request_payloads.append(data)
        except:
            pass
        route.fulfill(status=200, json={"config": DEFAULT_CONFIG})

    page.route("**/api/config/synthesis", handle_synthesis_update)

    slider = page.locator("#speedScale")
    slider.evaluate("el => { el.value = 1.25; el.dispatchEvent(new Event('input')); }")

    expect(page.locator("#val-speedScale")).to_have_text("1.25")

    slider.evaluate("el => { el.dispatchEvent(new Event('change')); }")

    assert len(request_payloads) > 0, "API request was not sent"
    payload = request_payloads[-1]
    assert payload["speed_scale"] == 1.25


def test_validation_error_alert(page: Page):
    """バリデーションエラー(422)時にアラートが表示され、値がロールバックされるか"""
    setup_mock_routes(page)
    page.goto("http://app.test/")
    page.click('button[data-tab="tab-voicevox"]')

    page.route(
        "**/api/config/synthesis",
        lambda route: route.fulfill(
            status=422,
            json={
                "status": "error",
                "message": "Too fast!",
                # Rollback value
                "speed_scale": 1.0,
            },
        ),
    )

    slider = page.locator("#speedScale")
    slider.evaluate("el => { el.value = 1.5; el.dispatchEvent(new Event('change')); }")

    expect(page.locator("#alert-modal")).to_have_class("modal-overlay active")
    expect(page.locator("#alert-msg")).to_contain_text("Too fast!")

    page.click("#alert-ok")
    expect(page.locator("#alert-modal")).not_to_have_class("active")

    # ロールバックの確認 (1.00に戻る)
    expect(page.locator("#val-speedScale")).to_have_text("1.00")


def test_h_sync_sse_update(page: Page):
    """H-Sync: SSEイベント受信によりUIが更新されるか"""
    setup_mock_routes(page)
    page.goto("http://app.test/")
    page.click('button[data-tab="tab-transcription"]')

    # 初期値確認 (デフォルトは 5)
    expect(page.locator("#val-cfg-beam-size")).to_have_text("5")

    # 2回目以降の getConfig で新しい値を返すようにモックを更新
    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "config": {
                    **DEFAULT_CONFIG,
                    "transcription": {
                        **DEFAULT_CONFIG["transcription"],
                        "beam_size": 8,
                    },
                },
                "outputDir": "C:/mock/output",
                "resolve_available": False,
                "voicevox_available": True,
            },
        ),
    )

    # SSEイベントを模擬的に発火させるために、 reload() で接続を再確立させ、
    # そのレスポンスに config_update を含める
    page.route(
        "**/api/stream",
        lambda route: route.fulfill(
            status=200,
            body='data: {"type": "config_update", "data": {}}\n\nretry: 10000\n\n',
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    page.reload()
    page.click('button[data-tab="tab-transcription"]')

    # UI更新の検証 (beam_size=8)
    expect(page.locator("#val-cfg-beam-size")).to_have_text("8")


if __name__ == "__main__":
    pytest.main([__file__])
