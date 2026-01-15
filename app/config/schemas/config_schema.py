from pydantic import Field, ConfigDict
from .base import BaseConfigModel
from .server_config import ServerConfig
from .voicevox_config import VoiceVoxConfig
from .synthesis_config import SynthesisConfig
from .system_config import SystemConfig
from .ffmpeg_config import FfmpegConfig
from .resolve_config import ResolveConfig


class ConfigSchema(BaseConfigModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    voicevox: VoiceVoxConfig = Field(default_factory=VoiceVoxConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    ffmpeg: FfmpegConfig = Field(default_factory=FfmpegConfig)
    resolve: ResolveConfig = Field(default_factory=ResolveConfig)
