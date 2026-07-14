from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.canvas import Canvas
from app.models.team import TeamMember
from app.schemas.canvas import CanvasCreate, CanvasUpdate


def create_canvas(
    db: Session,
    canvas_in: CanvasCreate,
    commit: bool = True,
    extra_data: dict = None,
) -> Canvas:
    data = canvas_in.model_dump(exclude_unset=True)
    if extra_data:
        data.update(extra_data)
    canvas = Canvas(**data)
    db.add(canvas)
    if commit:
        db.commit()
        db.refresh(canvas)
    else:
        # 事务内创建时需要 flush 才能拿到 default UUID，否则 canvas.id 为 None
        db.flush()
    return canvas


def get_canvas(db: Session, canvas_id: UUID) -> Optional[Canvas]:
    return db.query(Canvas).filter(Canvas.id == canvas_id).first()


def get_canvases(db: Session, user_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Canvas]:
    """列出用户有权限查看的画布：个人画布 + 所属团队的画布。"""
    query = db.query(Canvas)
    if user_id:
        # 个人画布
        own_filter = Canvas.user_id == user_id
        # 用户所属团队的画布
        team_ids_subquery = (
            db.query(TeamMember.team_id)
            .filter(TeamMember.user_id == user_id)
        )
        team_filter = Canvas.team_id.in_(team_ids_subquery)
        query = query.filter(or_(own_filter, team_filter))
    return query.order_by(Canvas.updated_at.desc()).offset(skip).limit(limit).all()


def update_canvas(db: Session, canvas: Canvas, canvas_in: CanvasUpdate) -> Canvas:
    update_data = canvas_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(canvas, field, value)
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


def delete_canvas(db: Session, canvas_id: UUID) -> bool:
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if not canvas:
        return False
    db.delete(canvas)
    db.commit()
    return True
