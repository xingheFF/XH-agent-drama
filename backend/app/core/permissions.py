"""
统一的画布/资产权限判断函数。
支持：个人所有者、团队协作者、显式 CanvasCollaborator 协作者。
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.canvas import Canvas
from app.models.collaboration import CanvasCollaborator, CollaboratorRole
from app.models.team import TeamMember, TeamMemberRole


def _is_owner(user_id: str, canvas: Canvas) -> bool:
    return bool(canvas.user_id) and str(canvas.user_id) == str(user_id)


def _get_team_member(db: Session, user_id: str, team_id: UUID) -> Optional[TeamMember]:
    return (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == str(user_id))
        .first()
    )


def _get_collaborator(db: Session, user_id: str, canvas_id: UUID) -> Optional[CanvasCollaborator]:
    return (
        db.query(CanvasCollaborator)
        .filter(CanvasCollaborator.canvas_id == canvas_id, CanvasCollaborator.user_id == str(user_id))
        .first()
    )


def can_access_canvas(db: Session, user_id: str, canvas: Canvas) -> bool:
    """用户是否可以访问画布（查看）。"""
    if not canvas:
        return False
    if _is_owner(user_id, canvas):
        return True
    if canvas.team_id:
        member = _get_team_member(db, user_id, canvas.team_id)
        if member:
            return True
    collab = _get_collaborator(db, user_id, canvas.id)
    if collab and collab.invite_status == "accepted":
        return True
    return False


def can_edit_canvas(db: Session, user_id: str, canvas: Canvas) -> bool:
    """用户是否可以编辑画布内容。"""
    if not canvas:
        return False
    if _is_owner(user_id, canvas):
        return True
    if canvas.team_id:
        member = _get_team_member(db, user_id, canvas.team_id)
        if member and member.role in {
            TeamMemberRole.OWNER,
            TeamMemberRole.ADMIN,
            TeamMemberRole.MEMBER,
        }:
            return True
    collab = _get_collaborator(db, user_id, canvas.id)
    if collab and collab.invite_status == "accepted" and collab.role == CollaboratorRole.EDITOR:
        return True
    return False


def can_delete_canvas(db: Session, user_id: str, canvas: Canvas) -> bool:
    """用户是否可以删除画布。"""
    if not canvas:
        return False
    if _is_owner(user_id, canvas):
        return True
    if canvas.team_id:
        member = _get_team_member(db, user_id, canvas.team_id)
        if member and member.role in {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}:
            return True
    return False


def can_manage_team_canvas(db: Session, user_id: str, canvas: Canvas) -> bool:
    """用户是否可以管理团队画布（转移、修改基础信息）。"""
    return can_delete_canvas(db, user_id, canvas)
