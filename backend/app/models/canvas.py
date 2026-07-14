import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.core.database import Base, GUID


class Canvas(Base):
    __tablename__ = "canvases"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, default="未命名画布")
    description = Column(Text, nullable=True)
    user_id = Column(String(255), nullable=True, index=True)
    team_id = Column(GUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    thumbnail_url = Column(String(512), nullable=True)
    meta = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    nodes = relationship("Node", back_populates="canvas", cascade="all, delete-orphan", lazy="select")
    edges = relationship("Edge", back_populates="canvas", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        Index("idx_canvases_team_id", "team_id"),
    )
