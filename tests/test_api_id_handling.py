import pytest
import json
import os
import shutil
from app import create_app
from app.config import config


@pytest.fixture
def client():
    import time
    import gc

    # Isolate config
    test_data_dir = os.path.join(os.getcwd(), "tests", "data_api")
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir, ignore_errors=True)
    os.makedirs(test_data_dir, exist_ok=True)

    test_config_path = os.path.join(test_data_dir, "test_api_config.json")

    # Save original paths
    original_data_dir = config.data_dir
    original_config_path = config.config_path

    # Switch to test paths
    config.data_dir = test_data_dir
    config.config_path = test_config_path

    # Initialize default config in test dir
    config._ensure_data_dir()
    config._config_obj = config.load_config()

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    # Restore original config
    config.data_dir = original_data_dir
    config.config_path = original_config_path
    config.load_config()

    # リソースの明示的な解放
    gc.collect()
    time.sleep(0.2)  # Windowsのファイルロック解除を待つ

    # Cleanup with retry logic
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


def test_play_non_existent_id(client):
    """存在しないIDに対して再生リクエストを送った場合、エラーが返ることを確認"""
    response = client.post(
        "/api/control/play",
        data=json.dumps({"id": 999999}),
        content_type="application/json",
    )
    # control_service.py で ValueError を投げ、routes.py で 500 になる
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert "Record not found" in data["message"]


def test_delete_non_existent_id(client):
    """存在しないIDに対して削除リクエストを送った場合、エラーにならず空リストが返る"""
    response = client.post(
        "/api/control/delete",
        data=json.dumps({"id": 999999}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["deleted"] == []


def test_update_text_non_existent_id(client):
    """存在しないIDに対してテキスト更新リクエストを送った場合、400が返ることを確認"""
    response = client.post(
        "/api/control/update_text",
        data=json.dumps({"id": 999999, "text": "new text"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_resolve_insert_not_connected(client, monkeypatch):
    """DaVinci Resolveが接続されていない状態でResolve挿入リクエストを送った場合、503が返ることを確認"""

    # Resolveクライアントのモック化(未接続状態)
    class MockResolveClient:
        def is_available(self):
            return False  # 未接続とシミュレート

    # get_resolve_clientをモック化
    from app.api.routes import control

    monkeypatch.setattr(control, "get_resolve_client", lambda: MockResolveClient())

    response = client.post(
        "/api/control/resolve_insert",
        data=json.dumps({"id": 1}),
        content_type="application/json",
    )
    assert response.status_code == 503
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert "not connected" in data["message"].lower()


def test_resolve_insert_non_existent_id(client, monkeypatch):
    """存在しないIDに対してResolve挿入リクエストを送った場合、500エラーが返ることを確認

    Resolveクライアントをモック化して接続状態をシミュレートし、
    その後の存在しないIDのエラーを検証する。
    """

    # Resolveクライアントのモック化
    class MockResolveClient:
        def is_available(self):
            return True  # 接続成功とシミュレート

    # get_resolve_clientをモック化
    from app.api.routes import control

    monkeypatch.setattr(control, "get_resolve_client", lambda: MockResolveClient())

    response = client.post(
        "/api/control/resolve_insert",
        data=json.dumps({"id": 999999}),
        content_type="application/json",
    )
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert "Record not found" in data["message"]
