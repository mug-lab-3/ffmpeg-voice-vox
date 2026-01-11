from typing import List, Optional
from app.api.schemas.base import BaseResponse

class DevicesResponse(BaseResponse):
    devices: List[str]

class BrowseResponse(BaseResponse):
    path: Optional[str] = None
