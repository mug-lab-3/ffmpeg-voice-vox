"""
API Schemas for System Domain.

IMPORTANT:
The definitions in this file must strictly follow the specifications
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from typing import List, Optional
from app.api.schemas.base import BaseResponse


class DevicesResponse(BaseResponse):
    devices: List[str]


class BrowseResponse(BaseResponse):
    path: Optional[str] = None
