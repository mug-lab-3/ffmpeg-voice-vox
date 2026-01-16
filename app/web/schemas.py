from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.config.schemas import FfmpegConfig, ResolveConfig

# --- API Schemas ---


class BaseResponse(BaseModel):
    """Base scheme for all API responses."""

    status: str = "ok"
    message: Optional[str] = None


class StatusResponse(BaseModel):
    """Simple status response."""

    status: str = "ok"
    message: Optional[str] = None


class APIConfigSchema(BaseModel):
    """Flattened config structure for frontend."""

    speaker_id: int
    speed_scale: float
    pitch_scale: float
    intonation_scale: float
    volume_scale: float
    ffmpeg: FfmpegConfig
    resolve: ResolveConfig


class ConfigResponse(BaseResponse):
    config: APIConfigSchema
    outputDir: str
    resolve_available: bool
    voicevox_available: bool


class LogEntry(BaseModel):
    timestamp: str
    text: str
    duration: str
    config: dict
    filename: str


class LogsResponse(BaseResponse):
    logs: List[LogEntry]


class ControlStateResponse(BaseResponse):
    enabled: bool
    playback: Optional[dict] = None
    resolve_available: bool
    voicevox_available: bool


class PlayResponse(BaseResponse):
    duration: float
    start_time: float


class DeleteResponse(BaseResponse):
    deleted: List[str]


class BrowseResponse(BaseResponse):
    path: Optional[str] = None


class DevicesResponse(BaseResponse):
    devices: List[str]


# --- Request Schemas ---


class ConfigRequest(BaseModel):
    speaker: Optional[int] = None
    speedScale: Optional[float] = None
    pitchScale: Optional[float] = None
    intonationScale: Optional[float] = None
    volumeScale: Optional[float] = None
    audioTrackIndex: Optional[int] = None
    subtitleTrackIndex: Optional[int] = None
    templateBin: Optional[str] = None
    templateName: Optional[str] = None
    outputDir: Optional[str] = None
    ffmpeg: Optional[Dict[str, Any]] = None


class ControlStateRequest(BaseModel):
    enabled: bool


class FilenameRequest(BaseModel):
    filename: str
