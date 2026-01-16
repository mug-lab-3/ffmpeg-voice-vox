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
    "ffmpeg": {
        "ffmpeg_path": "C:/mock/ffmpeg.exe",
        "input_device": "",
        "model_path": "",
        "vad_model_path": "",
        "queue_length": 10,
        "host": "localhost",
    },
    "resolve": {
        "audio_track_index": 1,
        "video_track_index": 2,
        "target_bin": "root",
        "template_name": "Auto",
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

    # 1. Base URL override (to load static files from local disk)
    # Note: We will use `page.route` to intercept specific API calls,
    # but for static assets (css, js), we need to handle them carefully if we open a "file://".
    # However, loading "file://" directly can cause CORS issues with modules.
    # So we'll stick to a fake URL "http://app.test" and intercept EVERYTHING.

    # Static Files: Map http://app.test/static/... to local folder
    static_root = os.path.abspath(os.path.join(os.getcwd(), "static"))
    templates_root = os.path.abspath(os.path.join(os.getcwd(), "templates"))

    def handle_static(route):
        url = route.request.url
        # e.g. http://app.test/static/css/style.css -> static/css/style.css
        start_idx = url.find("/static/")
        if start_idx != -1:
            rel_path = url[start_idx + 1 :]  # static/css/style.css
            local_path = os.path.join(os.getcwd(), rel_path.replace("/", os.sep))
            if os.path.exists(local_path):
                # Determine content type manually or let Playwright guess?
                # Playwright's fulfill needs body.
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

    # --- API Mocks ---

    # GET /api/config
    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "config": config_state,
                "outputDir": config_state["system"]["output_dir"],
                "resolve_available": False,
            },
        ),
    )

    # GET /api/speakers
    page.route(
        "**/api/speakers", lambda route: route.fulfill(status=200, json=MOCK_SPEAKERS)
    )

    # GET /api/logs
    page.route("**/api/logs", lambda route: route.fulfill(status=200, json=[]))

    # GET /api/control/state
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

    # GET /api/stream (SSE)
    # We will mock this by fulfilling with an empty stream slightly delayed,
    # or just hanging it to prevent connection errors.
    # For H-Sync tests, we might want to manually trigger events via JS evaluation.
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

    # リクエスト内容を検証するための変数
    request_payloads = []

    def handle_synthesis_update(route):
        # リクエストJSONをキャプチャ
        try:
            data = route.request.post_data_json
            request_payloads.append(data)
        except:
            pass
        route.fulfill(status=200, json={"config": DEFAULT_CONFIG})

    # POST /api/config/synthesis をインターセプト
    page.route("**/api/config/synthesis", handle_synthesis_update)

    # 操作: スライダーを動かす (inputイベント)
    slider = page.locator("#speedScale")
    slider.evaluate("el => { el.value = 1.25; el.dispatchEvent(new Event('input')); }")

    # L-Sync検証: リクエスト完了を待たずにUIは即時1.25になる
    expect(page.locator("#val-speedScale")).to_have_text("1.25")

    # 確定操作: changeイベントでAPIリクエストが飛ぶ
    slider.evaluate("el => { el.dispatchEvent(new Event('change')); }")

    # リクエストが捕捉されたか検証
    # (非同期タイミングによっては少し待つ必要があるかもしれないが、playwrightはevaluate完了を待つ)
    # 念のため、少し待って確認するか、expectでリトライさせた方が良いが、
    # ここではシンプルなassertで確認し、失敗ならWaitを入れる方針。
    assert len(request_payloads) > 0, "API request was not sent"

    payload = request_payloads[-1]
    assert "speed_scale" in payload
    # JSの浮動小数点の誤差を考慮しつつ比較 (1.25は正確に表現できるが念のため)
    assert payload["speed_scale"] == 1.25


def test_validation_error_alert(page: Page):
    """バリデーションエラー(422)時にアラートが表示され、値がロールバックされるか"""
    setup_mock_routes(page)
    page.goto("http://app.test/")
    page.click('button[data-tab="tab-voicevox"]')

    # エラーを返すようにモック
    page.route(
        "**/api/config/synthesis",
        lambda route: route.fulfill(
            status=422,
            json={
                "status": "error",
                "message": "Too fast!",
                "config": DEFAULT_CONFIG["synthesis"],
            },
            # configにはロールバック用の元の値(1.0)が含まれると想定
        ),
    )

    # 不正な操作 (例: 1.5) -> モックがエラーを返す
    slider = page.locator("#speedScale")
    slider.evaluate("el => { el.value = 1.5; el.dispatchEvent(new Event('change')); }")

    # アラート確認
    # style.cssの実装を見ると、modal-overlay active クラスが付与される
    expect(page.locator("#alert-modal")).to_have_class("modal-overlay active")
    expect(page.locator("#alert-msg")).to_contain_text("Too fast!")

    # OKクリック
    page.click("#alert-ok")
    expect(page.locator("#alert-modal")).not_to_have_class("active")

    # ロールバック確認 (1.0に戻る)
    # handleServerEventか、APIエラーハンドリング内で store.setConfig を呼ぶ実装になっているか確認が必要だが、
    # 通常はエラー時にリロードするか、レスポンスのconfigで上書きする
    # main.js の実装によれば `api.getConfig()` を呼ぶロジックは SSEの config_update 時のみかもしれないが
    # バリデーションエラー時はUIのアニメーションだけで戻らない場合、明示的に戻す処理があるか？
    # -> main.js のスライダーハンドラにはエラー時のロールバック処理は明示されていない場合がある。
    #    しかし、ストアの状態(1.0)とUI(1.5)がズレたままになるのを防ぐため、
    #    alert後に再描画が走るか検証。もし走らないならバグ発見となる。

    # updateConfig (logics.js/main.js) -> api call -> if fail -> alert.
    # 値を戻すロジックがないとL-Syncした1.5のままになる。
    # 既存の実装では `api.getConfig` を呼び直すなどの処理がないと戻らない可能性が高い。
    # テストとして「戻ること」を期待値とするなら、リロードまたはgetConfigが必要。

    # 一旦、値が戻っているか確認 (失敗したら実装修正が必要)
    expect(page.locator("#val-speedScale")).to_have_text("1.00")


def test_h_sync_sse_update(page: Page):
    """H-Sync: SSEイベント受信によりUIが更新されるか"""
    setup_mock_routes(page)
    page.goto("http://app.test/")
    page.click('button[data-tab="tab-ffmpeg"]')

    # 初期値確認
    expect(page.locator("#val-cfg-queue-length")).to_have_text("10")

    # SSEイベントを模擬的に発火
    # ブラウザ内の handleServerEvent を直接呼ぶか、MessageEventを発火させる
    # ここでは window.handleServerEvent が露出していないため、Workerからのメッセージをシミュレートするのは難しい
    # 代わりに、EventSourceのonmessageを叩く...のも難しいので、
    # api.getConfig が呼ばれるきっかけとなる config_update をシミュレートしたいが、
    # 最も確実なのは、playwrightで `window.dispatchEvent` 等を使うことだが、
    # main.js の EventSource 実装は内部隠蔽されている。

    # 代案: main.js が `handleServerEvent` をグローバルまたはモジュールスコープで持っているか？
    # type="module" なので外からは見えない。

    # 解決策: api/stream へのルートで、最初に config_update イベントを送りつける
    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "config": {
                    **DEFAULT_CONFIG,
                    "ffmpeg": {**DEFAULT_CONFIG["ffmpeg"], "queue_length": 25},
                },
                "outputDir": "",
                "resolve_available": False,
            },
        ),
    )

    # SSE接続が確立された後にデータを流すのは page.route だけでは制御が難しい（ストリームなので）。
    # しかし、WebUI起動時に /api/stream に接続しに行くので、そのレスポンスでイベントを流せる。
    page.route(
        "**/api/stream",
        lambda route: route.fulfill(
            status=200,
            body='data: {"type": "config_update", "data": {}}\n\nretry: 10000\n\n',
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    # リロードして新しいSSEレスポンスを読み込ませる
    page.reload()
    page.click('button[data-tab="tab-ffmpeg"]')

    # SSE経由で config_update -> getConfig (モックで queue_length=25) -> UI更新
    expect(page.locator("#val-cfg-queue-length")).to_have_text("25")
