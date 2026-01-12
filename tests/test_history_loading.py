import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from app.core.audio import AudioManager
from app.services.processor import StreamProcessor
from app.core.voicevox import VoiceVoxClient
from app.core.database import db_manager


class TestHistoryLoading(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Use patch to dynamically return test_dir for output_dir
        # This is safer than config.update as it resets after the with/patch block
        from app.config import config

        self.config_patcher = patch(
            "app.config.config.get",
            side_effect=lambda key, default=None: (
                self.test_dir
                if key == "system.output_dir"
                else config.config.get(key, default)
            ),
        )
        self.config_patcher.start()

        # Also patch save_config just in case
        self.save_patcher = patch("app.config.config.save_config")
        self.save_patcher.start()

        self.audio_manager = AudioManager()
        self.mock_vv = MagicMock(spec=VoiceVoxClient)

    def tearDown(self):
        self.config_patcher.stop()
        self.save_patcher.stop()
        shutil.rmtree(self.test_dir)

    @patch("app.core.database.db_manager.get_recent_logs")
    def test_processor_loading(self, mock_get_logs):
        # Setup DB mock return
        mock_get_logs.return_value = [
            {
                "id": 1,
                "timestamp": "2026-01-12 12:00:00",
                "text": "Hello World",
                "speaker_id": 1,
                "speed_scale": 1.0,
                "pitch_scale": 0.0,
                "intonation_scale": 1.0,
                "volume_scale": 1.0,
                "pre_phoneme_length": 0.1,
                "post_phoneme_length": 0.1,
                "output_path": "001_Hello.wav",
                "audio_duration": 1.5,
            }
        ]

        # Create the file on disk to satisfy physical check in _load_history
        wav_path = os.path.join(self.test_dir, "001_Hello.wav")
        with open(wav_path, "wb") as f:
            f.write(b"FAKE_WAV")

        processor = StreamProcessor(self.mock_vv, self.audio_manager)

        logs = processor.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["text"], "Hello World")
        self.assertEqual(logs[0]["id"], 1)
        self.assertEqual(logs[0]["filename"], "001_Hello.wav")

    @patch("app.core.database.db_manager.get_recent_logs")
    @patch("app.core.database.db_manager.delete_log")
    def test_missing_file_cleanup(self, mock_delete, mock_get_logs):
        # DB says file exists, but it's missing on disk
        mock_get_logs.return_value = [
            {
                "id": 99,
                "timestamp": "2026-01-12 12:00:00",
                "text": "Missing",
                "speaker_id": 1,
                "speed_scale": 1.0,
                "pitch_scale": 0.0,
                "intonation_scale": 1.0,
                "volume_scale": 1.0,
                "pre_phoneme_length": 0.1,
                "post_phoneme_length": 0.1,
                "output_path": "missing.wav",
                "audio_duration": 1.5,
            }
        ]

        processor = StreamProcessor(self.mock_vv, self.audio_manager)

        # Should have called delete_log for ID 99
        mock_delete.assert_called_with(99)
        self.assertEqual(len(processor.get_logs()), 0)


if __name__ == "__main__":
    unittest.main()
