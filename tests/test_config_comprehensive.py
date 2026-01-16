import os
import json
import pytest
import shutil
from app.config.manager import ConfigManager
from app.config.schemas import ConfigSchema


class TestConfigComprehensive:
    @pytest.fixture(autouse=True)
    def setup_isolated_env(self, tmp_path):
        """Prepare an isolated data directory for each test."""
        self.test_dir = tmp_path / "data"
        self.test_dir.mkdir()
        self.config_file = self.test_dir / "config.json"

        # Create a fresh ConfigManager for each test pointed at tmp_path
        self.manager = ConfigManager(
            config_filename="config.json", data_dir=str(self.test_dir)
        )

    def write_config_raw(self, data: dict):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read_config_raw(self) -> dict:
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_normal_loading(self):
        """Test that a valid config is loaded correctly."""
        valid_data = {
            "synthesis": {"speed_scale": 1.2, "speaker_id": 3},
            "transcription": {"beam_size": 7},
            "resolve": {"enabled": True},
        }
        self.write_config_raw(valid_data)

        config = self.manager.load_config_ex()
        assert config.synthesis.speed_scale == 1.2
        assert config.synthesis.speaker_id == 3
        assert config.transcription.beam_size == 7
        assert config.resolve.enabled is True

    def test_boundary_values(self):
        """Test boundary values for all constrained parameters."""
        cases = [
            # synthesis
            ("synthesis", "speed_scale", 0.5, True),
            ("synthesis", "speed_scale", 1.5, True),
            ("synthesis", "speed_scale", 0.4, False),
            ("synthesis", "speed_scale", 1.6, False),
            # transcription
            ("transcription", "beam_size", 1, True),
            ("transcription", "beam_size", 10, True),
            ("transcription", "beam_size", 0, False),
            ("transcription", "beam_size", 11, False),
            # resolve
            ("resolve", "audio_track_index", 1, True),
            ("resolve", "audio_track_index", 50, True),
            ("resolve", "audio_track_index", 0, False),
            ("resolve", "audio_track_index", 51, False),
        ]

        for section, key, value, should_be_valid in cases:
            test_data = {section: {key: value}}
            self.write_config_raw(test_data)

            config = self.manager.load_config_ex()
            actual_val = getattr(getattr(config, section), key)

            if should_be_valid:
                assert (
                    actual_val == value
                ), f"Boundary value {value} for {section}.{key} should be valid"
            else:
                default_val = getattr(getattr(ConfigSchema(), section), key)
                assert (
                    actual_val == default_val
                ), f"Abnormal value {value} for {section}.{key} should be reset to {default_val}"

    def test_type_mismatch(self):
        """Test that incorrect types are reset to defaults."""
        bad_data = {
            "synthesis": {
                "speed_scale": "very fast",
                "speaker_id": [1, 2],
            },
            "transcription": {"beam_size": "too large"},
            "resolve": {"enabled": "yes"},
        }

        self.write_config_raw(bad_data)
        config = self.manager.load_config_ex()

        defaults = ConfigSchema()
        assert config.synthesis.speed_scale == defaults.synthesis.speed_scale
        assert config.synthesis.speaker_id == defaults.synthesis.speaker_id
        assert config.transcription.beam_size == defaults.transcription.beam_size

    def test_missing_and_extra_keys(self):
        """Test that missing keys are filled and extra keys are ignored."""
        partial_data = {
            "synthesis": {"speed_scale": 1.2},
            "unknown_section": {"foo": "bar"},
            "transcription": {"beam_size": 7, "extra_key": 999},
        }
        self.write_config_raw(partial_data)

        config = self.manager.load_config_ex()

        assert config.synthesis.speed_scale == 1.2
        assert config.synthesis.speaker_id == ConfigSchema().synthesis.speaker_id

        dump = config.model_dump()
        assert "unknown_section" not in dump

        assert not hasattr(config.transcription, "extra_key")
        assert "extra_key" not in dump["transcription"]

    def test_sync_to_file(self):
        """Test that repairs are written back to the file."""
        invalid_data = {
            "synthesis": {"speed_scale": 9.9}
        }  # way out of range [0.5, 1.5]
        self.write_config_raw(invalid_data)

        # Load (triggers repair and sync)
        self.manager.load_config_ex()

        # Check file content
        file_data = self.read_config_raw()
        assert (
            file_data["synthesis"]["speed_scale"]
            == ConfigSchema().synthesis.speed_scale
        )

    def test_corrupt_json(self):
        """Test that corrupt JSON is backed up and a fresh one is created."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("THIS IS NOT JSON { { {")

        config = self.manager.load_config_ex()

        # Verify fresh config returned
        assert config.synthesis.speed_scale == ConfigSchema().synthesis.speed_scale

        # Verify backup exists
        backups = [f for f in os.listdir(self.test_dir) if "config.json.corrupt" in f]
        assert len(backups) > 0

        # Verify new config.json is valid
        assert os.path.exists(self.config_file)
        file_data = self.read_config_raw()
        assert "synthesis" in file_data

    def test_partial_repair_precision(self):
        """Test that only invalid fields are reset, while valid fields in the same or other sections are preserved."""
        # Mix of valid and invalid:
        # 1. synthesis: speed_scale is normal, but speaker_id is invalid.
        # 2. transcription: completely invalid (not a dict)
        # 3. server: completely normal
        mixed_data = {
            "synthesis": {
                "speed_scale": 1.2,  # VALID
                "speaker_id": -5,  # INVALID (ge=0)
            },
            "transcription": "I AM A STRING",  # INVALID (should be dict)
            "server": {"host": "192.168.1.100"},  # VALID
        }
        self.write_config_raw(mixed_data)

        config = self.manager.load_config_ex()

        # 1. Synthesis: Check precision
        # speed_scale should be PRESERVED (1.2)
        assert config.synthesis.speed_scale == 1.2
        # speaker_id should be RESET to default (1)
        assert config.synthesis.speaker_id == ConfigSchema().synthesis.speaker_id

        # 2. Transcription: Should be completely reset because the input wasn't even a dict
        assert config.transcription.beam_size == ConfigSchema().transcription.beam_size

        # 3. Server: Should be PRESERVED
        assert config.server.host == "192.168.1.100"
