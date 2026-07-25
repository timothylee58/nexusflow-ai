import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    event_type: str,
    user_id: str | None = None,
    org_id: str = "default",
    user_input: str | None = None,
    execution_path: list[str] | None = None,
    approval_choice: str | None = None,
    notes: str | None = None,
    severity: str | None = None,
    estimated_impact: float | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        org_id=org_id,
        user_input=user_input,
        execution_path=json.dumps(execution_path) if execution_path else None,
        approval_choice=approval_choice,
        notes=notes,
        severity=severity,
        estimated_impact=estimated_impact,
        payload=json.dumps(payload) if payload else None,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry
