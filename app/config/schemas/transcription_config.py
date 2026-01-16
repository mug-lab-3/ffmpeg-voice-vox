import os
from pydantic import Field, field_validator
from typing import Optional, Literal, Any
from .base import BaseConfigModel


class TranscriptionConfig(BaseConfigModel):
    model_size: str = "base"
    device: Literal["cpu", "cuda", "auto"] = "cpu"
    compute_type: str = "default"
    input_device: Optional[str] = ""
    model_path: Optional[str] = Field(default="", validate_default=True)
    beam_size: int = Field(default=5, ge=1, le=10)
    language: Optional[str] = Field(default="ja", max_length=2)

    @field_validator("model_path")
    @classmethod
    def validate_model_path(cls, v: str) -> str:
        if v and not os.path.exists(v):
            print(f"[Config] Warning: model_path does not exist: {v}")
        return v
