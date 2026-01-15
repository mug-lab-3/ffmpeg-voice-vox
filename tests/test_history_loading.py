import pytest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock
from app.core.audio import AudioManager
from app.services.processor import StreamProcessor
from app.core.database import Transcription
from app.core.voicevox import VoiceVoxClient
from app.config import config


@pytest.fixture
def setup_env():
    # Setup
    test_dir = tempfile.mkdtemp()

    with (patch("app.config.config.save_config_ex"),):
        # We don't need to patch app.core.database.config or others as they don't exist.
        # Instead, we should configure the instances used in tests if possible.
        # But here we are instantiating them or using globals.

        # db_manager is a global in app.core.database.
        # We can set its config directly.
        from app.core.database import db_manager

        mock_sys_config = MagicMock()
        mock_sys_config.output_dir = test_dir

        # Save original config to restore later
        original_db_config = db_manager.config
        db_manager.set_config(mock_sys_config)

        yield test_dir

        # Teardown
        db_manager.set_config(original_db_config)

    shutil.rmtree(test_dir)


@pytest.fixture
def mock_vv_client():
    return MagicMock(spec=VoiceVoxClient)


@pytest.fixture
def audio_manager(setup_env):
    # setup_env yields test_dir, which we can use for config
    test_dir = setup_env
    mock_sys_config = MagicMock()
    mock_sys_config.output_dir = test_dir
    return AudioManager(mock_sys_config)


@patch("app.core.database.db_manager.get_recent_logs")
def test_processor_loading(mock_get_logs, setup_env, mock_vv_client, audio_manager):
    test_dir = setup_env
    # Setup DB mock return with Models
    mock_get_logs.return_value = [
        Transcription(
            id=1,
            timestamp="2026-01-12 12:00:00",
            text="Hello World",
            speaker_id=1,
            output_path="001_Hello.wav",
            audio_duration=1.5,
        )
    ]

    # Create the file on disk to satisfy physical check in _load_history
    wav_path = os.path.join(test_dir, "001_Hello.wav")
    with open(wav_path, "wb") as f:
        f.write(b"FAKE_WAV")

    mock_syn_config = MagicMock()
    processor = StreamProcessor(mock_vv_client, audio_manager, mock_syn_config)

    logs = processor.get_logs()
    assert len(logs) == 1
    assert logs[0]["text"] == "Hello World"
    assert logs[0]["id"] == 1
    assert logs[0]["filename"] == "001_Hello.wav"


@patch("app.core.database.db_manager.update_audio_info")
@patch("app.core.database.db_manager.get_recent_logs")
@patch("app.core.database.db_manager.delete_log")
def test_missing_file_only_resets_status(
    mock_delete,
    mock_get_logs,
    mock_update_audio,
    setup_env,
    mock_vv_client,
    audio_manager,
):
    # DB says file exists, but it's missing on disk
    mock_get_logs.return_value = [
        Transcription(
            id=99,
            timestamp="2026-01-12 12:00:00",
            text="Missing",
            speaker_id=1,
            output_path="missing.wav",
            audio_duration=1.5,
        )
    ]

    mock_syn_config = MagicMock()
    processor = StreamProcessor(mock_vv_client, audio_manager, mock_syn_config)

    # Should NOT have called delete_log
    mock_delete.assert_not_called()

    # Should have called update_audio_info to reset status
    mock_update_audio.assert_called_with(99, None, -1.0)

    # Should still have the log in memory, but as pending
    logs = processor.get_logs()
    assert len(logs) == 1
    assert logs[0]["id"] == 99
    assert logs[0]["is_generated"] is False
    assert logs[0]["filename"].startswith("pending_")
