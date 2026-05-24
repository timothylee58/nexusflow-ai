"""
LangGraph orchestration — 5-node pipeline with heuristic fallback when no API key.
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.services.llm_provider import complete_text, is_llm_enabled, resolve_llm_provider
from src.services.redis_service import AGENT_LOG_CHANNEL, redis_service

logger = logging.getLogger(__name__)


class ParsedCommand(TypedDict):
    query_type: str
    region: str
    metric: str
    time_frame: str
    confidence: float
    raw_input: str


class MetricsData(TypedDict):
    region: str
    metric: str
    current_value: float
    threshold: float
    trend: str
    anomaly_detected: bool
    last_updated: str


class AnalysisResult(TypedDict):
    summary: str
    severity: str
    root_causes: list[str]
    confidence: float
    model: str
    tokens_used: int


class Decision(TypedDict):
    decision_type: str
    target_action: str
    estimated_impact: float
    requires_approval: bool
    reasoning: str


class DispatcherState(TypedDict, total=False):
    user_input: str
    timestamp: str
    user_id: str
    parsed_command: ParsedCommand | None
    metrics_data: MetricsData | None
    analysis: AnalysisResult | None
    decision: Decision | None
    execution_status: str
    slack_message_ts: str
    audit_log_id: str
    errors: list[str]
    execution_path: list[str]


async def _publish_node_event(node: str, message: str, user_id: str) -> None:
    await redis_service.publish(
        AGENT_LOG_CHANNEL,
        {
            "node": node,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
        },
    )


PARSE_SYSTEM_PROMPT = (
    "Convert logistics NL queries to JSON only. "
    "Fields: query_type, region (MY|SG|HK|TW), metric, time_frame, confidence."
)


def _heuristic_parse(user_input: str) -> ParsedCommand:
    text = user_input.lower()
    region = "MY"
    for code, keywords in {
        "MY": ("kl", "malaysia", "my", "kuala"),
        "SG": ("singapore", "sg"),
        "HK": ("hong kong", "hk"),
        "TW": ("taiwan", "tw"),
    }.items():
        if any(k in text for k in keywords):
            region = code
            break

    query_type = "status"
    if "bottleneck" in text or "congestion" in text:
        query_type = "bottleneck"
    elif "forecast" in text or "demand" in text:
        query_type = "forecast"
    elif "fraud" in text:
        query_type = "fraud_check"

    metric = "delivery_time"
    if "cost" in text:
        metric = "cost"
    elif "congestion" in text:
        metric = "congestion"

    return ParsedCommand(
        query_type=query_type,
        region=region,
        metric=metric,
        time_frame="realtime",
        confidence=0.75,
        raw_input=user_input,
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(match.group())


async def parse_node(state: DispatcherState) -> dict:
    user_input = state["user_input"]
    user_id = state.get("user_id", "anonymous")
    logger.info("[Parser] Processing: %s", user_input)
    await _publish_node_event("parse", f"Parsing: {user_input[:80]}", user_id)

    errors = list(state.get("errors") or [])
    execution_path = list(state.get("execution_path") or [])

    if is_llm_enabled():
        try:
            completion = await complete_text(
                system=PARSE_SYSTEM_PROMPT,
                user=user_input,
                tier="parse",
            )
            parsed = _extract_json(completion.text if completion else "")
            parsed_command = ParsedCommand(
                query_type=parsed.get("query_type", "status"),
                region=parsed.get("region", "MY"),
                metric=parsed.get("metric", "delivery_time"),
                time_frame=parsed.get("time_frame", "realtime"),
                confidence=float(parsed.get("confidence", 0.8)),
                raw_input=user_input,
            )
        except (json.JSONDecodeError, IndexError, KeyError, TypeError, RuntimeError):
            errors.append(
                f"Failed to parse via {resolve_llm_provider()}; using heuristic parser"
            )
            parsed_command = _heuristic_parse(user_input)
    else:
        parsed_command = _heuristic_parse(user_input)

    execution_path.append("parse")
    return {"parsed_command": parsed_command, "errors": errors, "execution_path": execution_path}


async def fetch_node(state: DispatcherState) -> dict:
    cmd = state["parsed_command"]
    user_id = state.get("user_id", "anonymous")
    if not cmd:
        return {"errors": (state.get("errors") or []) + ["Missing parsed command"]}

    logger.info("[Fetcher] Fetching %s for %s", cmd["metric"], cmd["region"])
    await _publish_node_event("fetch", f"Fetching {cmd['metric']} ({cmd['region']})", user_id)

    current_value = round(random.uniform(60, 95), 1)
    metrics_data = MetricsData(
        region=cmd["region"],
        metric=cmd["metric"],
        current_value=current_value,
        threshold=80.0,
        trend="degrading" if current_value > 75 else "stable",
        anomaly_detected=current_value > 80,
        last_updated=datetime.utcnow().isoformat(),
    )
    execution_path = list(state.get("execution_path") or [])
    execution_path.append("fetch")
    return {"metrics_data": metrics_data, "execution_path": execution_path}


async def analyze_node(state: DispatcherState) -> dict:
    metrics = state.get("metrics_data")
    user_id = state.get("user_id", "anonymous")
    errors = list(state.get("errors") or [])
    execution_path = list(state.get("execution_path") or [])

    if not metrics:
        errors.append("Missing metrics for analysis")
        execution_path.append("analyze")
        return {"errors": errors, "execution_path": execution_path}

    await _publish_node_event("analyze", f"Analyzing {metrics['metric']} anomaly", user_id)

    if is_llm_enabled():
        prompt = f"""Analyze logistics metrics and respond JSON only:
Region: {metrics['region']}
Metric: {metrics['metric']}
Current: {metrics['current_value']}%
Threshold: {metrics['threshold']}%
Trend: {metrics['trend']}
Anomaly: {metrics['anomaly_detected']}
Keys: summary, severity (critical|high|medium|low), root_causes (array), confidence (0-1)"""
        try:
            completion = await complete_text(system="", user=prompt, tier="analyze")
            analysis_raw = _extract_json(completion.text if completion else "")
            analysis = AnalysisResult(
                summary=analysis_raw.get("summary", ""),
                severity=analysis_raw.get("severity", "medium"),
                root_causes=analysis_raw.get("root_causes", []),
                confidence=float(analysis_raw.get("confidence", 0.7)),
                model=completion.model if completion else resolve_llm_provider(),
                tokens_used=completion.tokens_used if completion else 0,
            )
        except (json.JSONDecodeError, IndexError, KeyError, TypeError, RuntimeError):
            errors.append(
                f"Analysis failed via {resolve_llm_provider()}; using heuristic analysis"
            )
            analysis = _heuristic_analysis(metrics)
    else:
        analysis = _heuristic_analysis(metrics)

    execution_path.append("analyze")
    return {"analysis": analysis, "errors": errors, "execution_path": execution_path}


def _heuristic_analysis(metrics: MetricsData) -> AnalysisResult:
    value = metrics["current_value"]
    if value >= 90:
        severity = "critical"
    elif value >= 80:
        severity = "high"
    elif value >= 70:
        severity = "medium"
    else:
        severity = "low"

    return AnalysisResult(
        summary=(
            f"{metrics['region']} {metrics['metric']} at {value}% "
            f"({'above' if value > metrics['threshold'] else 'within'} threshold)."
        ),
        severity=severity,
        root_causes=["Peak-hour volume", "Route saturation"],
        confidence=0.72,
        model="heuristic-v1",
        tokens_used=0,
    )


async def decide_node(state: DispatcherState) -> dict:
    analysis = state.get("analysis")
    user_id = state.get("user_id", "anonymous")
    execution_path = list(state.get("execution_path") or [])

    if not analysis:
        execution_path.append("decide")
        return {"execution_path": execution_path, "errors": (state.get("errors") or []) + ["Missing analysis"]}

    await _publish_node_event("decide", f"Severity: {analysis['severity']}", user_id)

    severity = analysis["severity"]
    if severity == "critical":
        decision_type, target_action, requires_approval = "auto_dispatch", "reroute", True
    elif severity == "high":
        decision_type, target_action, requires_approval = "alert_hitl", "scale_resources", True
    elif severity == "medium":
        decision_type, target_action, requires_approval = "alert_hitl", "monitor", False
    else:
        decision_type, target_action, requires_approval = "no_action", "none", False

    impact_map = {"critical": 1200.0, "high": 600.0, "medium": 200.0, "low": 50.0}
    decision = Decision(
        decision_type=decision_type,
        target_action=target_action,
        estimated_impact=impact_map.get(severity, 100.0),
        requires_approval=requires_approval,
        reasoning=f"Severity {severity}: {analysis['summary']}",
    )
    execution_path.append("decide")
    return {"decision": decision, "execution_path": execution_path}


async def dispatch_node(state: DispatcherState) -> dict:
    from src.services.slack_service import post_hitl_alert

    decision = state.get("decision")
    analysis = state.get("analysis")
    user_id = state.get("user_id", "anonymous")
    execution_path = list(state.get("execution_path") or [])

    if not decision:
        execution_path.append("dispatch")
        return {
            "execution_status": "error",
            "execution_path": execution_path,
            "errors": (state.get("errors") or []) + ["Missing decision"],
        }

    await _publish_node_event("dispatch", decision["target_action"], user_id)

    slack_message_ts = ""
    execution_status = "completed"

    if decision["requires_approval"]:
        execution_status = "escalated"
        slack_message_ts = await post_hitl_alert(
            user_input=state.get("user_input", ""),
            severity=analysis["severity"] if analysis else "medium",
            summary=analysis["summary"] if analysis else "",
            target_action=decision["target_action"],
            estimated_impact=decision["estimated_impact"],
        )
        await _publish_node_event("dispatch", "Escalated to HITL / Slack", user_id)
    else:
        logger.info("[Dispatcher] Auto-executed: %s", decision["target_action"])
        await _publish_node_event("dispatch", f"Auto-executed {decision['target_action']}", user_id)

    execution_path.append("dispatch")
    return {
        "execution_status": execution_status,
        "slack_message_ts": slack_message_ts,
        "execution_path": execution_path,
    }


def create_orchestration_graph():
    workflow = StateGraph(DispatcherState)
    workflow.add_node("parse", parse_node)
    workflow.add_node("fetch", fetch_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("dispatch", dispatch_node)
    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "fetch")
    workflow.add_edge("fetch", "analyze")
    workflow.add_edge("analyze", "decide")
    workflow.add_edge("decide", "dispatch")
    workflow.add_edge("dispatch", END)
    return workflow.compile()


async def execute_orchestration(user_input: str, user_id: str = "user_default") -> DispatcherState:
    state: DispatcherState = {
        "user_input": user_input,
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "parsed_command": None,
        "metrics_data": None,
        "analysis": None,
        "decision": None,
        "execution_status": "pending",
        "slack_message_ts": "",
        "audit_log_id": "",
        "errors": [],
        "execution_path": [],
    }
    graph = create_orchestration_graph()
    result = await graph.ainvoke(state)
    logger.info("[Orchestration] Complete. Path: %s", result.get("execution_path"))
    return result
