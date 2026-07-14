from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class CanvasBase(BaseModel):
    name: Optional[str] = "未命名画布"
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = {}


class CanvasCreate(CanvasBase):
    team_id: Optional[UUID] = None


class CanvasUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    team_id: Optional[UUID] = None


class CanvasInDB(CanvasBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[str] = None
    team_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
