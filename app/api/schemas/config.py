from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.api.schemas.base import BaseResponse
from app.schemas import FfmpegConfig, ResolveConfig

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
