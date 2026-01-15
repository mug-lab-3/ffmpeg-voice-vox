"""
Service Handlers for Config Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from app.config import config
from app.api.schemas.config import ConfigResponse, APIConfigSchema
from app.core.voicevox import VoiceVoxClient
from app.core.resolve import ResolveClient

vv_client = VoiceVoxClient()
_resolve_client = None


def get_resolve_client():
    global _resolve_client
    if _resolve_client is None:
        _resolve_client = ResolveClient()
    return _resolve_client


def get_config_handler() -> ConfigResponse:
    """Gets the current configuration in the format expected by the frontend."""
    resolve_available = get_resolve_client().is_available()
    voicevox_available = vv_client.is_available()

    full_cfg = APIConfigSchema(
        **config.synthesis.model_dump(),
        ffmpeg=config.ffmpeg.model_dump(),
        resolve=config.resolve.model_dump(),
    )

    return ConfigResponse(
        config=full_cfg,
        outputDir=config.system.output_dir,
        resolve_available=resolve_available,
        voicevox_available=voicevox_available,
    )


def update_config_handler(new_config: dict) -> ConfigResponse:
    """Updates configuration and returns the updated state."""
    # Synthesis updates
    synthesis_fields = {
        "speaker": "speaker_id",
        "speedScale": "speed_scale",
        "pitchScale": "pitch_scale",
        "intonationScale": "intonation_scale",
        "volumeScale": "volume_scale",
        "prePhonemeLength": "pre_phoneme_length",
        "postPhonemeLength": "post_phoneme_length",
        "pauseLengthScale": "pause_length_scale",
    }
    for client_key, schema_key in synthesis_fields.items():
        if client_key in new_config:
            setattr(config.synthesis, schema_key, new_config[client_key])

    # Resolve updates
    resolve_fields = {
        "audioTrackIndex": "audio_track_index",
        "videoTrackIndex": "video_track_index",
        "templateBin": "target_bin",  # Note: frontend templateBin -> schema target_bin
        "templateName": "template_name",
    }
    for client_key, schema_key in resolve_fields.items():
        if client_key in new_config:
            val = new_config[client_key]
            if isinstance(val, str) and not val.strip():
                continue
            setattr(config.resolve, schema_key, val)

    # Handle output directory
    if "outputDir" in new_config:
        config.system.output_dir = new_config["outputDir"]

    # Handle FFmpeg config
    if "ffmpeg" in new_config:
        for k, v in new_config["ffmpeg"].items():
            if hasattr(config.ffmpeg, k):
                setattr(config.ffmpeg, k, v)

    config.save_config_ex()

    from app.core.events import event_manager

    event_manager.publish("config_update", {})

    return get_config_handler()

    from app.core.events import event_manager

    event_manager.publish("config_update", {})

    return get_config_handler()
