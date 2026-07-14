"""
团队 CRUD。
"""
import random
import string
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.team import Team, TeamMember, TeamMemberRole


_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LENGTH = 6


def _generate_team_code() -> str:
    """生成 6 位大写字母+数字团号。"""
    return "".join(random.choices(_CODE_CHARS, k=_CODE_LENGTH))


def create_team(db: Session, name: str, owner_id: str) -> Team:
    """创建团队，自动生成唯一团号，并把所有者加入成员。"""
    # 简单防重试
    for _ in range(10):
        code = _generate_team_code()
        existing = db.query(Team).filter(Team.team_code == code).first()
        if not existing:
            break
    else:
        raise RuntimeError("无法生成唯一团号")

    team = Team(name=name, team_code=code, owner_id=owner_id)
    db.add(team)
    db.flush()  # 拿到 team.id

    owner_member = TeamMember(
        team_id=team.id,
        user_id=owner_id,
        role=TeamMemberRole.OWNER,
    )
    db.add(owner_member)
    db.commit()
    db.refresh(team)
    return team


def get_team(db: Session, team_id: UUID) -> Optional[Team]:
    return db.query(Team).filter(Team.id == team_id).first()


def get_team_by_code(db: Session, team_code: str) -> Optional[Team]:
    return db.query(Team).filter(Team.team_code == team_code.upper().strip()).first()


def get_user_teams(db: Session, user_id: str) -> List[Team]:
    """获取用户加入的所有团队。"""
    return (
        db.query(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user_id)
        .order_by(Team.updated_at.desc())
        .all()
    )


def is_team_member(db: Session, user_id: str, team_id: UUID) -> bool:
    return (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
        is not None
    )


def get_team_member(db: Session, user_id: str, team_id: UUID) -> Optional[TeamMember]:
    return (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )


def add_team_member(db: Session, team_id: UUID, user_id: str, role: TeamMemberRole = TeamMemberRole.MEMBER) -> TeamMember:
    member = TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_team_member_role(db: Session, member: TeamMember, role: TeamMemberRole) -> TeamMember:
    member.role = role
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_team_member(db: Session, member: TeamMember) -> None:
    db.delete(member)
    db.commit()


def update_team(db: Session, team: Team, name: str) -> Team:
    team.name = name
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def delete_team(db: Session, team: Team) -> None:
    db.delete(team)
    db.commit()
