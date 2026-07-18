from typing import List
from uuid import UUID
import logging
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

logger = logging.getLogger(__name__)

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
    user_id = str(current_user.id)
    # 修改所属团队需要管理权限（owner 或团队 admin）
    if canvas_in.team_id is not None and not can_manage_team_canvas(db, user_id, canvas):
        raise HTTPException(status_code=403, detail="无权修改画布所属团队")

    # 如果要转移团队，校验目标团队是当前用户所在团队（防止转移到非自己团队）
    # team_id 为空字符串/None 表示转为个人项目，允许；非空时必须校验成员身份
    new_team_id = canvas_in.team_id
    team_changed = False
    if new_team_id is not None:
        # 归一化：空字符串视为 None（个人项目）
        try:
            target_team_id = UUID(str(new_team_id)) if str(new_team_id).strip() else None
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="team_id 格式错误")
        if target_team_id:
            if not team_crud.is_team_member(db, user_id=user_id, team_id=target_team_id):
                raise HTTPException(status_code=403, detail="你不是目标团队成员，无法转移该项目到该团队")
        # 判断是否真的发生变化
        old_team_id = canvas.team_id
        if target_team_id != old_team_id:
            team_changed = True
        # 把归一化后的值写回，避免空字符串残留
        canvas_in.team_id = target_team_id

    updated = crud_canvas.update_canvas(db, canvas, canvas_in)

    # 团队归属变化时，批量迁移画布下已有资产的 team_id，确保团队成员可见
    if team_changed:
        new_tid = updated.team_id
        db.query(Asset).filter(Asset.canvas_id == str(updated.id)).update(
            {Asset.team_id: new_tid}, synchronize_session=False
        )
        db.commit()
        logger.info(
            "[update_canvas] 画布 %s 团队归属变更: %s -> %s，已迁移资产 team_id",
            updated.id, old_team_id, new_tid,
        )

    return updated


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
