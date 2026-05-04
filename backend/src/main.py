"""
NexusFlow AI – FastAPI Application
Exposes all four platform services through a unified REST API.
"""
from __future__ import annotations

import os
from io import BytesIO
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from src.agent.nlp_router import parse_nl_command
from src.services.oddle_dispatcher import OddleAutonomousDispatcher, TrafficIncident
from src.services.vidstega_audit import VidStegaAuditTrail
from src.services.model_router import IntelligentModelRouter

app = FastAPI(
    title="NexusFlow AI",
    description="Multi-Agent Autonomous Operations Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
_dispatcher = OddleAutonomousDispatcher()
_audit = VidStegaAuditTrail()
_router = IntelligentModelRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class NLCommandRequest(BaseModel):
    query: str


class IncidentRequest(BaseModel):
    incident_id: str
    location: str
    region: str
    description: str


class AuditCreateRequest(BaseModel):
    decision_id: str
    ai_reasoning: dict[str, Any]
    user_approval: str
    amount: float


class AuditVerifyRequest(BaseModel):
    image_b64: str
    signature: str


class ModelRouteRequest(BaseModel):
    query: str
    context: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes – Week 1-2: Control Tower NL Interface
# ---------------------------------------------------------------------------

@app.post("/api/agent/parse-command")
async def parse_command(req: NLCommandRequest) -> dict[str, Any]:
    """Convert a natural-language logistics command to a structured query."""
    try:
        parsed = await parse_nl_command(req.query)
        return {"query": parsed, "raw_input": req.query}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Routes – Weeks 3-4: Oddle Autonomous Dispatcher
# ---------------------------------------------------------------------------

@app.post("/api/dispatch/analyse")
async def analyse_incident(req: IncidentRequest) -> dict[str, Any]:
    """Detect, analyse, and propose a dispatch decision for a traffic incident."""
    incident = TrafficIncident(
        incident_id=req.incident_id,
        location=req.location,
        region=req.region,
        description=req.description,
    )
    try:
        result = await _dispatcher.detect_and_dispatch(incident)
        return {
            "incident_id": result.incident.incident_id,
            "severity": result.severity,
            "impact": result.impact,
            "alternatives": result.alternatives,
            "decision": result.decision,
            "slack_payload": result.slack_payload,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Routes – Weeks 5-6: VidStega Audit Trail
# ---------------------------------------------------------------------------

@app.post("/api/audit/create")
async def create_audit(req: AuditCreateRequest) -> dict[str, Any]:
    """Embed AI reasoning into a receipt image and return it as base64 + signature."""
    import base64

    try:
        image_bytes, signature = _audit.create_audit_record(
            decision_id=req.decision_id,
            ai_reasoning=req.ai_reasoning,
            user_approval=req.user_approval,
            amount=req.amount,
        )
        return {
            "image_b64": base64.b64encode(image_bytes).decode(),
            "signature": signature,
            "decision_id": req.decision_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/audit/verify")
async def verify_audit(req: AuditVerifyRequest) -> dict[str, Any]:
    """Verify and extract an audit record from a base64-encoded receipt image."""
    import base64

    try:
        image_bytes = base64.b64decode(req.image_b64)
        result = _audit.verify_audit_record(image_bytes, req.signature)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Routes – Weeks 7-8: Intelligent Model Router
# ---------------------------------------------------------------------------

@app.post("/api/model/route")
async def route_query(req: ModelRouteRequest) -> dict[str, Any]:
    """Route a query to the cheapest capable model and return the response."""
    try:
        result = await _router.route_and_execute(req.query, req.context)
        return {
            "query": result.query,
            "complexity": result.complexity,
            "model_used": result.model_used,
            "response": result.response_text,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
            "timestamp": result.timestamp,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/model/stats")
async def model_stats() -> dict[str, Any]:
    """Return cumulative routing statistics and cost-savings summary."""
    s = _router.stats
    return {
        "total_queries": s.total_queries,
        "breakdown": {
            "haiku": s.haiku_count,
            "sonnet": s.sonnet_count,
            "opus": s.opus_count,
        },
        "total_cost_usd": round(s.total_cost_usd, 4),
        "hypothetical_all_opus_usd": round(s.hypothetical_all_opus_usd, 4),
        "savings_usd": round(s.savings_usd, 4),
        "savings_pct": round(s.savings_pct, 2),
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexusflow-ai"}
