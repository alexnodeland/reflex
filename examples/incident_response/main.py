"""Incident Response Example - Automated Incident Management.

This example demonstrates a PagerDuty-like incident response system that:
1. Receives alerts from monitoring systems
2. Deduplicates and correlates related alerts
3. Creates incidents with severity classification
4. Escalates through on-call chain with timeouts
5. Suggests runbooks and auto-remediation
6. Tracks resolution and triggers postmortems

Run with:
    python -m examples.incident_response.main

Or start the API server:
    uvicorn reflex.api.app:app --reload
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from reflex import (
    AgentContext,
    BaseEvent,
    EventRegistry,
    ReflexDeps,
    SimpleAgent,
    dedupe_filter,
    get_registry,
    immediate_trigger,
    trigger,
    type_filter,
)

# =============================================================================
# Enums and Models
# =============================================================================


class Severity(str, Enum):
    """Incident severity levels."""

    SEV1 = "sev1"  # Critical - customer impact, all hands
    SEV2 = "sev2"  # High - significant impact, immediate response
    SEV3 = "sev3"  # Medium - limited impact, business hours
    SEV4 = "sev4"  # Low - minor issue, best effort


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


class EscalationLevel(str, Enum):
    """Escalation chain levels."""

    PRIMARY = "primary"  # Primary on-call
    SECONDARY = "secondary"  # Secondary on-call
    MANAGER = "manager"  # Engineering manager
    EXECUTIVE = "executive"  # VP/C-level


class TriageResult(BaseModel):
    """LLM triage analysis output."""

    severity: Severity
    category: str  # "infrastructure", "application", "security", "data"
    affected_services: list[str]
    likely_cause: str
    suggested_runbook: str | None
    auto_remediation_possible: bool
    confidence: float = Field(ge=0.0, le=1.0)


# =============================================================================
# Custom Event Types
# =============================================================================


@EventRegistry.register
class AlertEvent(BaseEvent):
    """Alert from monitoring system."""

    type: Literal["alert.fired"] = "alert.fired"
    alert_id: str
    alert_name: str
    service: str
    severity: str
    message: str
    labels: dict = Field(default_factory=dict)  # Prometheus-style labels
    annotations: dict = Field(default_factory=dict)


@EventRegistry.register
class IncidentCreatedEvent(BaseEvent):
    """New incident created."""

    type: Literal["incident.created"] = "incident.created"
    incident_id: str
    title: str
    severity: str
    status: str
    services: list[str]
    alert_ids: list[str]
    triage_summary: str


@EventRegistry.register
class IncidentUpdatedEvent(BaseEvent):
    """Incident status updated."""

    type: Literal["incident.updated"] = "incident.updated"
    incident_id: str
    previous_status: str
    new_status: str
    update_message: str
    updated_by: str  # user_id or "system"


@EventRegistry.register
class EscalationEvent(BaseEvent):
    """Escalation to next on-call level."""

    type: Literal["incident.escalation"] = "incident.escalation"
    incident_id: str
    escalation_level: str
    reason: str
    target_user_id: str
    notification_channels: list[str]  # ["sms", "phone", "slack"]


@EventRegistry.register
class AcknowledgmentEvent(BaseEvent):
    """Incident acknowledged by responder."""

    type: Literal["incident.acknowledged"] = "incident.acknowledged"
    incident_id: str
    acknowledged_by: str
    response_time_seconds: int


@EventRegistry.register
class RunbookSuggestedEvent(BaseEvent):
    """Runbook suggested for incident."""

    type: Literal["incident.runbook_suggested"] = "incident.runbook_suggested"
    incident_id: str
    runbook_id: str
    runbook_title: str
    match_confidence: float
    auto_execute: bool


@EventRegistry.register
class IncidentResolvedEvent(BaseEvent):
    """Incident resolved."""

    type: Literal["incident.resolved"] = "incident.resolved"
    incident_id: str
    resolution_summary: str
    resolved_by: str
    time_to_resolve_minutes: int
    root_cause: str | None


@EventRegistry.register
class PostmortemRequestedEvent(BaseEvent):
    """Postmortem requested for incident."""

    type: Literal["incident.postmortem_requested"] = "incident.postmortem_requested"
    incident_id: str
    severity: str
    services: list[str]
    timeline_events: list[str]
    assignee: str


# =============================================================================
# On-Call Schedule (simulated)
# =============================================================================

ON_CALL_SCHEDULE = {
    EscalationLevel.PRIMARY: {
        "user_id": "oncall_primary",
        "name": "Alice Engineer",
        "channels": ["slack", "sms"],
    },
    EscalationLevel.SECONDARY: {
        "user_id": "oncall_secondary",
        "name": "Bob Engineer",
        "channels": ["slack", "sms", "phone"],
    },
    EscalationLevel.MANAGER: {
        "user_id": "eng_manager",
        "name": "Carol Manager",
        "channels": ["slack", "phone"],
    },
    EscalationLevel.EXECUTIVE: {
        "user_id": "vp_eng",
        "name": "Dave VP",
        "channels": ["phone"],
    },
}

# Runbook database (simulated)
RUNBOOKS = {
    "database_connection": {
        "id": "rb_001",
        "title": "Database Connection Issues",
        "steps": ["Check DB health", "Verify connection pool", "Restart if needed"],
        "auto_executable": False,
    },
    "high_cpu": {
        "id": "rb_002",
        "title": "High CPU Usage",
        "steps": ["Identify hot process", "Scale horizontally", "Investigate code"],
        "auto_executable": True,
    },
    "memory_leak": {
        "id": "rb_003",
        "title": "Memory Leak Response",
        "steps": ["Capture heap dump", "Rolling restart", "Analyze dump"],
        "auto_executable": True,
    },
    "ssl_certificate": {
        "id": "rb_004",
        "title": "SSL Certificate Expiry",
        "steps": ["Renew certificate", "Deploy to servers", "Verify"],
        "auto_executable": True,
    },
}

# Incident tracking (simulated)
ACTIVE_INCIDENTS: dict[str, dict] = {}
INCIDENT_COUNTER = 0


def create_incident_id() -> str:
    """Generate unique incident ID."""
    global INCIDENT_COUNTER
    INCIDENT_COUNTER += 1
    return f"INC-{INCIDENT_COUNTER:05d}"


def get_escalation_target(level: EscalationLevel) -> dict:
    """Get on-call person for escalation level."""
    return ON_CALL_SCHEDULE.get(level, ON_CALL_SCHEDULE[EscalationLevel.PRIMARY])


# =============================================================================
# AI-Powered Incident Triage
# =============================================================================

triage_agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=ReflexDeps,
    result_type=TriageResult,
    system_prompt="""You are an incident response coordinator analyzing alerts.

Triage incoming alerts to determine:
1. Severity (sev1-sev4)
2. Category (infrastructure, application, security, data)
3. Affected services
4. Likely root cause
5. Relevant runbook
6. Whether auto-remediation is possible

Severity guidelines:
- SEV1: Complete outage, data loss risk, security breach
- SEV2: Partial outage, significant user impact
- SEV3: Degraded performance, limited impact
- SEV4: Minor issue, no immediate user impact

Match to runbooks when possible:
- Database errors → database_connection
- High CPU/load → high_cpu
- Memory issues → memory_leak
- Certificate errors → ssl_certificate

Be decisive. Faster triage = faster resolution.""",
)


@triage_agent.tool
async def get_service_dependencies(ctx: RunContext[ReflexDeps], service: str) -> str:
    """Get service dependency information."""
    dependencies = {
        "api-gateway": ["auth-service", "user-service", "postgres"],
        "user-service": ["postgres", "redis"],
        "auth-service": ["redis", "vault"],
        "payment-service": ["postgres", "stripe-api"],
    }
    deps = dependencies.get(service, [])
    return f"Service {service} depends on: {', '.join(deps) or 'no dependencies'}"


@triage_agent.tool
async def get_recent_deployments(ctx: RunContext[ReflexDeps], service: str) -> str:
    """Check recent deployments for the service."""
    # Simulated - in production would query deployment system
    return f"Service {service}: No deployments in last 24 hours."


@triage_agent.tool
async def get_available_runbooks(ctx: RunContext[ReflexDeps]) -> str:
    """List available runbooks."""
    lines = [f"  • {k}: {v['title']}" for k, v in RUNBOOKS.items()]
    return "Available runbooks:\n" + "\n".join(lines)


# =============================================================================
# Alert Processing Agent
# =============================================================================


async def process_alert(ctx: AgentContext) -> dict:
    """Process incoming alerts and create/update incidents."""
    event: AlertEvent = ctx.event

    # Use AI to triage the alert
    try:
        result = await triage_agent.run(
            f"Triage this alert:\n"
            f"  Name: {event.alert_name}\n"
            f"  Service: {event.service}\n"
            f"  Severity: {event.severity}\n"
            f"  Message: {event.message}\n"
            f"  Labels: {event.labels}",
            deps=ctx.deps,
        )
        triage = result.data
    except Exception as e:
        # Default to SEV2 on triage failure
        triage = TriageResult(
            severity=Severity.SEV2,
            category="unknown",
            affected_services=[event.service],
            likely_cause=f"Triage failed: {e}",
            suggested_runbook=None,
            auto_remediation_possible=False,
            confidence=0.0,
        )

    # Create incident
    incident_id = create_incident_id()
    incident = ctx.derive_event(
        IncidentCreatedEvent,
        incident_id=incident_id,
        title=f"[{triage.severity.value.upper()}] {event.alert_name}",
        severity=triage.severity.value,
        status=IncidentStatus.TRIGGERED.value,
        services=triage.affected_services,
        alert_ids=[event.alert_id],
        triage_summary=triage.likely_cause,
    )
    await ctx.publish(incident)

    # Track incident
    ACTIVE_INCIDENTS[incident_id] = {
        "severity": triage.severity.value,
        "status": IncidentStatus.TRIGGERED.value,
        "services": triage.affected_services,
        "escalation_level": EscalationLevel.PRIMARY,
    }

    print(f"\n🚨 [INCIDENT CREATED] {incident_id}")
    print(f"   Title: {incident.title}")
    print(f"   Severity: {triage.severity.value.upper()}")
    print(f"   Services: {', '.join(triage.affected_services)}")
    print(f"   Likely Cause: {triage.likely_cause}")

    # Suggest runbook if found
    if triage.suggested_runbook and triage.suggested_runbook in RUNBOOKS:
        runbook = RUNBOOKS[triage.suggested_runbook]
        runbook_event = ctx.derive_event(
            RunbookSuggestedEvent,
            incident_id=incident_id,
            runbook_id=runbook["id"],
            runbook_title=runbook["title"],
            match_confidence=triage.confidence,
            auto_execute=runbook["auto_executable"] and triage.confidence > 0.8,
        )
        await ctx.publish(runbook_event)

    return {
        "incident_id": incident_id,
        "severity": triage.severity.value,
        "category": triage.category,
    }


alert_processor = SimpleAgent(process_alert)


# =============================================================================
# Escalation Agent
# =============================================================================


async def handle_incident_created(ctx: AgentContext) -> dict:
    """Handle new incident - initiate escalation."""
    event: IncidentCreatedEvent = ctx.event

    # Determine escalation level based on severity
    if event.severity == Severity.SEV1.value:
        level = EscalationLevel.MANAGER  # SEV1 goes to manager immediately
    else:
        level = EscalationLevel.PRIMARY

    target = get_escalation_target(level)

    escalation = ctx.derive_event(
        EscalationEvent,
        incident_id=event.incident_id,
        escalation_level=level.value,
        reason=f"New {event.severity} incident: {event.title}",
        target_user_id=target["user_id"],
        notification_channels=target["channels"],
    )
    await ctx.publish(escalation)

    print(f"\n📢 [ESCALATION] {event.incident_id}")
    print(f"   Level: {level.value.upper()}")
    print(f"   Target: {target['name']} ({target['user_id']})")
    print(f"   Channels: {', '.join(target['channels'])}")

    return {
        "escalated_to": target["user_id"],
        "level": level.value,
    }


escalation_agent = SimpleAgent(handle_incident_created)


# =============================================================================
# Notification Agent
# =============================================================================


async def send_notification(ctx: AgentContext) -> dict:
    """Send notifications for escalation."""
    event: EscalationEvent = ctx.event

    print(f"\n📱 [NOTIFICATION] Incident {event.incident_id}")
    for channel in event.notification_channels:
        emoji = {"slack": "💬", "sms": "📱", "phone": "📞"}.get(channel, "📧")
        print(f"   {emoji} Sending {channel.upper()} to {event.target_user_id}")

    # In production: integrate with Slack, Twilio, PagerDuty

    return {
        "notifications_sent": len(event.notification_channels),
        "target": event.target_user_id,
    }


notification_agent = SimpleAgent(send_notification)


# =============================================================================
# Runbook Handler
# =============================================================================


async def handle_runbook(ctx: AgentContext) -> dict:
    """Handle runbook suggestions."""
    event: RunbookSuggestedEvent = ctx.event

    print(f"\n📖 [RUNBOOK] Suggested for {event.incident_id}")
    print(f"   Title: {event.runbook_title}")
    print(f"   Confidence: {event.match_confidence:.0%}")
    print(f"   Auto-execute: {event.auto_execute}")

    if event.auto_execute:
        print("   🤖 Auto-executing runbook...")
        # In production: trigger automation workflow

    return {
        "runbook_id": event.runbook_id,
        "auto_executed": event.auto_execute,
    }


runbook_agent = SimpleAgent(handle_runbook)


# =============================================================================
# Resolution Handler
# =============================================================================


async def handle_resolution(ctx: AgentContext) -> dict:
    """Handle incident resolution."""
    event: IncidentResolvedEvent = ctx.event

    print(f"\n✅ [RESOLVED] Incident {event.incident_id}")
    print(f"   Summary: {event.resolution_summary}")
    print(f"   TTR: {event.time_to_resolve_minutes} minutes")
    print(f"   Root Cause: {event.root_cause or 'TBD in postmortem'}")

    # Clean up tracking
    if event.incident_id in ACTIVE_INCIDENTS:
        inc = ACTIVE_INCIDENTS.pop(event.incident_id)

        # Request postmortem for SEV1/SEV2
        if inc["severity"] in (Severity.SEV1.value, Severity.SEV2.value):
            postmortem = ctx.derive_event(
                PostmortemRequestedEvent,
                incident_id=event.incident_id,
                severity=inc["severity"],
                services=inc["services"],
                timeline_events=[],  # Would be populated from event history
                assignee=event.resolved_by,
            )
            await ctx.publish(postmortem)
            print("   📝 Postmortem requested")

    return {
        "resolved": True,
        "incident_id": event.incident_id,
    }


resolution_agent = SimpleAgent(handle_resolution)


# =============================================================================
# Postmortem Handler
# =============================================================================


async def handle_postmortem_request(ctx: AgentContext) -> dict:
    """Handle postmortem request."""
    event: PostmortemRequestedEvent = ctx.event

    print(f"\n📝 [POSTMORTEM] Requested for {event.incident_id}")
    print(f"   Severity: {event.severity.upper()}")
    print(f"   Services: {', '.join(event.services)}")
    print(f"   Assignee: {event.assignee}")

    # In production: create Jira ticket, schedule meeting, create doc

    return {
        "postmortem_requested": True,
        "assignee": event.assignee,
    }


postmortem_agent = SimpleAgent(handle_postmortem_request)


# =============================================================================
# Trigger Registration
# =============================================================================


# Deduplicate alerts (same alert within 5 minutes)
alert_dedupe = dedupe_filter(
    key_func=lambda e: f"{e.alert_name}:{e.service}",
    window_seconds=300,
)


@trigger(
    name="alert-processor",
    filter=type_filter("alert.fired") & alert_dedupe,
    trigger_func=immediate_trigger(),
    agent=alert_processor,
    priority=20,
)
def alert_trigger():
    """Process incoming alerts with deduplication."""
    pass


@trigger(
    name="incident-escalator",
    filter=type_filter("incident.created"),
    trigger_func=immediate_trigger(),
    agent=escalation_agent,
    priority=15,
)
def escalation_trigger():
    """Escalate new incidents."""
    pass


@trigger(
    name="notification-sender",
    filter=type_filter("incident.escalation"),
    trigger_func=immediate_trigger(),
    agent=notification_agent,
    priority=10,
)
def notification_trigger():
    """Send notifications for escalations."""
    pass


@trigger(
    name="runbook-handler",
    filter=type_filter("incident.runbook_suggested"),
    trigger_func=immediate_trigger(),
    agent=runbook_agent,
    priority=10,
)
def runbook_trigger():
    """Handle runbook suggestions."""
    pass


@trigger(
    name="resolution-handler",
    filter=type_filter("incident.resolved"),
    trigger_func=immediate_trigger(),
    agent=resolution_agent,
    priority=15,
)
def resolution_trigger():
    """Handle incident resolution."""
    pass


@trigger(
    name="postmortem-handler",
    filter=type_filter("incident.postmortem_requested"),
    trigger_func=immediate_trigger(),
    agent=postmortem_agent,
    priority=5,
)
def postmortem_trigger():
    """Handle postmortem requests."""
    pass


# =============================================================================
# Demo Runner
# =============================================================================


async def demo():
    """Run an interactive demonstration."""
    print("=" * 60)
    print("🚨 Incident Response Example")
    print("=" * 60)

    # Show registered components
    registry = get_registry()
    print(f"\nRegistered triggers: {len(registry.triggers)}")
    for t in registry.triggers:
        print(f"  • {t.name} (priority: {t.priority})")

    print("\nRegistered event types:")
    for name in EventRegistry.type_names():
        if "incident" in name or "alert" in name:
            print(f"  • {name}")

    # Simulate alerts
    print("\n" + "-" * 60)
    print("Simulated Incident Flow:")
    print("-" * 60)

    sample_alerts = [
        {
            "alert_id": "alert_001",
            "alert_name": "HighCPUUsage",
            "service": "api-gateway",
            "severity": "warning",
            "message": "CPU usage above 90% for 5 minutes",
            "labels": {"env": "production", "region": "us-east-1"},
        },
        {
            "alert_id": "alert_002",
            "alert_name": "DatabaseConnectionFailure",
            "service": "user-service",
            "severity": "critical",
            "message": "Cannot connect to primary database",
            "labels": {"env": "production", "db": "postgres-primary"},
        },
        {
            "alert_id": "alert_003",
            "alert_name": "SSLCertificateExpiring",
            "service": "payment-service",
            "severity": "warning",
            "message": "SSL certificate expires in 7 days",
            "labels": {"env": "production", "domain": "pay.example.com"},
        },
    ]

    for alert in sample_alerts:
        sev_emoji = "🔴" if alert["severity"] == "critical" else "🟡"
        print(f"\n{sev_emoji} [{alert['alert_name']}] {alert['service']}")
        print(f"   {alert['message']}")

        event = AlertEvent(
            source=f"prometheus:{alert['service']}",
            alert_id=alert["alert_id"],
            alert_name=alert["alert_name"],
            service=alert["service"],
            severity=alert["severity"],
            message=alert["message"],
            labels=alert["labels"],
        )
        print(f"   Event ID: {event.id}")

    print("\n" + "=" * 60)
    print("Incident Lifecycle:")
    print("  1. AlertEvent received from monitoring")
    print("  2. AI triages: severity, category, runbook")
    print("  3. IncidentCreatedEvent published")
    print("  4. EscalationEvent → on-call notified")
    print("  5. RunbookSuggestedEvent → auto-remediation if confident")
    print("  6. AcknowledgmentEvent (manual)")
    print("  7. IncidentResolvedEvent → cleanup")
    print("  8. PostmortemRequestedEvent (SEV1/SEV2)")
    print()
    print("On-Call Schedule:")
    for level, person in ON_CALL_SCHEDULE.items():
        print(f"  • {level.value}: {person['name']} ({person['channels']})")
    print()
    print("To run the full system:")
    print("  1. Start PostgreSQL: docker-compose up -d")
    print("  2. Run migrations: alembic upgrade head")
    print("  3. Start API: uvicorn reflex.api.app:app --reload")
    print("  4. POST alerts to /events")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
