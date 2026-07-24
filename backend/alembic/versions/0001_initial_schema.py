"""Initial schema — slack_users, agent_actions, audit_logs

Revision ID: 0001
Revises:
Create Date: 2026-07-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "slack_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slack_user_id", sa.String(32), nullable=False, unique=True),
        sa.Column("slack_username", sa.String(128), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("added_by", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("parsed_command", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("execution_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("execution_path", sa.Text(), nullable=True),
        sa.Column("slack_message_ts", sa.String(128), nullable=True),
        sa.Column("hitl_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("user_input", sa.Text(), nullable=True),
        sa.Column("execution_path", sa.Text(), nullable=True),
        sa.Column("approval_choice", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(32), nullable=True),
        sa.Column("estimated_impact", sa.Float(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_agent_actions_user_id", "agent_actions", ["user_id"])
    op.create_index("ix_agent_actions_execution_status", "agent_actions", ["execution_status"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_actions")
    op.drop_table("slack_users")
