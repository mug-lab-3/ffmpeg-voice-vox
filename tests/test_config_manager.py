import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from app.config import ConfigManager
from app.schemas import ConfigSchema


class TestConfigManager:
    @pytest.fixture
    def test_config_file(self):
        filename = "test_config_pytest.json"
        data_dir = os.path.join(os.getcwd(), "data")
        path = os.path.join(data_dir, filename)

        # Cleanup before
        if os.path.exists(path):
            os.remove(path)

        yield filename

        # Cleanup after
        if os.path.exists(path):
            os.remove(path)

    def test_missing_config_file_creates_defaults(self, test_config_file):
        """Test behavior when config file is missing (Clean install scenario)."""
        # Ensure file doesn't exist
        assert not os.path.exists(os.path.join(os.getcwd(), "data", test_config_file))

        cm = ConfigManager(test_config_file)

        # Check standard defaults
        assert cm.config["server"]["host"] == "127.0.0.1"
        assert cm.config["system"]["output_dir"] == ""
        assert cm.config["voicevox"]["port"] == 50021

        # Verify file was created in the correct location
        assert os.path.exists(cm.config_path)

        # Check parent directory exists
        assert os.path.exists(cm.data_dir)

    def test_update_persistence(self, test_config_file):
        """Test that updates are saved and reloaded."""
        cm = ConfigManager(test_config_file)
        new_path = "C:\\TestPath"

        # Update
        success = cm.update("system.output_dir", new_path)
        assert success is True
        assert cm.config["system"]["output_dir"] == new_path

        # Reload new instance
        cm2 = ConfigManager(test_config_file)
        assert cm2.config["system"]["output_dir"] == new_path

    def test_load_corrupted_json(self, test_config_file):
        """Test recovery from corrupted JSON."""
        cm = ConfigManager(test_config_file)
        path = cm.config_path

        # Write only a valid JSON part but effectively corrupted structure (empty)
        # Or invalid types to trigger Pydantic validation error
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"synthesis": {"speed_scale": "invalid_string"}}, f)

        # Should load with defaults for affected section
        cm2 = ConfigManager(test_config_file)
        assert cm2.config["synthesis"]["speed_scale"] == 1.0  # Default

    @patch("app.config.os.fsync")
    def test_save_calls_fsync(self, mock_fsync, test_config_file):
        """Test that save_config calls fsync."""
        cm = ConfigManager(test_config_file)

        # Trigger save
        cm.update("server.host", "127.0.0.2")

        # Check if fsync was called
        # fsync is called with a file descriptor (int)
        assert mock_fsync.called
        # Verify it was called with an integer
        args, _ = mock_fsync.call_args
        assert isinstance(args[0], int)

    def test_update_validation_failure(self, test_config_file):
        """Test validation failure on update."""
        cm = ConfigManager(test_config_file)
        original_speed = cm.config["synthesis"]["speed_scale"]

        # Try invalid value (max is 1.5)
        success = cm.update("synthesis.speed_scale", 5.0)
        assert success is False
        assert cm.config["synthesis"]["speed_scale"] == original_speed

    def test_nested_update(self, test_config_file):
        """Test updating nested dictionary fields."""
        cm = ConfigManager(test_config_file)
        cm.update("voicevox.port", 55555)

        cm2 = ConfigManager(test_config_file)
        assert cm2.config["voicevox"]["port"] == 55555
