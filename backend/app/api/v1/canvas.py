from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_current_active_user, require_canvas_access, require_canvas_edit
from app.core.database import get_db
from app.crud import canvas as crud_canvas
from app.crud import team as team_crud
from app.models.asset import Asset
from app.models.canvas import Canvas
from app.models.edge import Edge
from app.models.node import Node
from app.models.snapshot import CanvasSnapshot
from app.models.user import User
from app.schemas.canvas import CanvasCreate, CanvasUpdate, CanvasInDB
from app.schemas import CanvasDetail
from app.core.permissions import can_delete_canvas, can_manage_team_canvas

router = APIRouter(prefix="/canvases", tags=["canvases"])


@router.post("", response_model=CanvasInDB, status_code=201)
def create_canvas(
    canvas_in: CanvasCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    extra_data = {"user_id": str(current_user.id)}
    # 如果指定了 team_id，校验用户是否为团队成员
    if canvas_in.team_id:
        if not team_crud.is_team_member(db, user_id=str(current_user.id), team_id=canvas_in.team_id):
            raise HTTPException(status_code=403, detail="你不是该团队成员，无法创建团队画布")
        extra_data["team_id"] = canvas_in.team_id
    return crud_canvas.create_canvas(
        db,
        canvas_in,
        extra_data=extra_data,
    )


@router.get("", response_model=List[CanvasInDB])
def list_canvases(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return crud_canvas.get_canvases(
        db,
        user_id=str(current_user.id),
        skip=skip,
        limit=min(limit, 200),
    )


@router.get("/{canvas_id}", response_model=CanvasDetail)
def get_canvas(
    canvas_id: UUID,
    canvas: Canvas = Depends(require_canvas_access),
):
    return canvas


@router.patch("/{canvas_id}", response_model=CanvasInDB)
def update_canvas(
    canvas_id: UUID,
    canvas_in: CanvasUpdate,
    canvas: Canvas = Depends(require_canvas_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # 仅基础信息修改（名称、描述等）需要管理权限；内容编辑走节点/边接口
    if canvas_in.team_id is not None and not can_manage_team_canvas(db, str(current_user.id), canvas):
        raise HTTPException(status_code=403, detail="无权修改画布所属团队")
    return crud_canvas.update_canvas(db, canvas, canvas_in)


@router.delete("/{canvas_id}", status_code=204)
def delete_canvas(
    canvas_id: UUID,
    canvas: Canvas = Depends(require_canvas_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not can_delete_canvas(db, str(current_user.id), canvas):
        raise HTTPException(status_code=403, detail="没有权限删除该画布")
    cid = str(canvas.id)
    # 级联删除关联数据，避免外键约束失败
    db.query(Asset).filter(Asset.canvas_id == cid).delete(synchronize_session=False)
    db.query(Edge).filter(Edge.canvas_id == cid).delete(synchronize_session=False)
    db.query(Node).filter(Node.canvas_id == cid).delete(synchronize_session=False)
    db.query(CanvasSnapshot).filter(CanvasSnapshot.canvas_id == cid).delete(synchronize_session=False)
    db.delete(canvas)
    db.commit()
    return None
