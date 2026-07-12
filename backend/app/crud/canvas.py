from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.canvas import Canvas
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
    query = db.query(Canvas)
    if user_id:
        query = query.filter(Canvas.user_id == user_id)
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
