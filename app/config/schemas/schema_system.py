import os
from pydantic import field_validator
from .base import BaseConfigModel


class SystemConfig(BaseConfigModel):
    output_dir: str = ""

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        if v and not os.path.exists(v):
            print(f"[Config] Warning: output_dir does not exist: {v}")
        return v
