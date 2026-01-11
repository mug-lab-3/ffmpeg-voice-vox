import os
import json
import pytest
from app.config import ConfigManager
from pydantic import ValidationError


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

    manager = ConfigManager("config.json")
    manager.data_dir = str(config_dir)
    manager.config_path = str(config_file)

    # Load should succeed with defaults despite corruption
    manager._config_obj = manager.load_config()

    # Verify backup created
    backups = list(config_dir.glob("config.json.corrupt.*"))
    assert len(backups) == 1

    # Verify defaults loaded
    assert manager.config["ffmpeg"]["host"] == "127.0.0.1"


def test_schema_relaxation(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json")
    manager.data_dir = str(config_dir)
    manager.config_path = str(config_file)
    manager._config_obj = manager.load_config()  # Create defaults

    # 1. Test None for model_path (should fail now as backend is strict)
    # WebUI sanitizes this, so backend should reject strict None
    success = manager.update("ffmpeg.model_path", None)
    assert success is False

    # 2. Test None for queue_length (should fail now)
    success = manager.update("ffmpeg.queue_length", None)
    assert success is False


def test_host_validation(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json")
    manager.data_dir = str(config_dir)
    manager.config_path = str(config_file)
    manager._config_obj = manager.load_config()

    # 1. Valid Host
    assert manager.update("ffmpeg.host", "192.168.1.1") is True
    assert manager.update("ffmpeg.host", "localhost") is True
    assert manager.update("ffmpeg.host", "my-server.local") is True

    # 2. Invalid Host (Empty string -> should fail now based on my implementation choice?
    # Wait, in schemas.py I put raise ValueError("Host cannot be empty").
    # So update should return False.
    assert manager.update("ffmpeg.host", "") is False

    # 3. Invalid Host (Bad chars)
    assert manager.update("ffmpeg.host", "http://bad-url") is False


def test_robust_update(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json")
    manager.data_dir = str(config_dir)
    manager.config_path = str(config_file)

    # Create file with one invalid field in ffmpeg section
    initial_data = {
        "ffmpeg": {"ffmpeg_path": "valid/path", "queue_length": 999}  # Invalid (max 30)
    }
    with open(config_file, "w") as f:
        json.dump(initial_data, f)

    # Load (should fallback queue_length to 10, keep ffmpeg_path)
    manager._config_obj = manager.load_config()
    assert manager.config["ffmpeg"]["queue_length"] == 10
    assert manager.config["ffmpeg"]["ffmpeg_path"] == "valid/path"

    # Now try to update a valid field while checks pass
    success = manager.update("ffmpeg.input_device", "Microphone")
    assert success is True
    assert manager.config["ffmpeg"]["input_device"] == "Microphone"


if __name__ == "__main__":
    pytest.main([__file__])
