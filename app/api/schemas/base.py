from pydantic import BaseModel
from typing import Optional

class BaseResponse(BaseModel):
    """Base scheme for all API responses."""
    status: str = "ok"
    message: Optional[str] = None

class StatusResponse(BaseResponse):
    """Simple status response."""
    pass
