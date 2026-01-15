from .base import BaseConfigModel


class ServerConfig(BaseConfigModel):
    host: str = "127.0.0.1"
