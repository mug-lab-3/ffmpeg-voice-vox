"""
API Schemas for Config Domain.

IMPORTANT:
The definitions in this file must strictly follow the specifications
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.api.schemas.base import BaseResponse
from app.schemas import FfmpegConfig, ResolveConfig


class SynthesisUpdate(BaseModel):
    speaker_id: Optional[int] = None
    speed_scale: Optional[float] = Field(None, ge=0.5, le=1.5)
    pitch_scale: Optional[float] = Field(None, ge=-0.15, le=0.15)
    intonation_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    volume_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    timing: Optional[str] = None


class ResolveUpdate(BaseModel):
    enabled: Optional[bool] = None
    audio_track_index: Optional[int] = Field(None, ge=1, le=50)
    video_track_index: Optional[int] = Field(None, ge=1, le=50)
    target_bin: Optional[str] = None
    template_name: Optional[str] = None


class SystemUpdate(BaseModel):
    output_dir: Optional[str] = None


class FfmpegUpdate(BaseModel):
    ffmpeg_path: Optional[str] = None
    input_device: Optional[str] = None
    model_path: Optional[str] = None
    vad_model_path: Optional[str] = None
    host: Optional[str] = None
    queue_length: Optional[int] = Field(None, ge=1, le=30)


class APIConfigSchema(BaseModel):
    """Flattened config structure for frontend."""

    speaker_id: int
    speed_scale: float
    pitch_scale: float
    intonation_scale: float
    volume_scale: float
    timing: str
    ffmpeg: FfmpegConfig
    resolve: ResolveConfig


class ConfigResponse(BaseResponse):
    config: APIConfigSchema
    outputDir: str
    resolve_available: bool
    voicevox_available: bool
