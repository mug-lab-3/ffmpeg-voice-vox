"""
Configuration Schemas and Validation.

IMPORTANT:
The definitions in this file (schemas.py) are strictly based on the specifications
documented in `doc/specification/user-config.md`.
If you need to change setting items, types, default values, or validation ranges,
please update the specification document (user-config.md) FIRST, then modify
this file to ensure they are perfectly synchronized.
"""

import os
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Annotated

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"

class VoiceVoxConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 50021

class SynthesisConfig(BaseModel):
    speaker_id: Annotated[int, Field(ge=0)] = 1
    speed_scale: Annotated[float, Field(ge=0.5, le=1.5)] = 1.0
    pitch_scale: Annotated[float, Field(ge=-0.15, le=0.15)] = 0.0
    intonation_scale: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    volume_scale: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    timing: str = "immediate"  # immediate | on_demand

class SystemConfig(BaseModel):
    output_dir: str = ""

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        if v and not os.path.exists(v):
            print(f"[Config] Warning: output_dir does not exist: {v}")
        return v

class FfmpegConfig(BaseModel):
    ffmpeg_path: str = ""
    input_device: str = ""
    model_path: str = ""
    vad_model_path: str = ""
    host: str = "127.0.0.1"
    queue_length: Annotated[int, Field(ge=1, le=30)] = 10

    @field_validator("ffmpeg_path")
    @classmethod
    def validate_ffmpeg_path(cls, v: str) -> str:
        if v and not os.path.exists(v):
            print(f"[Config] Warning: ffmpeg_path does not exist: {v}")
        return v

class ResolveConfig(BaseModel):
    enabled: bool = False
    audio_track_index: Annotated[int, Field(ge=1, le=50)] = 1
    subtitle_track_index: Annotated[int, Field(ge=1, le=50)] = 2
    template_bin: str = "VoiceVox Captions"
    template_name: str = "DefaultTemplate"

class ConfigSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')  # Ignore unknown fields

    server: ServerConfig = Field(default_factory=ServerConfig)
    voicevox: VoiceVoxConfig = Field(default_factory=VoiceVoxConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    ffmpeg: FfmpegConfig = Field(default_factory=FfmpegConfig)
    resolve: ResolveConfig = Field(default_factory=ResolveConfig)
