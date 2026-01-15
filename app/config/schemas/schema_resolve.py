from pydantic import Field
from typing import Annotated
from .base import BaseConfigModel


class ResolveConfig(BaseConfigModel):
    enabled: bool = False
    audio_track_index: Annotated[int, Field(ge=1, le=50)] = 1
    video_track_index: Annotated[int, Field(ge=1, le=50)] = 2
    target_bin: str = "VoiceVox Captions"
    template_name: str = "Auto"
