import pytest
import json
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_play_non_existent_id(client):
    """存在しないIDに対して再生リクエストを送った場合、エラーが返ることを確認"""
    response = client.post("/api/control/play", 
                           data=json.dumps({"id": 999999}),
                           content_type='application/json')
    # control_service.py で ValueError を投げ、routes.py で 500 になる
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert "Record not found" in data["message"]

def test_delete_non_existent_id(client):
    """存在しないIDに対して削除リクエストを送った場合、エラーにならず空リストが返る"""
    response = client.post("/api/control/delete", 
                           data=json.dumps({"id": 999999}),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["deleted"] == []

def test_update_text_non_existent_id(client):
    """存在しないIDに対してテキスト更新リクエストを送った場合、現状の実装では200が返る"""
    response = client.post("/api/control/update_text", 
                           data=json.dumps({"id": 999999, "text": "new text"}),
                           content_type='application/json')
    assert response.status_code == 200

def test_resolve_insert_non_existent_id(client):
    """存在しないIDに対してResolve挿入リクエストを送った場合、エラーが返ることを確認"""
    response = client.post("/api/control/resolve_insert", 
                           data=json.dumps({"id": 999999}),
                           content_type='application/json')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["status"] == "error"
