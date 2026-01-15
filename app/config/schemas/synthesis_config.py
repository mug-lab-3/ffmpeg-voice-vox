from pydantic import Field
from typing import Annotated
from .base import BaseConfigModel


class SynthesisConfig(BaseConfigModel):
    speaker_id: Annotated[int, Field(ge=0)] = 1
    speed_scale: Annotated[float, Field(ge=0.5, le=1.5)] = 1.0
    pitch_scale: Annotated[float, Field(ge=-0.15, le=0.15)] = 0.0
    intonation_scale: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    volume_scale: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    pre_phoneme_length: Annotated[float, Field(ge=0.0, le=1.5)] = 0.1
    post_phoneme_length: Annotated[float, Field(ge=0.0, le=1.5)] = 0.1
    pause_length_scale: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    timing: str = "on_demand"  # immediate | on_demand
