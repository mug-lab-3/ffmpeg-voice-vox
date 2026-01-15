from app.core.ffmpeg import FFmpegClient
from app.api.schemas.system import DevicesResponse

def get_audio_devices_handler(ffmpeg_client: FFmpegClient, ffmpeg_path: str) -> DevicesResponse:
    """Lists available audio devices."""
    if not ffmpeg_path:
        raise ValueError("FFmpeg path not configured on server")

    devices = ffmpeg_client.list_audio_devices(ffmpeg_path)
    return DevicesResponse(devices=devices)


def heartbeat_handler():
    """Simple alive check."""
    return {"status": "alive"}
