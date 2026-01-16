"""
API Schemas for Config Domain.

IMPORTANT:
The definitions in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.api.schemas.base import BaseResponse
from app.config.schemas import TranscriptionConfig, ResolveConfig


class SynthesisUpdate(BaseModel):
    speaker_id: Optional[int] = None
    speed_scale: Optional[float] = Field(None, ge=0.5, le=1.5)
    pitch_scale: Optional[float] = Field(None, ge=-0.15, le=0.15)
    intonation_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    volume_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    pre_phoneme_length: Optional[float] = Field(None, ge=0.0, le=1.5)
    post_phoneme_length: Optional[float] = Field(None, ge=0.0, le=1.5)
    pause_length_scale: Optional[float] = Field(None, ge=0.0, le=2.0)
    timing: Optional[str] = None


class ResolveUpdate(BaseModel):
    enabled: Optional[bool] = None
    audio_track_index: Optional[int] = Field(None, ge=1, le=50)
    video_track_index: Optional[int] = Field(None, ge=1, le=50)
    target_bin: Optional[str] = None
    template_name: Optional[str] = None


class SystemUpdate(BaseModel):
    output_dir: Optional[str] = None


class TranscriptionUpdate(BaseModel):
    model_size: Optional[str] = None
    device: Optional[Literal["cpu", "cuda", "auto"]] = None
    compute_type: Optional[str] = None
    input_device: Optional[str] = None
    sample_rate: Optional[int] = None
    beam_size: Optional[int] = None
    language: Optional[str] = None


class APIConfigSchema(BaseModel):
    """Flattened config structure for frontend."""

    speaker_id: int
    speed_scale: float
    pitch_scale: float
    intonation_scale: float
    volume_scale: float
    pre_phoneme_length: float
    post_phoneme_length: float
    pause_length_scale: float
    timing: str
    transcription: TranscriptionConfig
    resolve: ResolveConfig


class ConfigResponse(BaseResponse):
    config: APIConfigSchema
    outputDir: str
    resolve_available: bool
    voicevox_available: bool
