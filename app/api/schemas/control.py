"""
API Schemas for Control Domain.

IMPORTANT:
The definitions in this file must strictly follow the specifications
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict
from app.api.schemas.base import BaseResponse


class LogEntry(BaseModel):
    timestamp: str
    text: str
    duration: str
    config: dict
    filename: str


class LogsResponse(BaseResponse):
    logs: List[LogEntry]


class ControlStateResponse(BaseResponse):
    enabled: bool
    playback: Optional[dict] = None
    resolve_available: bool
    voicevox_available: bool


class PlayResponse(BaseResponse):
    duration: float
    start_time: float


class DeleteResponse(BaseResponse):
    deleted: List[str]


class ControlStateRequest(BaseModel):
    enabled: bool


class FilenameRequest(BaseModel):
    filename: str
