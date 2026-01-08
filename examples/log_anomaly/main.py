"""Log Anomaly Detection Example - Multi-Service Log Aggregation.

This example demonstrates a log aggregation and anomaly detection system that:
1. Receives logs from multiple services via HTTP
2. Filters and deduplicates log entries
3. Detects anomalies using threshold triggers
4. Correlates errors across services using LLM
5. Generates alerts for root cause analysis

Run with:
    python -m examples.log_anomaly.main

Or start the API server:
    uvicorn reflex.api.app:app --reload
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from reflex import (
    AgentContext,
    BaseEvent,
    EventRegistry,
    ReflexDeps,
    SimpleAgent,
    dedupe_filter,
    error_threshold_trigger,
    get_registry,
    immediate_trigger,
    periodic_summary_trigger,
    source_filter,
    trigger,
    type_filter,
)

if TYPE_CHECKING:
    from datetime import datetime


# =============================================================================
# Enums and Models
# =============================================================================


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class AnomalyType(str, Enum):
    """Types of detected anomalies."""

    ERROR_SPIKE = "error_spike"
    LATENCY_SPIKE = "latency_spike"
    MEMORY_LEAK = "memory_leak"
    CONNECTION_FAILURE = "connection_failure"
    CASCADE_FAILURE = "cascade_failure"
    UNKNOWN = "unknown"


class CorrelationResult(BaseModel):
    """LLM root cause analysis output."""

    anomaly_type: AnomalyType
    root_cause: str
    affected_services: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: str
    severity: str  # "low", "medium", "high", "critical"


# =============================================================================
# Custom Event Types
# =============================================================================


@EventRegistry.register
class LogEvent(BaseEvent):
    """Log entry from a service."""

    type: Literal["log.entry"] = "log.entry"
    service: str
    environment: str  # "production", "staging", "development"
    level: str  # debug, info, warn, error, fatal
    message: str
    context: dict = Field(default_factory=dict)  # Additional structured data
    trace_id: str | None = None
    span_id: str | None = None


@EventRegistry.register
class ErrorLogEvent(BaseEvent):
    """Error log specifically for threshold tracking."""

    type: Literal["log.error"] = "log.error"
    service: str
    environment: str
    error_type: str
    message: str
    stack_trace: str | None = None
    context: dict = Field(default_factory=dict)


@EventRegistry.register
class AnomalyDetectedEvent(BaseEvent):
    """Anomaly detected in log patterns."""

    type: Literal["log.anomaly"] = "log.anomaly"
    anomaly_type: str
    services: list[str]
    error_count: int
    window_seconds: int
    sample_messages: list[str]


@EventRegistry.register
class RootCauseAnalysisEvent(BaseEvent):
    """Root cause analysis result."""

    type: Literal["log.root_cause"] = "log.root_cause"
    anomaly_id: str
    root_cause: str
    affected_services: list[str]
    recommended_action: str
    severity: str
    confidence: float


@EventRegistry.register
class LogSummaryEvent(BaseEvent):
    """Periodic log summary."""

    type: Literal["log.summary"] = "log.summary"
    period_start: datetime
    period_end: datetime
    total_logs: int
    by_level: dict[str, int]
    by_service: dict[str, int]
    error_rate: float


# =============================================================================
# Service Health Tracking (simulated)
# =============================================================================

SERVICE_ERROR_COUNTS: dict[str, int] = {}
SERVICE_LAST_ERRORS: dict[str, list[str]] = {}


def record_error(service: str, message: str) -> int:
    """Record error and return current count."""
    SERVICE_ERROR_COUNTS[service] = SERVICE_ERROR_COUNTS.get(service, 0) + 1
    if service not in SERVICE_LAST_ERRORS:
        SERVICE_LAST_ERRORS[service] = []
    SERVICE_LAST_ERRORS[service].append(message)
    # Keep only last 10 errors
    SERVICE_LAST_ERRORS[service] = SERVICE_LAST_ERRORS[service][-10:]
    return SERVICE_ERROR_COUNTS[service]


def get_service_errors(service: str) -> list[str]:
    """Get recent errors for a service."""
    return SERVICE_LAST_ERRORS.get(service, [])


# =============================================================================
# AI-Powered Root Cause Analyzer
# =============================================================================

root_cause_analyzer = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=ReflexDeps,
    result_type=CorrelationResult,
    system_prompt="""You are a DevOps engineer analyzing log anomalies.

Given error logs from multiple services, determine:
1. The type of anomaly (error_spike, latency_spike, memory_leak, connection_failure,
   cascade_failure, unknown)
2. The most likely root cause
3. Which services are affected
4. Recommended immediate action
5. Severity level

Common patterns:
- Database connection errors across services → DB overload or network issue
- Timeout errors spreading service to service → Cascade failure
- Memory errors increasing over time → Memory leak
- Sudden spike in all error types → Deployment issue or infrastructure problem
- Single service errors only → Service-specific bug

Be specific about root cause. Recommend actionable steps.""",
)


@root_cause_analyzer.tool
async def get_service_error_history(ctx: RunContext[ReflexDeps], service: str) -> str:
    """Get recent error history for a service."""
    errors = get_service_errors(service)
    if not errors:
        return f"Service {service}: No recent errors recorded."
    return f"Service {service} recent errors:\n" + "\n".join(f"  - {e}" for e in errors)


@root_cause_analyzer.tool
async def get_all_service_status(ctx: RunContext[ReflexDeps]) -> str:
    """Get error counts for all services."""
    if not SERVICE_ERROR_COUNTS:
        return "No errors recorded for any service."
    lines = [f"  {svc}: {count} errors" for svc, count in SERVICE_ERROR_COUNTS.items()]
    return "Service error counts:\n" + "\n".join(lines)


# =============================================================================
# Log Processing Agent
# =============================================================================


async def process_log(ctx: AgentContext) -> dict:
    """Process incoming log entries."""
    event: LogEvent = ctx.event

    # Track errors
    if event.level in ("error", "fatal"):
        record_error(event.service, event.message)

        # Create specific error event for threshold tracking
        error_event = ctx.derive_event(
            ErrorLogEvent,
            service=event.service,
            environment=event.environment,
            error_type=event.context.get("error_type", "unknown"),
            message=event.message,
            stack_trace=event.context.get("stack_trace"),
            context=event.context,
        )
        await ctx.publish(error_event)

    return {
        "processed": True,
        "service": event.service,
        "level": event.level,
    }


log_processor = SimpleAgent(process_log)


# =============================================================================
# Anomaly Detection Agent
# =============================================================================


async def detect_anomaly(ctx: AgentContext) -> dict:
    """Detect anomalies when error threshold is reached."""

    # Collect recent errors from this and related services
    services_with_errors = list(SERVICE_ERROR_COUNTS.keys())
    sample_messages = []
    for svc in services_with_errors[:5]:  # Top 5 services
        sample_messages.extend(get_service_errors(svc)[-2:])

    # Create anomaly event
    anomaly = ctx.derive_event(
        AnomalyDetectedEvent,
        anomaly_type="error_spike",
        services=services_with_errors,
        error_count=sum(SERVICE_ERROR_COUNTS.values()),
        window_seconds=60,
        sample_messages=sample_messages[:10],
    )
    await ctx.publish(anomaly)

    print("\n⚠️  [ANOMALY] Error spike detected!")
    print(f"   Services affected: {', '.join(services_with_errors)}")
    print(f"   Total errors: {sum(SERVICE_ERROR_COUNTS.values())}")

    return {
        "anomaly_detected": True,
        "anomaly_id": anomaly.id,
        "services": services_with_errors,
    }


anomaly_detector = SimpleAgent(detect_anomaly)


# =============================================================================
# Root Cause Analysis Agent
# =============================================================================


async def analyze_root_cause(ctx: AgentContext) -> dict:
    """Analyze anomaly and determine root cause using LLM."""
    event: AnomalyDetectedEvent = ctx.event

    # Build context for LLM
    context = f"""
Anomaly Type: {event.anomaly_type}
Affected Services: {", ".join(event.services)}
Error Count: {event.error_count} in {event.window_seconds}s

Sample Error Messages:
{chr(10).join(f"  - {msg}" for msg in event.sample_messages)}
"""

    try:
        result = await root_cause_analyzer.run(
            f"Analyze this anomaly:\n{context}",
            deps=ctx.deps,
        )
        analysis = result.data
    except Exception as e:
        analysis = CorrelationResult(
            anomaly_type=AnomalyType.UNKNOWN,
            root_cause=f"Analysis failed: {e}",
            affected_services=event.services,
            confidence=0.0,
            recommended_action="Manual investigation required",
            severity="high",
        )

    # Publish root cause analysis
    rca = ctx.derive_event(
        RootCauseAnalysisEvent,
        anomaly_id=event.id,
        root_cause=analysis.root_cause,
        affected_services=analysis.affected_services,
        recommended_action=analysis.recommended_action,
        severity=analysis.severity,
        confidence=analysis.confidence,
    )
    await ctx.publish(rca)

    print("\n🔍 [ROOT CAUSE ANALYSIS]")
    print(f"   Anomaly Type: {analysis.anomaly_type.value}")
    print(f"   Root Cause: {analysis.root_cause}")
    print(f"   Severity: {analysis.severity.upper()}")
    print(f"   Confidence: {analysis.confidence:.0%}")
    print(f"   Action: {analysis.recommended_action}")

    return {
        "analyzed": True,
        "root_cause": analysis.root_cause,
        "severity": analysis.severity,
    }


rca_agent = SimpleAgent(analyze_root_cause)


# =============================================================================
# Log Summary Agent
# =============================================================================


async def generate_summary(ctx: AgentContext) -> dict:
    """Generate periodic log summary."""
    print("\n📊 [LOG SUMMARY]")
    print(f"   Services with errors: {len(SERVICE_ERROR_COUNTS)}")

    for service, count in sorted(SERVICE_ERROR_COUNTS.items(), key=lambda x: -x[1]):
        print(f"     • {service}: {count} errors")

    total_errors = sum(SERVICE_ERROR_COUNTS.values())
    print(f"   Total errors tracked: {total_errors}")

    return {"summary_generated": True, "total_errors": total_errors}


summary_agent = SimpleAgent(generate_summary)


# =============================================================================
# Alert Handler
# =============================================================================


async def handle_root_cause_alert(ctx: AgentContext) -> dict:
    """Handle root cause alerts - send notifications."""
    event: RootCauseAnalysisEvent = ctx.event

    print("\n🚨 [ALERT] Root Cause Identified")
    print(f"   Severity: {event.severity.upper()}")
    print(f"   Services: {', '.join(event.affected_services)}")
    print(f"   Root Cause: {event.root_cause}")
    print(f"   Action: {event.recommended_action}")

    # In production: send to PagerDuty, Slack, etc.

    return {"alerted": True, "severity": event.severity}


alert_agent = SimpleAgent(handle_root_cause_alert)


# =============================================================================
# Trigger Registration
# =============================================================================


# Deduplicate identical log entries within 5 seconds
log_dedupe = dedupe_filter(
    key_func=lambda e: f"{e.service}:{e.level}:{e.message[:100]}",
    window_seconds=5,
)


@trigger(
    name="log-processor",
    filter=type_filter("log.entry") & source_filter(r".*-prod.*") & log_dedupe,
    trigger_func=immediate_trigger(),
    agent=log_processor,
    priority=20,
    scope_key=lambda e: f"service:{e.service}",
)
def log_processing_trigger():
    """Process production logs with deduplication."""
    pass


@trigger(
    name="anomaly-detector",
    filter=type_filter("log.error"),
    trigger_func=error_threshold_trigger(
        threshold=5,
        window_seconds=60,
        error_types=["log.error"],
    ),
    agent=anomaly_detector,
    priority=15,
    scope_key=lambda e: f"env:{e.environment}",
)
def anomaly_detection_trigger():
    """Detect anomalies after 5 errors in 60 seconds."""
    pass


@trigger(
    name="root-cause-analyzer",
    filter=type_filter("log.anomaly"),
    trigger_func=immediate_trigger(),
    agent=rca_agent,
    priority=10,
)
def rca_trigger():
    """Analyze anomalies for root cause."""
    pass


@trigger(
    name="rca-alerter",
    filter=type_filter("log.root_cause"),
    trigger_func=immediate_trigger(),
    agent=alert_agent,
    priority=5,
)
def alert_trigger():
    """Send alerts for root cause findings."""
    pass


@trigger(
    name="log-summary",
    filter=type_filter("log.entry"),
    trigger_func=periodic_summary_trigger(
        event_count=50,
        max_interval_seconds=300,  # Every 5 minutes or 50 logs
    ),
    agent=summary_agent,
    priority=1,
)
def summary_trigger():
    """Generate periodic log summaries."""
    pass


# =============================================================================
# Demo Runner
# =============================================================================


async def demo():
    """Run an interactive demonstration."""
    print("=" * 60)
    print("📊 Log Anomaly Detection Example")
    print("=" * 60)

    # Show registered components
    registry = get_registry()
    print(f"\nRegistered triggers: {len(registry.triggers)}")
    for t in registry.triggers:
        print(f"  • {t.name} (priority: {t.priority})")

    print("\nRegistered event types:")
    for name in EventRegistry.type_names():
        if "log" in name:
            print(f"  • {name}")

    # Simulate log flow
    print("\n" + "-" * 60)
    print("Simulated Log Flow:")
    print("-" * 60)

    sample_logs = [
        ("api-gateway-prod", "production", "info", "Request received: GET /api/users"),
        ("auth-service-prod", "production", "info", "Token validated for user_123"),
        ("user-service-prod", "production", "error", "Database connection timeout"),
        ("api-gateway-prod", "production", "error", "Upstream service unavailable"),
        ("auth-service-prod", "production", "error", "Redis connection refused"),
        ("user-service-prod", "production", "error", "Query timeout after 30s"),
        ("payment-service-prod", "production", "error", "Transaction failed: DB locked"),
    ]

    for service, env, level, message in sample_logs:
        emoji = "🔴" if level == "error" else "🟢" if level == "info" else "🟡"
        print(f"\n{emoji} [{service}] {level.upper()}: {message[:50]}...")
        event = LogEvent(
            source=f"fluentd:{service}",
            service=service,
            environment=env,
            level=level,
            message=message,
        )
        print(f"   Event ID: {event.id}")

    print("\n" + "=" * 60)
    print("Event Flow:")
    print("  1. LogEvent received from services")
    print("  2. Deduplicated (5s window)")
    print("  3. Errors create ErrorLogEvent")
    print("  4. 5 errors in 60s → AnomalyDetectedEvent")
    print("  5. LLM analyzes → RootCauseAnalysisEvent")
    print("  6. Alert sent to ops team")
    print()
    print("To run the full system:")
    print("  1. Start PostgreSQL: docker-compose up -d")
    print("  2. Run migrations: alembic upgrade head")
    print("  3. Start API: uvicorn reflex.api.app:app --reload")
    print("  4. Send logs via HTTP POST /events")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
