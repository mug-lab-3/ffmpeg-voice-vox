"""
Base API Schemas.

IMPORTANT:
The definitions in this file must strictly follow the specifications 
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""
from pydantic import BaseModel
from typing import Optional

class BaseResponse(BaseModel):
    """Base scheme for all API responses."""
    status: str = "ok"
    error_code: Optional[str] = None
    message: Optional[str] = None

class StatusResponse(BaseResponse):
    """Simple status response."""
    pass
