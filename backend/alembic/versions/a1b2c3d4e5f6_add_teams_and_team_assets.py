"""add teams and team assets

Revision ID: a1b2c3d4e5f6
Revises: 11c0ab19dc92
Create Date: 2026-07-15 00:00:00.000000

新增团队表、团队成员表，并为 canvases/assets 增加 team_id 字段。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.database import GUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '11c0ab19dc92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    """检查表是否已存在（兼容 SQLite 和 PostgreSQL）。"""
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    """检查列是否已存在。"""
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(c["name"] == column_name for c in columns)


def upgrade() -> None:
    bind = op.get_bind()

    # teams
    if not _table_exists(bind, 'teams'):
        op.create_table(
            'teams',
            sa.Column('id', GUID(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('team_code', sa.String(length=16), nullable=False),
            sa.Column('owner_id', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('team_code')
        )
        op.create_index(op.f('ix_teams_owner_id'), 'teams', ['owner_id'], unique=False)
        op.create_index(op.f('ix_teams_team_code'), 'teams', ['team_code'], unique=True)

    # team_members
    if not _table_exists(bind, 'team_members'):
        op.create_table(
            'team_members',
            sa.Column('id', GUID(), nullable=False),
            sa.Column('team_id', GUID(), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('role', sa.Enum('owner', 'admin', 'member', name='teammemberrole'), nullable=False),
            sa.Column('joined_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('team_id', 'user_id', name='uq_team_user')
        )
        op.create_index(op.f('ix_team_members_team_id'), 'team_members', ['team_id'], unique=False)
        op.create_index(op.f('ix_team_members_user_id'), 'team_members', ['user_id'], unique=False)

    # canvases.team_id
    if not _column_exists(bind, 'canvases', 'team_id'):
        op.add_column('canvases', sa.Column('team_id', GUID(), nullable=True))
        op.create_index(op.f('ix_canvases_team_id'), 'canvases', ['team_id'], unique=False)
        op.create_foreign_key('fk_canvases_team_id', 'canvases', 'teams', ['team_id'], ['id'], ondelete='SET NULL')

    # assets.team_id
    if not _column_exists(bind, 'assets', 'team_id'):
        op.add_column('assets', sa.Column('team_id', GUID(), nullable=True))
        op.create_index(op.f('ix_assets_team_id'), 'assets', ['team_id'], unique=False)
        op.create_foreign_key('fk_assets_team_id', 'assets', 'teams', ['team_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, 'assets', 'team_id'):
        op.drop_constraint('fk_assets_team_id', 'assets', type_='foreignkey')
        op.drop_index(op.f('ix_assets_team_id'), table_name='assets')
        op.drop_column('assets', 'team_id')

    if _column_exists(bind, 'canvases', 'team_id'):
        op.drop_constraint('fk_canvases_team_id', 'canvases', type_='foreignkey')
        op.drop_index(op.f('ix_canvases_team_id'), table_name='canvases')
        op.drop_column('canvases', 'team_id')

    if _table_exists(bind, 'team_members'):
        op.drop_index(op.f('ix_team_members_user_id'), table_name='team_members')
        op.drop_index(op.f('ix_team_members_team_id'), table_name='team_members')
        op.drop_table('team_members')

    if _table_exists(bind, 'teams'):
        op.drop_index(op.f('ix_teams_team_code'), table_name='teams')
        op.drop_index(op.f('ix_teams_owner_id'), table_name='teams')
        op.drop_table('teams')
