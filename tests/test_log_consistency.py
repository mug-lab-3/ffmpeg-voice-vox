import unittest
from unittest.mock import MagicMock
from app.services.processor import StreamProcessor
from app.config import config


class TestLogConsistency(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.config_patcher = patch("app.config.config.save_config_ex")
        self.config_patcher.start()

        self.vv_client = MagicMock()
        self.audio_manager = MagicMock()
        # Mock scan_output_dir to return empty list
        self.audio_manager.scan_output_dir.return_value = []
        self.processor = StreamProcessor(self.vv_client, self.audio_manager)
        # Clear logs to ensure test starts with 0 logs despite existing DB entries
        self.processor.received_logs = []

    def tearDown(self):
        self.config_patcher.stop()

    def test_log_config_is_copy(self):
        # 1. Set initial speaker
        config.synthesis.speaker_id = 1

        # 2. Add a log entry
        from app.core.database import Transcription
        t1 = Transcription(
            id=1,
            text="Hello",
            audio_duration=1.0,
            output_path="hello.wav",
            speaker_id=1,
        )
        self.processor._add_log_from_db(t1)

        # 3. Verify first log has speaker 1
        logs = self.processor.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["config"]["speaker_id"], 1)

        # 4. Change speaker in global config
        config.synthesis.speaker_id = 2

        # 5. Verify first log STILL has speaker 1 (not changed to 2)
        self.assertEqual(
            logs[0]["config"]["speaker_id"],
            1,
            "Log entry should not change when global config changes",
        )

        # 6. Add another log entry
        t2 = Transcription(
            id=2,
            text="World",
            audio_duration=1.0,
            output_path="world.wav",
            speaker_id=2,
        )
        self.processor._add_log_from_db(t2)

        # 7. Verify second log has speaker 2
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1]["config"]["speaker_id"], 2)
        self.assertEqual(logs[0]["config"]["speaker_id"], 1)


if __name__ == "__main__":
    unittest.main()
