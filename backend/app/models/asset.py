import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, JSON, Enum as SAEnum, Index
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base, GUID


class AssetType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    CHARACTER = "character"
    SCENE = "scene"
    OTHER = "other"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True, index=True)
    team_id = Column(GUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    canvas_id = Column(GUID(), ForeignKey("canvases.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False, default="未命名资产")
    asset_type = Column(SAEnum(AssetType), nullable=False, default=AssetType.IMAGE)
    file_path = Column(String(512), nullable=False)
    file_url = Column(String(512), nullable=False)
    thumbnail_url = Column(String(512), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    description = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
