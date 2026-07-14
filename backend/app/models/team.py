"""
团队模型：支持创建团队、团号加入、团队画布与资产共享。
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, GUID


class TeamMemberRole(str, enum.Enum):
    """团队成员角色。"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Team(Base):
    """团队。"""
    __tablename__ = "teams"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, default="未命名团队")
    team_code = Column(String(16), nullable=False, unique=True, index=True)
    owner_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan", lazy="select")


class TeamMember(Base):
    """团队成员关系。"""
    __tablename__ = "team_members"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    team_id = Column(GUID(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    role = Column(SAEnum(TeamMemberRole), nullable=False, default=TeamMemberRole.MEMBER)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="members")

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user"),
        Index("idx_team_members_team_id", "team_id"),
        Index("idx_team_members_user_id", "user_id"),
    )
