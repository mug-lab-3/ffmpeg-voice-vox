"""
Service Handlers for System Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications 
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""
from app.config import config
from app.api.schemas.system import DevicesResponse

ffmpeg_client = FFmpegClient()

def get_audio_devices_handler() -> DevicesResponse:
    """Lists available audio devices."""
    ffmpeg_path = config.get("ffmpeg.ffmpeg_path")
    if not ffmpeg_path:
        raise ValueError("FFmpeg path not configured on server")
        
    devices = ffmpeg_client.list_audio_devices(ffmpeg_path)
    return DevicesResponse(devices=devices)

def heartbeat_handler():
    """Simple alive check."""
    return {"status": "alive"}
