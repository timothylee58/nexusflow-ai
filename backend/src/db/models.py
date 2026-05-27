from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(32), default="pending")
    execution_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_message_ts: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # HITL expiry — set when action is escalated to Slack
    hitl_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_choice: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estimated_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
