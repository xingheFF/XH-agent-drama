import os
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.asset import Asset, AssetType
from app.schemas.asset import AssetCreate, AssetUpdate


def create_asset(db: Session, asset_in: AssetCreate, file_path: str, file_url: str, mime_type: str = None, file_size: int = None, user_id: str = None, team_id: uuid.UUID = None) -> Asset:
    asset = Asset(
        **asset_in.model_dump(exclude_unset=True),
        file_path=file_path,
        file_url=file_url,
        mime_type=mime_type,
        file_size=file_size,
        user_id=user_id,
        team_id=team_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_asset(db: Session, asset_id: uuid.UUID) -> Optional[Asset]:
    return db.query(Asset).filter(Asset.id == asset_id).first()


def get_assets(db: Session, user_id: str = None, team_ids: List[uuid.UUID] = None, canvas_id: uuid.UUID = None, asset_type: AssetType = None, query: str = None, skip: int = 0, limit: int = 50) -> List[Asset]:
    q = db.query(Asset)
    filters = []
    if user_id:
        filters.append(Asset.user_id == user_id)
    if team_ids:
        filters.append(Asset.team_id.in_(team_ids))
    if filters:
        q = q.filter(or_(*filters))
    if canvas_id:
        q = q.filter(Asset.canvas_id == canvas_id)
    if asset_type:
        q = q.filter(Asset.asset_type == asset_type)
    if query:
        q = q.filter(or_(
            Asset.name.ilike(f"%{query}%"),
            Asset.description.ilike(f"%{query}%"),
        ))
    return q.order_by(Asset.created_at.desc()).offset(skip).limit(limit).all()


def update_asset_canvas_id(db: Session, asset_id: uuid.UUID, canvas_id: uuid.UUID, commit: bool = True) -> bool:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        return False
    asset.canvas_id = canvas_id
    db.add(asset)
    if commit:
        db.commit()
    return True


def update_asset(db: Session, asset: Asset, asset_in: AssetUpdate) -> Asset:
    update_data = asset_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, asset_id: uuid.UUID) -> bool:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        return False
    try:
        if os.path.exists(asset.file_path):
            os.remove(asset.file_path)
    except Exception:
        pass
    db.delete(asset)
    db.commit()
    return True
