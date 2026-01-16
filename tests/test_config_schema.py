import pytest
from pydantic import ValidationError
from app.config.schemas import (
    ConfigSchema,
    ServerConfig,
    VoiceVoxConfig,
    SynthesisConfig,
    SystemConfig,
    FfmpegConfig,
    ResolveConfig,
)
from unittest.mock import patch


class TestConfigSchema:
    def test_default_values(self):
        """Test default values for all configuration sections."""
        config = ConfigSchema()

        # Server
        assert config.server.host == "127.0.0.1"

        # VoiceVox
        assert config.voicevox.host == "127.0.0.1"
        assert config.voicevox.port == 50021

        # Synthesis
        assert config.synthesis.speaker_id == 1
        assert config.synthesis.speed_scale == 1.0
        assert config.synthesis.pitch_scale == 0.0
        assert config.synthesis.intonation_scale == 1.0
        assert config.synthesis.volume_scale == 1.0
        assert config.synthesis.timing == "on_demand"

        # System
        assert config.system.output_dir == ""

        # Ffmpeg
        assert config.ffmpeg.ffmpeg_path == ""
        assert config.ffmpeg.input_device == ""
        assert config.ffmpeg.model_path == ""
        assert config.ffmpeg.vad_model_path == ""
        assert config.ffmpeg.host == "127.0.0.1"
        assert config.ffmpeg.queue_length == 10

        # Resolve
        assert config.resolve.enabled is False
        assert config.resolve.audio_track_index == 1
        assert config.resolve.video_track_index == 2
        assert config.resolve.target_bin == "VoiceVox Captions"
        assert config.resolve.template_name == "Auto"

    # --- Synthesis Validation ---
    @pytest.mark.parametrize("speaker_id", [-1, -5])
    def test_synthesis_speaker_invalid(self, speaker_id):
        with pytest.raises(ValidationError):
            SynthesisConfig(speaker_id=speaker_id)

    @pytest.mark.parametrize("speed", [0.4, 1.6])
    def test_synthesis_speed_invalid(self, speed):
        with pytest.raises(ValidationError):
            SynthesisConfig(speed_scale=speed)

    @pytest.mark.parametrize("pitch", [-0.2, 0.2])
    def test_synthesis_pitch_invalid(self, pitch):
        with pytest.raises(ValidationError):
            SynthesisConfig(pitch_scale=pitch)

    @pytest.mark.parametrize("val", [-0.1, 2.1])
    def test_synthesis_volume_invalid(self, val):
        with pytest.raises(ValidationError):
            SynthesisConfig(volume_scale=val)

    @pytest.mark.parametrize("val", [-0.1, 2.1])
    def test_synthesis_intonation_invalid(self, val):
        with pytest.raises(ValidationError):
            SynthesisConfig(intonation_scale=val)

    # --- Ffmpeg Validation ---
    @pytest.mark.parametrize("queue_len", [0, 31])
    def test_ffmpeg_queue_invalid(self, queue_len):
        with pytest.raises(ValidationError):
            FfmpegConfig(queue_length=queue_len)

    def test_ffmpeg_path_warning(self, capsys):
        """Test that non-existent ffmpeg path triggers a warning print but passes validation."""
        # capsys fixture captures stdout/stderr
        path = "non_existent_ffmpeg.exe"
        config = FfmpegConfig(ffmpeg_path=path)

        assert config.ffmpeg_path == path

        captured = capsys.readouterr()
        assert f"[Config] Warning: ffmpeg_path does not exist: {path}" in captured.out

    # --- System Validation ---
    def test_output_dir_warning(self, capsys):
        """Test that non-existent output_dir triggers a warning print but passes validation."""
        path = "non_existent_dir"
        config = SystemConfig(output_dir=path)

        assert config.output_dir == path

        captured = capsys.readouterr()
        assert f"[Config] Warning: output_dir does not exist: {path}" in captured.out

    # --- Resolve Validation ---
    @pytest.mark.parametrize("track", [0, 51])
    def test_resolve_track_invalid(self, track):
        with pytest.raises(ValidationError):
            ResolveConfig(audio_track_index=track)

        with pytest.raises(ValidationError):
            ResolveConfig(audio_track_index=track)
        with pytest.raises(ValidationError):
            ResolveConfig(video_track_index=track)

    def test_resolve_track_valid(self):
        """Test boundary values for resolve tracks."""
        # 1 and 50 are valid
        c1 = ResolveConfig(audio_track_index=1, video_track_index=50)
        assert c1.audio_track_index == 1
        assert c1.video_track_index == 50

    def test_extra_fields_ignored(self):
        """Test that unknown fields are ignored (extra='ignore')."""
        data = {
            "server": {"host": "1.2.3.4", "unknown_field": "value"},
            "unknown_section": {"foo": "bar"},
        }
        config = ConfigSchema(**data)
        assert config.server.host == "1.2.3.4"
        # Accessing unknown field would be an AttributeError, so we check they are not in model_dump
        dump = config.model_dump()
        assert "unknown_section" not in dump
        assert "unknown_field" not in dump["server"]
