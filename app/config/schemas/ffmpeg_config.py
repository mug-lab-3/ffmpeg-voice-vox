import os
import re
from pydantic import Field, field_validator
from typing import Annotated
from .base import BaseConfigModel


class FfmpegConfig(BaseConfigModel):
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

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if not v:
            raise ValueError("Host cannot be empty")

        ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"

        if re.match(ip_pattern, v) or re.match(hostname_pattern, v) or v == "localhost":
            return v
        raise ValueError(f"Invalid host format: {v}")
