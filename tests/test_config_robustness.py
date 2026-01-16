import os
import json
import pytest
from app.config import ConfigManager
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def protect_config():
    """本番のconfig.jsonがテストで書き換えられないように保護する"""
    from unittest.mock import patch

    # ConfigManagerのsave_config_exをパッチして、テスト中の書き込みを阻止する
    with patch("app.config.ConfigManager.save_config_ex"):
        yield


@pytest.fixture
def clean_env(tmp_path):
    config_dir = tmp_path / "data"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    return config_dir, config_file


def test_fresh_start_and_corruption(clean_env):
    config_dir, config_file = clean_env

    # 1. Test Corrupt File Handling
    with open(config_file, "w") as f:
        f.write("{ invalid json,, }")

    manager = ConfigManager("config.json", data_dir=str(config_dir))

    # Load should succeed with defaults despite corruption
    manager._config_obj = manager.load_config_ex()

    # Verify backup created
    backups = list(config_dir.glob("config.json.corrupt.*"))
    assert len(backups) == 1

    # Verify defaults loaded
    assert manager.ffmpeg.host == "127.0.0.1"


def test_schema_relaxation(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json", data_dir=str(config_dir))

    # 1. Test None for model_path (should fail as backend is strict)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        manager.ffmpeg.model_path = None

    # 2. Test None for queue_length (should fail)
    with pytest.raises(ValidationError):
        manager.ffmpeg.queue_length = None


def test_host_validation(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json", data_dir=str(config_dir))

    # 1. Valid Host
    manager.ffmpeg.host = "192.168.1.1"
    assert manager.ffmpeg.host == "192.168.1.1"
    manager.ffmpeg.host = "localhost"
    assert manager.ffmpeg.host == "localhost"
    manager.ffmpeg.host = "my-server.local"
    assert manager.ffmpeg.host == "my-server.local"

    # 2. Invalid Host (Empty string -> should fail based on schema)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        manager.ffmpeg.host = ""

    # 3. Invalid Host (Bad chars)
    with pytest.raises(ValidationError):
        manager.ffmpeg.host = "http://bad-url"


def test_robust_update(clean_env):
    config_dir, config_file = clean_env

    # Create file with one invalid field in ffmpeg section to test repair on load
    initial_data = {
        "ffmpeg": {"ffmpeg_path": "valid/path", "queue_length": 999}  # Invalid (max 30)
    }
    with open(config_file, "w") as f:
        json.dump(initial_data, f)

    # Load (should repair queue_length to 10 via load_best_effort, keep ffmpeg_path)
    manager = ConfigManager("config.json", data_dir=str(config_dir))
    assert manager.ffmpeg.queue_length == 10
    assert manager.ffmpeg.ffmpeg_path == "valid/path"

    # Now try to update a valid field
    manager.ffmpeg.input_device = "Microphone"
    assert manager.ffmpeg.input_device == "Microphone"


if __name__ == "__main__":
    pytest.main([__file__])
