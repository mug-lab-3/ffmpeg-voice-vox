import unittest
import json
from server import app, received_logs

class TestWebUILogs(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Clear logs
        received_logs.clear()

    def test_get_logs_empty(self):
        response = self.app.get('/api/logs')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data, [])

        received_logs.append({
            "timestamp": "12:00:00",
            "text": "test_log_struct",
            "duration": "100.0s",
            "config": {"speaker": 1},
            "filename": "test.wav"
        })

        response = self.app.get('/api/logs')
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['text'], "test_log_struct")
        self.assertIn('config', data[0])
        self.assertEqual(data[0]['filename'], "test.wav")

if __name__ == '__main__':
    unittest.main()
