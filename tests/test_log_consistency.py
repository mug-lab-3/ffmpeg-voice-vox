import unittest
from unittest.mock import MagicMock
from app.core.processor import StreamProcessor
from app.config import config


class TestLogConsistency(unittest.TestCase):
    def setUp(self):
        self.vv_client = MagicMock()
        self.audio_manager = MagicMock()
        # Mock scan_output_dir to return empty list
        self.audio_manager.scan_output_dir.return_value = []
        self.processor = StreamProcessor(self.vv_client, self.audio_manager)

    def test_log_config_is_copy(self):
        # 1. Set initial speaker
        config.update("synthesis.speaker_id", 1)

        # 2. Add a log entry
        self.processor._add_log("Hello", 1.0, "hello.wav", speaker_id=1)

        # 3. Verify first log has speaker 1
        logs = self.processor.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["config"]["speaker_id"], 1)

        # 4. Change speaker in global config
        config.update("synthesis.speaker_id", 2)

        # 5. Verify first log STILL has speaker 1 (not changed to 2)
        self.assertEqual(
            logs[0]["config"]["speaker_id"],
            1,
            "Log entry should not change when global config changes",
        )

        # 6. Add another log entry
        self.processor._add_log("World", 1.0, "world.wav", speaker_id=2)

        # 7. Verify second log has speaker 2
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1]["config"]["speaker_id"], 2)
        self.assertEqual(logs[0]["config"]["speaker_id"], 1)


if __name__ == "__main__":
    unittest.main()
