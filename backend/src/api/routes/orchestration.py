"""FastAPI routes — orchestration, SSE, audit, HITL."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import random
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.langgraph_orchestration import execute_orchestration
from src.api.deps import get_org_id, require_api_key
from src.config import settings
from src.db.models import AgentAction, AuditLog
from src.db.session import get_session
from src.services.audit_service import write_audit_log
from src.services.llm_provider import resolve_llm_provider
from src.services.redis_service import AGENT_LOG_CHANNEL, redis_service

TRAFFIC_CHANNEL = "nexusflow:traffic"

logger = logging.getLogger(__name__)

_auth = [Depends(require_api_key)]

agent_router = APIRouter(prefix="/agent", tags=["agent"], dependencies=_auth)
sse_router = APIRouter(prefix="/sse", tags=["sse"], dependencies=_auth)
audit_router = APIRouter(prefix="/audit", tags=["audit"], dependencies=_auth)


class QueryRequest(BaseModel):
    query: str
    user_id: str = "user_default"
    region: str | None = None


class OrchestrateResponse(BaseModel):
    action_id: str | None = None
    parsed_command: dict | None = None
    analysis: dict | None = None
    decision: dict | None = None
    execution_status: str
    slack_message_ts: str = ""
    execution_path: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    llm_mode: str


class HitlApprovalRequest(BaseModel):
    decision_id: str
    approval_choice: str
    user_id: str = "dashboard_user"
    notes: str = ""


class AuditEventRequest(BaseModel):
    event_type: str
    user_id: str | None = None
    user_input: str | None = None
    execution_path: list[str] | None = None
    timestamp: str | None = None
    payload: dict | None = None


@agent_router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_query(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> OrchestrateResponse:
    try:
        logger.info("[Orchestrate] org=%s query=%s", org_id, request.query)
        result = await execute_orchestration(
            user_input=request.query,
            user_id=request.user_id,
        )

        action_id: str | None = None
        if result.get("decision") and result.get("parsed_command"):
            action = AgentAction(
                user_id=request.user_id,
                org_id=org_id,
                user_input=request.query,
                parsed_command=json.dumps(result["parsed_command"]),
                analysis=json.dumps(result["analysis"]) if result.get("analysis") else None,
                decision=json.dumps(result["decision"]),
                execution_status=result.get("execution_status", "pending"),
                execution_path=json.dumps(result.get("execution_path", [])),
                slack_message_ts=result.get("slack_message_ts") or None,
            )

            if result.get("execution_status") == "escalated" and result.get("decision", {}).get("requires_approval"):
                from datetime import timedelta
                from src.config import settings as _s
                action.hitl_expires_at = datetime.utcnow() + timedelta(minutes=_s.hitl_timeout_minutes)

            session.add(action)
            await session.commit()
            await session.refresh(action)
            action_id = action.id

            if result.get("execution_status") == "escalated":
                severity = result["analysis"]["severity"] if result.get("analysis") else "medium"
                summary = result["analysis"]["summary"] if result.get("analysis") else ""
                target_action = result["decision"]["target_action"]
                estimated_impact = result["decision"]["estimated_impact"]

                # Fan out to Slack
                try:
                    from src.services.slack_service import post_hitl_alert as _post_slack
                    real_ts, _ = await _post_slack(
                        action_id=action_id,
                        user_input=request.query,
                        severity=severity,
                        summary=summary,
                        target_action=target_action,
                        estimated_impact=estimated_impact,
                    )
                    action.slack_message_ts = real_ts
                    await session.commit()
                except Exception as _exc:
                    logger.warning("[Orchestrate] Slack HITL post failed: %s", _exc)

                # Fan out to Teams (non-blocking)
                try:
                    from src.services.teams_service import post_hitl_alert as _post_teams
                    await _post_teams(
                        action_id=action_id,
                        user_input=request.query,
                        severity=severity,
                        summary=summary,
                        target_action=target_action,
                        estimated_impact=estimated_impact,
                    )
                except Exception as _exc:
                    logger.warning("[Orchestrate] Teams HITL post failed: %s", _exc)

                await redis_service.publish(
                    AGENT_LOG_CHANNEL,
                    {
                        "node": "dispatch",
                        "message": f"HITL alert dispatched (action={action_id})",
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": request.user_id,
                    },
                )

            await write_audit_log(
                session,
                event_type="orchestration_executed",
                user_id=request.user_id,
                org_id=org_id,
                user_input=request.query,
                execution_path=result.get("execution_path"),
                severity=result["analysis"]["severity"] if result.get("analysis") else None,
                estimated_impact=result["decision"]["estimated_impact"] if result.get("decision") else None,
                payload={
                    "action_id": action_id,
                    "execution_status": result.get("execution_status"),
                },
            )

        return OrchestrateResponse(
            action_id=action_id,
            parsed_command=result.get("parsed_command"),
            analysis=result.get("analysis"),
            decision=result.get("decision"),
            execution_status=result.get("execution_status", "error"),
            slack_message_ts=result.get("slack_message_ts", ""),
            execution_path=result.get("execution_path", []),
            errors=result.get("errors", []),
            llm_mode=resolve_llm_provider(),
        )
    except Exception as exc:
        logger.error("[Orchestrate] Error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@agent_router.post("/hitl/approve")
async def approve_decision(
    body: HitlApprovalRequest,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> dict:
    if body.approval_choice not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="approval_choice must be approve or reject")

    query = select(AgentAction).where(AgentAction.slack_message_ts == body.decision_id)
    if not body.decision_id:
        query = select(AgentAction).order_by(AgentAction.created_at.desc()).limit(1)

    result = await session.execute(query)
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found for decision_id")

    if body.approval_choice == "approve":
        action.execution_status = "executing"
        await asyncio.sleep(0.05)
        action.execution_status = "completed"
    else:
        action.execution_status = "rejected"

    await write_audit_log(
        session,
        event_type=f"hitl_{body.approval_choice}",
        user_id=body.user_id,
        org_id=org_id,
        user_input=action.user_input,
        approval_choice=body.approval_choice,
        notes=body.notes,
        payload={"decision_id": body.decision_id, "action_id": action.id},
    )

    await redis_service.publish(
        AGENT_LOG_CHANNEL,
        {
            "node": "hitl",
            "message": f"Decision {body.approval_choice}d by {body.user_id}",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": body.user_id,
        },
    )

    if action.slack_message_ts:
        try:
            from src.services.slack_service import update_hitl_message
            target_action = "action"
            if action.decision:
                target_action = json.loads(action.decision).get("target_action", "action")
            await update_hitl_message(
                message_ts=action.slack_message_ts,
                choice=body.approval_choice,
                decided_by=body.user_id,
                target_action=target_action,
                notes=body.notes,
            )
        except Exception as _exc:
            logger.warning("[HITL approve] Slack update failed: %s", _exc)

    await session.commit()
    return {
        "success": True,
        "decision_id": body.decision_id,
        "action_id": action.id,
        "status": action.execution_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@sse_router.get("/metrics")
async def stream_metrics(request: Request) -> StreamingResponse:
    async def metrics_generator() -> AsyncGenerator[str, None]:
        regions = ["MY", "SG", "HK", "TW"]
        live_cache: dict[str, dict] = {}

        async def _traffic_listener() -> None:
            async for raw in redis_service.subscribe(TRAFFIC_CHANNEL):
                try:
                    sample = json.loads(raw) if isinstance(raw, str) else raw
                    payload = sample.get("payload", {})
                    region = payload.get("region")
                    if region and region in regions:
                        live_cache[region] = {
                            "type": "metrics_update",
                            "region": region,
                            "congestion": payload.get("congestion", 50),
                            "avg_delivery_time": payload.get("avg_delivery_time", 3.0),
                            "active_deliveries": payload.get("active_deliveries", 1000),
                            "active_incidents": payload.get("active_incidents", 0),
                            "last_updated": payload.get("capturedAt", datetime.utcnow().isoformat()),
                        }
                except Exception:
                    pass

        listener = asyncio.create_task(_traffic_listener())
        try:
            while True:
                if await request.is_disconnected():
                    break
                for region in regions:
                    metrics = live_cache.get(region) or _mock_regional_metrics(region)
                    yield f"data: {json.dumps(metrics)}\n\n"
                    await asyncio.sleep(0.35)
                await asyncio.sleep(1)
        finally:
            listener.cancel()

    return StreamingResponse(
        metrics_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@sse_router.get("/agent-log")
async def stream_agent_log(request: Request) -> StreamingResponse:
    async def log_generator() -> AsyncGenerator[str, None]:
        async for message in redis_service.subscribe(AGENT_LOG_CHANNEL):
            if await request.is_disconnected():
                break
            yield f"data: {message}\n\n"

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@audit_router.post("/log")
async def log_audit_event(
    body: AuditEventRequest,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> dict:
    entry = await write_audit_log(
        session,
        event_type=body.event_type,
        user_id=body.user_id,
        org_id=org_id,
        user_input=body.user_input,
        execution_path=body.execution_path,
        payload=body.payload,
    )
    return {
        "success": True,
        "id": entry.id,
        "event_type": body.event_type,
        "timestamp": body.timestamp or datetime.utcnow().isoformat(),
    }


@audit_router.get("/recent")
async def recent_audit_logs(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> dict:
    query = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 100))
    )
    result = await session.execute(query)
    logs = result.scalars().all()
    return {
        "items": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "user_id": log.user_id,
                "user_input": log.user_input,
                "approval_choice": log.approval_choice,
                "severity": log.severity,
                "estimated_impact": log.estimated_impact,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


@audit_router.get("/export")
async def export_audit_logs(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    event_type: str | None = None,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> StreamingResponse:
    """Export audit logs for compliance. Supports JSON and CSV.

    Query params:
      format    — json (default) | csv
      from      — ISO date lower bound, e.g. 2025-01-01
      to        — ISO date upper bound, e.g. 2025-12-31
      event_type — filter to a single event type
    """
    conditions = [AuditLog.org_id == org_id]
    if from_date:
        try:
            conditions.append(AuditLog.created_at >= datetime.fromisoformat(from_date))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'from' date: {from_date}")
    if to_date:
        try:
            conditions.append(AuditLog.created_at <= datetime.fromisoformat(to_date))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'to' date: {to_date}")
    if event_type:
        conditions.append(AuditLog.event_type == event_type)

    result = await session.execute(
        select(AuditLog).where(*conditions).order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()

    _FIELDS = [
        "id", "event_type", "user_id", "org_id", "user_input",
        "approval_choice", "notes", "severity", "estimated_impact",
        "execution_path", "payload", "created_at",
    ]

    if format == "csv":
        def _csv_stream() -> AsyncGenerator[str, None]:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore")
            writer.writeheader()
            yield buf.getvalue()
            for log in logs:
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore")
                writer.writerow({
                    "id": log.id,
                    "event_type": log.event_type,
                    "user_id": log.user_id or "",
                    "org_id": log.org_id,
                    "user_input": log.user_input or "",
                    "approval_choice": log.approval_choice or "",
                    "notes": log.notes or "",
                    "severity": log.severity or "",
                    "estimated_impact": log.estimated_impact or "",
                    "execution_path": log.execution_path or "",
                    "payload": log.payload or "",
                    "created_at": log.created_at.isoformat(),
                })
                yield buf.getvalue()

        async def _async_csv() -> AsyncGenerator[str, None]:
            for chunk in _csv_stream():
                yield chunk

        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        return StreamingResponse(
            _async_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="audit_{org_id}_{stamp}.csv"'},
        )

    # JSON streaming
    async def _json_stream() -> AsyncGenerator[str, None]:
        yield '{"items":['
        for i, log in enumerate(logs):
            row = {
                "id": log.id,
                "event_type": log.event_type,
                "user_id": log.user_id,
                "org_id": log.org_id,
                "user_input": log.user_input,
                "approval_choice": log.approval_choice,
                "notes": log.notes,
                "severity": log.severity,
                "estimated_impact": log.estimated_impact,
                "execution_path": log.execution_path,
                "payload": log.payload,
                "created_at": log.created_at.isoformat(),
            }
            yield ("" if i == 0 else ",") + json.dumps(row)
        yield "]}"

    return StreamingResponse(
        _json_stream(),
        media_type="application/json",
    )


def _mock_regional_metrics(region: str) -> dict:
    congestion = random.randint(30, 95)
    return {
        "type": "metrics_update",
        "region": region,
        "congestion": congestion,
        "delivery_delay": random.randint(10, 80),
        "avg_delivery_time": round(random.uniform(3, 6), 1),
        "active_deliveries": random.randint(500, 2000),
        "active_incidents": random.randint(0, 5 if congestion > 75 else 2),
        "last_updated": datetime.utcnow().isoformat(),
    }


# ── VidStega tamper-proof audit receipts ──────────────────────────────────────

class VidStegaCreateRequest(BaseModel):
    decision_id: str
    ai_reasoning: dict
    user_approval: str
    amount: float = 0.0


class VidStegaVerifyRequest(BaseModel):
    image_b64: str
    signature: str


@audit_router.post("/vidstega/create")
async def create_vidstega_receipt(body: VidStegaCreateRequest) -> dict:
    import base64
    from src.services.vidstega_audit import VidStegaAuditTrail

    trail = VidStegaAuditTrail(signing_secret=settings.vidstega_signing_secret)
    image_bytes, signature = trail.create_audit_record(
        decision_id=body.decision_id,
        ai_reasoning=body.ai_reasoning,
        user_approval=body.user_approval,
        amount=body.amount,
    )
    return {
        "decision_id": body.decision_id,
        "image_b64": base64.b64encode(image_bytes).decode(),
        "signature": signature,
    }


@audit_router.post("/vidstega/verify")
async def verify_vidstega_receipt(body: VidStegaVerifyRequest) -> dict:
    import base64
    from src.services.vidstega_audit import VidStegaAuditTrail

    trail = VidStegaAuditTrail(signing_secret=settings.vidstega_signing_secret)
    try:
        image_bytes = base64.b64decode(body.image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")
    return trail.verify_audit_record(image_bytes, body.signature)


from fastapi.responses import Response as FastAPIResponse


@audit_router.get("/receipt/{action_id}")
async def get_action_receipt(
    action_id: str,
    session: AsyncSession = Depends(get_session),
    org_id: str = Depends(get_org_id),
) -> FastAPIResponse:
    from src.services.vidstega_audit import VidStegaAuditTrail

    result = await session.execute(
        select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.org_id == org_id,
        )
    )
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    analysis = json.loads(action.analysis) if action.analysis else {}
    decision = json.loads(action.decision) if action.decision else {}
    ai_reasoning = {
        "user_input": action.user_input,
        "execution_path": json.loads(action.execution_path) if action.execution_path else [],
        "severity": analysis.get("severity", "unknown"),
        "summary": analysis.get("summary", ""),
        "target_action": decision.get("target_action", ""),
    }

    trail = VidStegaAuditTrail(signing_secret=settings.vidstega_signing_secret)
    image_bytes, signature = trail.create_audit_record(
        decision_id=action_id,
        ai_reasoning=ai_reasoning,
        user_approval=action.execution_status or "pending",
        amount=float(decision.get("estimated_impact", 0.0)),
    )
    return FastAPIResponse(
        content=image_bytes,
        media_type="image/png",
        headers={"X-VidStega-Signature": signature},
    )
