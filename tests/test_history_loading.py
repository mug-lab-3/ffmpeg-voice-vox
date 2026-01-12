import pytest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from app.core.audio import AudioManager
from app.services.processor import StreamProcessor
from app.core.voicevox import VoiceVoxClient
from app.config import config


@pytest.fixture
def setup_env():
    # Setup
    test_dir = tempfile.mkdtemp()

    # Patch config.get to return test_dir for output_dir
    config_get_patcher = patch(
        "app.config.config.get",
        side_effect=lambda key, default=None: (
            test_dir if key == "system.output_dir" else config.config.get(key, default)
        ),
    )
    save_patcher = patch("app.config.config.save_config")

    mock_get = config_get_patcher.start()
    save_patcher.start()

    yield test_dir

    # Teardown
    config_get_patcher.stop()
    save_patcher.stop()
    shutil.rmtree(test_dir)


@pytest.fixture
def mock_vv_client():
    return MagicMock(spec=VoiceVoxClient)


@pytest.fixture
def audio_manager():
    return AudioManager()


@patch("app.core.database.db_manager.get_recent_logs")
def test_processor_loading(mock_get_logs, setup_env, mock_vv_client, audio_manager):
    test_dir = setup_env
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
    wav_path = os.path.join(test_dir, "001_Hello.wav")
    with open(wav_path, "wb") as f:
        f.write(b"FAKE_WAV")

    processor = StreamProcessor(mock_vv_client, audio_manager)

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

    processor = StreamProcessor(mock_vv_client, audio_manager)

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
