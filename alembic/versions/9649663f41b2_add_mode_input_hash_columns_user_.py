"""add mode/input_hash columns + user_consents + pii_access_log tables

Revision ID: 9649663f41b2
Revises:
Create Date: 2026-05-16

PDPA compliance migration — ดู CLAUDE.md Section 2.8 + 6.5

Changes:
- เพิ่ม `mode` column ใน `check_requests` (แยก ML vs Q&A mode)
- เพิ่ม `input_hash` column ใน `check_requests` (SHA256 สำหรับ dedup)
- สร้าง `user_consents` table (PDPA มาตรา 19)
- สร้าง `pii_access_log` table (PDPA มาตรา 39)
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


revision: str = "9649663f41b2"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) แก้ check_requests — เพิ่ม mode, input_hash
    op.add_column(
        "check_requests",
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="qa"),
    )
    op.add_column(
        "check_requests",
        sa.Column("input_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_check_requests_input_hash",
        "check_requests",
        ["input_hash"],
    )

    # 2) user_consents table (PDPA มาตรา 19)
    op.create_table(
        "user_consents",
        sa.Column("consent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_token", sa.String(length=128), nullable=True),
        sa.Column("consent_version", sa.String(length=20), nullable=False),
        sa.Column(
            "accepted_at",
            sa.TIMESTAMP(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("withdrawn_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("consent_id"),
    )
    op.create_index(
        "ix_user_consents_session_token",
        "user_consents",
        ["session_token"],
    )

    # 3) pii_access_log table (PDPA มาตรา 39)
    op.create_table(
        "pii_access_log",
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("accessed_field_type", sa.String(length=50), nullable=False),
        sa.Column("accessor_service", sa.String(length=100), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["check_requests.request_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(
        "ix_pii_access_log_input_hash",
        "pii_access_log",
        ["input_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_pii_access_log_input_hash", table_name="pii_access_log")
    op.drop_table("pii_access_log")

    op.drop_index("ix_user_consents_session_token", table_name="user_consents")
    op.drop_table("user_consents")

    op.drop_index("ix_check_requests_input_hash", table_name="check_requests")
    op.drop_column("check_requests", "input_hash")
    op.drop_column("check_requests", "mode")
