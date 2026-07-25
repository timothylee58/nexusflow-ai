"""Add org_id for multi-tenancy; expand role to include operator/viewer

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add org_id to all three tables with "default" as the back-fill value
    for table in ("slack_users", "agent_actions", "audit_logs"):
        op.add_column(
            table,
            sa.Column("org_id", sa.String(128), nullable=False, server_default="default"),
        )
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])


def downgrade() -> None:
    for table in ("slack_users", "agent_actions", "audit_logs"):
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_column(table, "org_id")
