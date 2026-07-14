"""
团队相关 Pydantic Schema。
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TeamMemberOut(BaseModel):
    id: UUID
    user_id: str
    username: Optional[str] = None
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamBase(BaseModel):
    name: str


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = None


class TeamOut(TeamBase):
    id: UUID
    team_code: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    members: Optional[List[TeamMemberOut]] = None

    model_config = ConfigDict(from_attributes=True)


class JoinTeamRequest(BaseModel):
    team_code: str


class UpdateMemberRoleRequest(BaseModel):
    role: str  # owner / admin / member


class TeamListOut(BaseModel):
    teams: List[TeamOut]
    total: int
