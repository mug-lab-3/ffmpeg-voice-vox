import pytest
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock, PropertyMock
from app.core.database import DatabaseManager
from app.services.processor import StreamProcessor
from app.core.audio import AudioManager
from app.core.voicevox import VoiceVoxClient
from app.config import config


class TestNegativeDuration:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        with (
            patch("app.core.database.config") as mock_db_config,
            patch("app.core.audio.config") as mock_audio_config,
            patch("app.config.config.save_config_ex"),
        ):
            mock_db_config.system.output_dir = self.test_dir
            mock_audio_config.system.output_dir = self.test_dir
            self.db_manager = DatabaseManager()
            self.audio_manager = AudioManager()
            self.mock_vv = MagicMock(spec=VoiceVoxClient)

            yield

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_duration_is_negative_one(self):
        # Test that adding a new transcription sets duration to -1.0
        db_id = self.db_manager.add_transcription("test text", 1, {})
        transcription = self.db_manager.get_transcription(db_id)
        assert transcription.audio_duration == -1.0

    def test_update_text_resets_duration_to_negative_one(self):
        # First add with explicit duration
        db_id = self.db_manager.add_transcription(
            "test text", 1, {}, audio_duration=5.0
        )
        t1 = self.db_manager.get_transcription(db_id)
        assert t1.audio_duration == 5.0

        # Update text
        self.db_manager.update_transcription_text(db_id, "updated text")

        # Check duration is now -1.0
        t2 = self.db_manager.get_transcription(db_id)
        assert t2.audio_duration == -1.0

    def test_processor_cache_update(self):
        # Create a processor and mock its internal state to test log update
        processor = StreamProcessor(self.mock_vv, self.audio_manager)

        # Inject a fake log entry
        fake_log = {"id": 99, "text": "Old", "duration": "5.00s", "filename": "old.wav"}
        processor.received_logs = [fake_log]

        # Mock DB update since we test that separately
        with (
            patch(
                "app.services.processor.db_manager.update_transcription_text"
            ) as mock_db_update,
            patch("app.core.events.event_manager.publish") as mock_publish,
        ):

            processor.update_log_text(99, "New")

            # Check cache update
            assert processor.received_logs[0]["text"] == "New"
            assert processor.received_logs[0]["duration"] == "-1.00s"
            assert processor.received_logs[0]["filename"] == "pending_99.wav"
            assert processor.received_logs[0]["is_generated"] is False
