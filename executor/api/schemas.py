from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ScanCreate(BaseModel):
    name: str
    target: str
    config: Optional[Dict[str, Any]] = None


class ScanResponseModel(BaseModel):
    id: uuid.UUID
    name: str
    target: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskSubmit(BaseModel):
    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    payload: Optional[Any] = None
    auth_token: Optional[str] = None
    retry_count: int = 3
    priority_level: str = "P3"


class QueueStats(BaseModel):
    queue_name: str
    size: int
    delayed_size: int
    dlq_size: int


class SystemMetrics(BaseModel):
    active_workers: int
    total_scans: int
    queues: List[QueueStats]


class DiscoverRequest(BaseModel):
    """Request body for the /discover endpoint."""
    spec_source: str
    base_url: Optional[str] = None
    jwt_tokens: Optional[Dict[str, str]] = None
