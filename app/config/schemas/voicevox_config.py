from .base import BaseConfigModel


class VoiceVoxConfig(BaseConfigModel):
    host: str = "127.0.0.1"
    port: int = 50021
