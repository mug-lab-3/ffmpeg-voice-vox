from pydantic import Field
from .base import BaseConfigModel


class ServerConfig(BaseConfigModel):
    host: str = "127.0.0.1"
    port: int = Field(default=3000, ge=1, le=65535)
