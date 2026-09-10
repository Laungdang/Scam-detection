"""add chat_sessions.deleted_at for soft delete

Revision ID: 7d6e2894fa54
Revises: 9649663f41b2
Create Date: 2026-05-16 16:16:41.983096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d6e2894fa54'
down_revision: Union[str, Sequence[str], None] = '9649663f41b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at column for soft delete (Heuristic Eval H3 fix)."""
    op.add_column(
        "chat_sessions",
        sa.Column("deleted_at", sa.TIMESTAMP(), nullable=True),
    )
    op.create_index(
        "ix_chat_sessions_deleted_at",
        "chat_sessions",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_deleted_at", table_name="chat_sessions")
    op.drop_column("chat_sessions", "deleted_at")
