from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_canvas_access
from app.core.database import get_db
from app.crud import edge as crud_edge
from app.crud import canvas as crud_canvas
from app.crud import node as crud_node
from app.models.edge import Edge
from app.models.user import User
from app.schemas.edge import EdgeCreate, EdgeUpdate, EdgeInDB

router = APIRouter(prefix="/edges", tags=["edges"])


def _check_edge_canvas_access(edge, db: Session, current_user: User):
    """校验连线所属画布的访问权限。"""
    canvas = crud_canvas.get_canvas(db, edge.canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="画布不存在")
    if canvas.user_id and str(canvas.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="没有权限访问该连线")


@router.post("", response_model=EdgeInDB, status_code=201)
def create_edge(
    edge_in: EdgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    canvas = crud_canvas.get_canvas(db, edge_in.canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="画布不存在")
    if canvas.user_id and str(canvas.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="没有权限访问该画布")
    # 校验自环
    if edge_in.source_node_id == edge_in.target_node_id:
        raise HTTPException(status_code=400, detail="不允许自环连线")
    # 校验源/目标节点存在
    source_node = crud_node.get_node(db, edge_in.source_node_id)
    if not source_node:
        raise HTTPException(status_code=400, detail="源节点不存在")
    target_node = crud_node.get_node(db, edge_in.target_node_id)
    if not target_node:
        raise HTTPException(status_code=400, detail="目标节点不存在")
    # 校验节点属于同一画布
    if source_node.canvas_id != edge_in.canvas_id or target_node.canvas_id != edge_in.canvas_id:
        raise HTTPException(status_code=400, detail="节点不属于该画布")
    # 校验重复边
    existing = db.query(Edge).filter(
        Edge.source_node_id == edge_in.source_node_id,
        Edge.target_node_id == edge_in.target_node_id,
        Edge.edge_type == edge_in.edge_type,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该连线已存在")
    return crud_edge.create_edge(db, edge_in)


@router.get("/{edge_id}", response_model=EdgeInDB)
def get_edge(
    edge_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edge = crud_edge.get_edge(db, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="连线不存在")
    _check_edge_canvas_access(edge, db, current_user)
    return edge


@router.get("/canvas/{canvas_id}", response_model=List[EdgeInDB])
def list_edges_by_canvas(
    canvas_id: UUID,
    db: Session = Depends(get_db),
    canvas=Depends(require_canvas_access),
):
    return crud_edge.get_edges_by_canvas(db, canvas_id)


@router.patch("/{edge_id}", response_model=EdgeInDB)
def update_edge(
    edge_id: UUID,
    edge_in: EdgeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edge = crud_edge.get_edge(db, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="连线不存在")
    _check_edge_canvas_access(edge, db, current_user)
    return crud_edge.update_edge(db, edge, edge_in)


@router.delete("/{edge_id}", status_code=204)
def delete_edge(
    edge_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edge = crud_edge.get_edge(db, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="连线不存在")
    _check_edge_canvas_access(edge, db, current_user)
    crud_edge.delete_edge(db, edge_id)
    return None
