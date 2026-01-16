import os
import json
import pytest
from app.config import ConfigManager
from pydantic import ValidationError
from app.config.schemas import TranscriptionConfig


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


def test_beam_size_validation(clean_env):
    config_dir, config_file = clean_env
    # Try to break beam_size with a value that Pydantic 2.x won't coerce to a valid int within range
    invalid_data = {"transcription": {"beam_size": 100}}  # Range is 1-10
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(invalid_data, f)

    manager = ConfigManager("config.json", data_dir=str(config_dir))
    # Our repair logic should have reset it
    assert manager.transcription.beam_size == 5


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
    assert manager.transcription.beam_size == 5


def test_schema_relaxation(clean_env):
    config_dir, config_file = clean_env
    manager = ConfigManager("config.json", data_dir=str(config_dir))

    # 1. Test invalid value for model_size
    with pytest.raises(ValidationError):
        # Directly validating an invalid literal should raise
        TranscriptionConfig.model_validate(
            {"model_size": "base", "device": "invalid_device"}
        )

    # 2. Test None for beam_size (should fail on direct model validation)
    with pytest.raises(ValidationError):
        TranscriptionConfig.model_validate({"beam_size": None})

    # 3. Language validation
    # Valid language
    manager.transcription.language = "ja"
    assert manager.transcription.language == "ja"
    manager.transcription.language = ""
    assert manager.transcription.language == ""

    # Invalid language (Too long)
    with pytest.raises(ValidationError):
        manager.transcription.language = "japanese"


def test_robust_update(clean_env):
    config_dir, config_file = clean_env

    # Create file with one invalid field in transcription section to test repair on load
    initial_data = {
        "transcription": {"model_size": "medium", "beam_size": 999}  # Invalid (max 10)
    }
    with open(config_file, "w") as f:
        json.dump(initial_data, f)

    # Load (should repair beam_size to 5 via load_best_effort, keep model_size)
    manager = ConfigManager("config.json", data_dir=str(config_dir))
    assert manager.transcription.beam_size == 5
    assert manager.transcription.model_size == "medium"

    # Now try to update a valid field
    manager.transcription.input_device = "Microphone"
    assert manager.transcription.input_device == "Microphone"


if __name__ == "__main__":
    pytest.main([__file__])
