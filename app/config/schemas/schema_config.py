from pydantic import Field, ConfigDict
from .base import BaseConfigModel
from .schema_server import ServerConfig
from .schema_voicevox import VoiceVoxConfig
from .schema_synthesis import SynthesisConfig
from .schema_system import SystemConfig
from .schema_ffmpeg import FfmpegConfig
from .schema_resolve import ResolveConfig


class ConfigSchema(BaseConfigModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    voicevox: VoiceVoxConfig = Field(default_factory=VoiceVoxConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    ffmpeg: FfmpegConfig = Field(default_factory=FfmpegConfig)
    resolve: ResolveConfig = Field(default_factory=ResolveConfig)
