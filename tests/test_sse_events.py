import unittest
import json
import time
import threading
import os
from app import create_app
from app.core.events import event_manager


class TestSSEEvents(unittest.TestCase):
    def setUp(self):
        # Isolate config
        from app.config import config

        self.config = config
        self.original_config_path = config.config_path
        self.test_data_dir = os.path.join(os.getcwd(), "tests", "data_sse")
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)

        self.test_config_path = os.path.join(self.test_data_dir, "test_sse_config.json")

        # Switch to test config path by injecting data_dir
        # But wait, 'config' is a global instance. We should probably mock it or re-init it safely?
        # A safer way is to just temporarily point config.data_dir and config.config_path
        self.original_data_dir = config.data_dir
        config.data_dir = self.test_data_dir
        config.config_path = self.test_config_path

        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

        # Re-initialize with defaults in new location
        config._ensure_data_dir()
        config._config_obj = config.load_config()

        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        # Restore config
        self.config.data_dir = self.original_data_dir
        self.config.config_path = self.original_config_path
        self.config.load_config()

        # Cleanup
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

    def test_server_restart_event_broadcast(self):
        """EventManager.publish_server_restart() が正しい形式でイベントを送信するか検証"""

        # 購読開始
        q = event_manager.subscribe()

        try:
            # イベント発行
            event_manager.publish_server_restart()

            # キューから取得 (timeout付き)
            msg = q.get(timeout=2)

            # SSE形式の検証 "data: {...}\n\n"
            self.assertTrue(msg.startswith("data: "))
            self.assertTrue(msg.endswith("\n\n"))

            # 内容の解析
            payload_str = msg.replace("data: ", "").strip()
            payload = json.loads(payload_str)

            self.assertEqual(payload["type"], "server_restart")
            self.assertEqual(payload["data"], {})

        finally:
            event_manager.unsubscribe(q)

    def test_sse_endpoint_stream(self):
        """/api/stream エンドポイントがイベントをストリーム配信するか検証"""

        # 別スレッドでイベントを発行する関数
        def emit_event():
            time.sleep(0.5)
            event_manager.publish_server_restart()

        threading.Thread(target=emit_event).start()

        # ストリーム接続
        response = self.client.get("/api/stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")

        # イテレータから最初の1つ(または数個)のイベントを取得
        found = False
        start_time = time.time()
        for chunk in response.iter_encoded():
            data = chunk.decode("utf-8")
            if "server_restart" in data:
                found = True
                break
            if time.time() - start_time > 3:  # タイムアウト
                break

        self.assertTrue(found, "server_restart event not found in stream")

    def test_config_update_event_on_synthesis_change(self):
        """音声合成設定の変更時に config_update イベントが発行されるか検証"""
        q = event_manager.subscribe()
        try:
            res = self.client.post("/api/config/synthesis", json={"speed_scale": 1.1})
            self.assertEqual(res.status_code, 200)

            msg = q.get(timeout=2)
            payload = json.loads(msg.replace("data: ", "").strip())
            self.assertEqual(payload["type"], "config_update")
        finally:
            event_manager.unsubscribe(q)

    def test_config_update_event_on_ffmpeg_change(self):
        """FFmpeg設定の変更時に config_update イベントが発行されるか検証"""
        q = event_manager.subscribe()
        try:
            res = self.client.post(
                "/api/config/ffmpeg", json={"ffmpeg_path": "dummy/path"}
            )
            self.assertEqual(res.status_code, 200)

            msg = q.get(timeout=2)
            payload = json.loads(msg.replace("data: ", "").strip())
            self.assertEqual(payload["type"], "config_update")
        finally:
            event_manager.unsubscribe(q)


if __name__ == "__main__":
    unittest.main()
