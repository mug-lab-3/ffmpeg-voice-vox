import unittest
import json
from app import create_app
from app.web.routes import processor


class TestWebUILogs(unittest.TestCase):
    def setUp(self):
        self.flask_app = create_app()
        self.client = self.flask_app.test_client()
        self.flask_app.testing = True
        # Clear logs via processor
        processor.received_logs = []

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
