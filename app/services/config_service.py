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
        **config.get("synthesis"),
        ffmpeg=config.get("ffmpeg"),
        resolve=config.get("resolve"),
    )

    return ConfigResponse(
        config=full_cfg,
        outputDir=config.get("system.output_dir"),
        resolve_available=resolve_available,
        voicevox_available=voicevox_available,
    )


def update_config_handler(new_config: dict) -> ConfigResponse:
    """Updates configuration and returns the updated state."""
    # Mapping for backward compatibility with frontend
    mapping = {
        "speaker": "synthesis.speaker_id",
        "speedScale": "synthesis.speed_scale",
        "pitchScale": "synthesis.pitch_scale",
        "intonationScale": "synthesis.intonation_scale",
        "volumeScale": "synthesis.volume_scale",
        "prePhonemeLength": "synthesis.pre_phoneme_length",
        "postPhonemeLength": "synthesis.post_phoneme_length",
        "pauseLengthScale": "synthesis.pause_length_scale",
        "audioTrackIndex": "resolve.audio_track_index",
        "videoTrackIndex": "resolve.video_track_index",
        "templateBin": "resolve.template_bin",
        "templateName": "resolve.template_name",
    }

    for client_key, config_key in mapping.items():
        if client_key in new_config:
            val = new_config[client_key]

            # Reject empty strings for critical resolve settings
            if client_key in ["templateBin", "templateName"] and not str(val).strip():
                continue

            config.update(config_key, val)

    # Handle output directory
    if "outputDir" in new_config:
        config.update("system.output_dir", new_config["outputDir"])
        # We need access to processor to reload history
        # (This will be handled in the route or via events)

    # Handle FFmpeg config
    if "ffmpeg" in new_config:
        for k, v in new_config["ffmpeg"].items():
            config.update(f"ffmpeg.{k}", v)

    from app.core.events import event_manager

    event_manager.publish("config_update", {})

    return get_config_handler()
