"""
团队管理 API：创建团队、团号加入、成员管理。
"""
import logging
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.team import TeamMemberRole
from app.models.user import User
from app.schemas.team import (
    TeamCreate,
    TeamUpdate,
    TeamOut,
    TeamListOut,
    JoinTeamRequest,
    UpdateMemberRoleRequest,
    TeamMemberOut,
)
from app.crud import team as team_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])


def _serialize_team(team: Any, include_members: bool = True) -> dict:
    """把 Team ORM 对象序列化为响应字典。"""
    data = {
        "id": str(team.id),
        "name": team.name,
        "team_code": team.team_code,
        "owner_id": team.owner_id,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
    }
    if include_members and team.members:
        data["members"] = [_serialize_member(m) for m in team.members]
    else:
        data["members"] = []
    return data


def _serialize_member(member: Any) -> dict:
    role = member.role.value if hasattr(member.role, "value") else str(member.role)
    return {
        "id": str(member.id),
        "user_id": member.user_id,
        "username": member.username if hasattr(member, "username") else None,
        "role": role,
        "joined_at": member.joined_at,
    }


@router.post("", response_model=TeamOut)
async def create_team(
    req: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建团队，自动生成团号。"""
    team = team_crud.create_team(db, name=req.name, owner_id=str(current_user.id))
    return _serialize_team(team)


@router.get("", response_model=TeamListOut)
async def list_my_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我加入/创建的团队列表。"""
    teams = team_crud.get_user_teams(db, user_id=str(current_user.id))
    return {
        "teams": [_serialize_team(t, include_members=False) for t in teams],
        "total": len(teams),
    }


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取团队详情（含成员列表），仅限团队成员。"""
    team = team_crud.get_team(db, team_id=team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if not team_crud.is_team_member(db, user_id=str(current_user.id), team_id=team_id):
        raise HTTPException(status_code=403, detail="无权访问该团队")
    return _serialize_team(team, include_members=True)


@router.put("/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: UUID,
    req: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改团队名称（owner/admin 可修改）。"""
    team = team_crud.get_team(db, team_id=team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    member = team_crud.get_team_member(db, user_id=str(current_user.id), team_id=team_id)
    if not member or member.role not in {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}:
        raise HTTPException(status_code=403, detail="无权修改团队信息")

    if not req.name:
        raise HTTPException(status_code=400, detail="团队名称不能为空")

    team = team_crud.update_team(db, team=team, name=req.name)
    return _serialize_team(team)


@router.delete("/{team_id}")
async def delete_team(
    team_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解散团队（仅 owner）。"""
    team = team_crud.get_team(db, team_id=team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if str(team.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="仅团队所有者可以解散团队")

    team_crud.delete_team(db, team=team)
    return {"status": "ok", "message": "团队已解散"}


@router.post("/join")
async def join_team_by_code(
    req: JoinTeamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """输入团号加入团队。"""
    team = team_crud.get_team_by_code(db, team_code=req.team_code)
    if not team:
        raise HTTPException(status_code=404, detail="团号不存在")

    user_id = str(current_user.id)
    existing = team_crud.get_team_member(db, user_id=user_id, team_id=team.id)
    if existing:
        raise HTTPException(status_code=409, detail="你已是该团队成员")

    team_crud.add_team_member(db, team_id=team.id, user_id=user_id, role=TeamMemberRole.MEMBER)
    return {"status": "ok", "team_id": str(team.id), "team_name": team.name}


@router.put("/{team_id}/members/{user_id}/role", response_model=TeamMemberOut)
async def update_member_role(
    team_id: UUID,
    user_id: str,
    req: UpdateMemberRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改成员角色（owner/admin 可修改，owner 不能被降级）。"""
    team = team_crud.get_team(db, team_id=team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    operator = team_crud.get_team_member(db, user_id=str(current_user.id), team_id=team_id)
    if not operator or operator.role not in {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}:
        raise HTTPException(status_code=403, detail="无权修改成员角色")

    target = team_crud.get_team_member(db, user_id=user_id, team_id=team_id)
    if not target:
        raise HTTPException(status_code=404, detail="成员不存在")

    # owner 不能被降级/删除
    if target.role == TeamMemberRole.OWNER:
        raise HTTPException(status_code=403, detail="不能修改团队所有者角色")

    # admin 不能修改其他 admin 或 owner
    if operator.role == TeamMemberRole.ADMIN and target.role in {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}:
        raise HTTPException(status_code=403, detail="admin 不能修改该成员角色")

    role_map = {
        "owner": TeamMemberRole.OWNER,
        "admin": TeamMemberRole.ADMIN,
        "member": TeamMemberRole.MEMBER,
    }
    new_role = role_map.get(req.role.lower())
    if not new_role:
        raise HTTPException(status_code=400, detail="无效角色")

    target = team_crud.update_team_member_role(db, member=target, role=new_role)
    return _serialize_member(target)


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(
    team_id: UUID,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除团队成员（owner/admin 可移除，owner 不能被移除）。"""
    team = team_crud.get_team(db, team_id=team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    operator_id = str(current_user.id)
    # 允许自己退出团队
    if operator_id == user_id:
        if str(team.owner_id) == user_id:
            raise HTTPException(status_code=400, detail="团队所有者不能退出，请先转让所有权或解散团队")
        member = team_crud.get_team_member(db, user_id=user_id, team_id=team_id)
        if not member:
            raise HTTPException(status_code=404, detail="你不是该团队成员")
        team_crud.remove_team_member(db, member=member)
        return {"status": "ok", "message": "已退出团队"}

    operator = team_crud.get_team_member(db, user_id=operator_id, team_id=team_id)
    if not operator or operator.role not in {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}:
        raise HTTPException(status_code=403, detail="无权移除成员")

    target = team_crud.get_team_member(db, user_id=user_id, team_id=team_id)
    if not target:
        raise HTTPException(status_code=404, detail="成员不存在")
    if target.role == TeamMemberRole.OWNER:
        raise HTTPException(status_code=403, detail="不能移除团队所有者")
    if operator.role == TeamMemberRole.ADMIN and target.role == TeamMemberRole.ADMIN:
        raise HTTPException(status_code=403, detail="admin 不能移除其他 admin")

    team_crud.remove_team_member(db, member=target)
    return {"status": "ok", "message": "成员已移除"}
