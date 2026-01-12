import unittest
import json
import os
import shutil
from app import create_app
from app.config import config
from app.web.routes import processor


class TestWebUILogs(unittest.TestCase):
    def setUp(self):
        # Isolate config
        self.test_data_dir = os.path.join(os.getcwd(), "tests", "data_logs")
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)

        self.test_config_path = os.path.join(
            self.test_data_dir, "test_logs_config.json"
        )

        self.original_data_dir = config.data_dir
        self.original_config_path = config.config_path

        config.data_dir = self.test_data_dir
        config.config_path = self.test_config_path

        config._ensure_data_dir()
        config._config_obj = config.load_config()

        self.flask_app = create_app()
        self.client = self.flask_app.test_client()
        self.flask_app.testing = True
        # Clear logs via processor
        processor.received_logs = []

    def tearDown(self):
        # Restore config
        config.data_dir = self.original_data_dir
        config.config_path = self.original_config_path
        config.load_config()

        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_get_logs_empty(self):
        response = self.client.get("/api/logs")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data, [])

        processor.received_logs.append(
            {
                "id": 1,
                "timestamp": "2026-01-12T12:00:00Z",
                "text": "test_log_struct",
                "duration": "100.00s",
                "config": {"speaker_id": 1},
                "filename": "test.wav",
            }
        )

        response = self.client.get("/api/logs")
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["text"], "test_log_struct")
        self.assertIn("config", data[0])
        self.assertEqual(data[0]["filename"], "test.wav")


if __name__ == "__main__":
    unittest.main()
