import pytest
import json
import os
import shutil
from app import create_app
from app.config import config
from app.core.events import event_manager


@pytest.fixture(scope="module")
def app():
    """テスト用Flaskアプリの初期化"""
    app = create_app()
    app.testing = True
    return app


@pytest.fixture(scope="module")
def client(app):
    """テスト用HTTPクライアント"""
    return app.test_client()


@pytest.fixture(scope="module", autouse=True)
def isolate_config():
    """
    config.json の隔離とバックアップ/復元を行うFixture。
    テスト開始時にディレクトリを切り替え、終了時に削除して元に戻す。
    """
    import time
    import gc

    # 隔離用ディレクトリの設定
    test_data_dir = os.path.join(os.getcwd(), "tests", "data_integration_pytest")
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir, ignore_errors=True)
    os.makedirs(test_data_dir, exist_ok=True)

    # 元の状態を保持
    original_data_dir = config.data_dir
    original_config_path = config.config_path

    # configオブジェクトの設定をテスト用に上書き
    config.data_dir = test_data_dir
    config.config_path = os.path.join(test_data_dir, "config.json")

    # テスト用初期設定の作成
    config._ensure_data_dir()
    config._config_obj = config.load_config()
    config.save_config_ex()

    yield  # テストの実行

    # 元の状態に復元
    config.data_dir = original_data_dir
    config.config_path = original_config_path
    config.load_config()

    # リソースの明示的な解放
    gc.collect()
    time.sleep(0.2)  # Windowsのファイルロック解除を待つ

    # テスト用ディレクトリの削除(エラーを無視)
    if os.path.exists(test_data_dir):
        try:
            shutil.rmtree(test_data_dir)
        except (PermissionError, OSError):
            # Windowsでファイルがロックされている場合、再試行
            time.sleep(1.0)
            try:
                shutil.rmtree(test_data_dir)
            except Exception:
                # それでも失敗する場合は静かに無視
                # (テスト自体は成功しており、次回実行時に削除される)
                pass


@pytest.fixture
def event_queue():
    """SSEイベント購読用のキュー"""
    q = event_manager.subscribe()
    yield q
    event_manager.unsubscribe(q)


def test_synthesis_config_update_flow(client, event_queue):
    """音声合成設定の更新(API) -> ファイル保存 -> SSE通知の一連の流れを検証"""
    new_speed = 1.45
    payload = {"speed_scale": new_speed}

    # 1. API Request
    response = client.post("/api/config/synthesis", json=payload)
    assert response.status_code == 200

    # 2. Verify persistence in file
    with open(config.config_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        assert saved_data.get("synthesis", {}).get("speed_scale") == new_speed

    # 3. Verify SSE Event
    try:
        msg = event_queue.get(timeout=2)
        event = json.loads(msg.replace("data: ", "").strip())
        assert event["type"] == "config_update"
    except Exception as e:
        pytest.fail(f"SSE event 'config_update' was not received: {e}")


def test_system_config_output_dir_flow(client, event_queue):
    """出力ディレクトリの更新(API) -> ファイル保存 -> SSE通知の流れを検証"""
    # ダミーパスの作成
    new_output_dir = os.path.abspath(
        os.path.join(config.data_dir, "pytest_dummy_output")
    )
    if not os.path.exists(new_output_dir):
        os.makedirs(new_output_dir)

    payload = {"output_dir": new_output_dir}

    # 1. API Request
    response = client.post("/api/config/system", json=payload)
    assert response.status_code == 200

    # 2. Verify persistence in file
    with open(config.config_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        # Check against normalized path if necessary, but string match should work for simple cases
        assert saved_data.get("system", {}).get("output_dir") == new_output_dir

    # 3. Verify SSE Event
    try:
        msg = event_queue.get(timeout=2)
        event = json.loads(msg.replace("data: ", "").strip())
        assert event["type"] == "config_update"
        assert event["data"].get("outputDir") == new_output_dir
    except Exception as e:
        pytest.fail(f"SSE event 'config_update' for system was not received: {e}")


def test_transcription_config_update_flow(client, event_queue):
    """Transcription設定の更新フローを検証"""
    new_size = "medium"
    payload = {"model_size": new_size}

    # 1. API Request
    response = client.post("/api/config/transcription", json=payload)
    assert response.status_code == 200

    # 2. Verify persistence
    with open(config.config_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        assert saved_data.get("transcription", {}).get("model_size") == new_size

    # 3. Verify SSE
    try:
        msg = event_queue.get(timeout=2)
        event = json.loads(msg.replace("data: ", "").strip())
        assert event["type"] == "config_update"
    except Exception as e:
        pytest.fail(
            f"SSE event 'config_update' for transcription was not received: {e}"
        )


def test_resolve_config_update_flow(client, event_queue):
    """Resolve設定の更新フローを検証"""
    payload = {
        "audio_track_index": 5,
        "video_track_index": 3,
        "target_bin": "Test Bin",
        "template_name": "Test Template",
    }

    # 1. API Request
    response = client.post("/api/config/resolve", json=payload)
    assert response.status_code == 200

    # 2. Verify persistence
    with open(config.config_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        res_cfg = saved_data.get("resolve", {})
        assert res_cfg.get("audio_track_index") == 5
        assert res_cfg.get("video_track_index") == 3
        assert res_cfg.get("target_bin") == "Test Bin"
        assert res_cfg.get("template_name") == "Test Template"

    # 3. Verify SSE
    try:
        msg = event_queue.get(timeout=2)
        event = json.loads(msg.replace("data: ", "").strip())
        assert event["type"] == "config_update"
    except Exception as e:
        pytest.fail(f"SSE event 'config_update' for resolve was not received: {e}")
