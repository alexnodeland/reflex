"""PydanticAI agents for common use cases.

This module provides pre-configured agents for common patterns:
- alert_agent: Generates and sends alerts
- summary_agent: Summarizes event streams

These agents demonstrate how to build PydanticAI agents with
tools that access the ReflexDeps dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from reflex.config import settings
from reflex.core.deps import ReflexDeps

if TYPE_CHECKING:
    from reflex.core.events import Event

# --- Response Models ---


class AlertResponse(BaseModel):
    """Structured response from the alert agent."""

    severity: str = Field(description="Alert severity: low, medium, high, critical")
    title: str = Field(description="Brief alert title")
    description: str = Field(description="Detailed alert description")
    recommended_action: str = Field(description="Suggested action to take")
    should_notify: bool = Field(default=True, description="Whether to send notifications")


class SummaryResponse(BaseModel):
    """Structured response from the summary agent."""

    # Required fields (per PRD)
    period: str = Field(description="Time period covered (e.g., 'Last 24 hours')")
    event_count: int = Field(description="Total events summarized")
    highlights: list[str] = Field(description="Key highlights from the events")
    concerns: list[str] = Field(description="Issues that need attention")

    # Optional extended fields
    notable_patterns: list[str] = Field(
        default_factory=list, description="Notable patterns detected"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations based on the summary"
    )


# --- Alert Agent ---

alert_agent: Agent[ReflexDeps, AlertResponse] = Agent(
    model=settings.default_model,
    deps_type=ReflexDeps,
    output_type=AlertResponse,
    defer_model_check=True,  # Don't validate model at import time
    system_prompt="""You are an intelligent alerting agent for a real-time event processing system.

Your job is to:
1. Analyze event summaries and patterns
2. Determine the severity of issues
3. Generate clear, actionable alerts
4. Recommend appropriate responses

When generating alerts:
- Be specific about what happened
- Quantify the impact when possible
- Suggest concrete actions
- Consider escalation needs

Severity levels:
- low: Minor issue, no immediate action needed
- medium: Issue worth investigating soon
- high: Problem requiring prompt attention
- critical: Severe issue requiring immediate action
""",
)


@alert_agent.tool
async def get_recent_events(
    ctx: RunContext[ReflexDeps],
    event_type: str | None = None,
    hours: int = 1,
) -> str:
    """Fetch recent events from the store.

    Args:
        ctx: Run context with dependencies
        event_type: Optional filter by event type
        hours: Number of hours to look back (default 1)

    Returns:
        Summary of recent events
    """
    store = ctx.deps.store
    start = datetime.now(UTC) - timedelta(hours=hours)

    event_types = [event_type] if event_type else None
    events: list[Event] = []

    async for event in store.replay(start=start, event_types=event_types):
        events.append(event)
        if len(events) >= 100:  # Cap at 100 events
            break

    if not events:
        return f"No events found in the last {hours} hour(s)"

    lines: list[str] = [f"Found {len(events)} events in the last {hours} hour(s):"]
    for event in events[-20:]:  # Show last 20
        lines.append(f"- [{event.timestamp.isoformat()}] {event.type} from {event.source}")

    return "\n".join(lines)


@alert_agent.tool
async def send_slack_notification(
    ctx: RunContext[ReflexDeps],
    channel: str,
    message: str,
    severity: str = "medium",
) -> str:
    """Send a notification to Slack.

    Args:
        ctx: Run context with dependencies
        channel: Slack channel to post to (e.g., #alerts)
        message: Message to send
        severity: Alert severity for emoji selection

    Returns:
        Confirmation message
    """
    # In a real implementation, this would use the httpx client
    # to post to a Slack webhook URL from settings
    http = ctx.deps.http

    emoji_map = {
        "low": "ℹ️",  # noqa: RUF001
        "medium": "⚠️",
        "high": "🔶",
        "critical": "🚨",
    }
    emoji = emoji_map.get(severity, "📢")

    # Placeholder - in production, would POST to Slack webhook
    # webhook_url = settings.slack_webhook_url
    # await http.post(webhook_url, json={"text": f"{emoji} {message}", "channel": channel})

    # For now, just log and return success
    _ = http  # Acknowledge the dependency is available
    return f"[Slack] Would send to {channel}: {emoji} {message}"


@alert_agent.tool
async def create_incident_ticket(
    ctx: RunContext[ReflexDeps],
    title: str,
    description: str,
    priority: str = "medium",
) -> str:
    """Create an incident ticket in the ticketing system.

    Args:
        ctx: Run context with dependencies
        title: Ticket title
        description: Detailed description
        priority: Ticket priority (low, medium, high, critical)

    Returns:
        Ticket ID or confirmation
    """
    # In a real implementation, this would use the httpx client
    # to create a ticket in PagerDuty, Jira, etc.
    http = ctx.deps.http

    # Placeholder - in production, would POST to ticketing API
    # await http.post(settings.ticketing_api_url, json={...})

    _ = http  # Acknowledge the dependency is available
    ticket_id = f"INC-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    return f"[Ticketing] Would create ticket {ticket_id}: {title} (priority: {priority})"


# --- Summary Agent ---

_SUMMARY_SYSTEM_PROMPT = """\
You are an intelligent summarization agent for a real-time event processing system.

Your job is to:
1. Analyze batches of events
2. Identify patterns and anomalies
3. Generate concise, informative summaries
4. Highlight important trends

When summarizing:
- Focus on what's actionable
- Group related events
- Note unusual patterns
- Quantify changes over time

Your summaries should be:
- Concise but comprehensive
- Easy to scan quickly
- Actionable when relevant
"""

summary_agent: Agent[ReflexDeps, SummaryResponse] = Agent(
    model=settings.default_model,
    deps_type=ReflexDeps,
    output_type=SummaryResponse,
    defer_model_check=True,  # Don't validate model at import time
    system_prompt=_SUMMARY_SYSTEM_PROMPT,
)


@summary_agent.tool
async def get_event_statistics(
    ctx: RunContext[ReflexDeps],
    hours: int = 24,
) -> str:
    """Get statistics about recent events.

    Args:
        ctx: Run context with dependencies
        hours: Number of hours to analyze (default 24)

    Returns:
        Statistics summary
    """
    store = ctx.deps.store
    start = datetime.now(UTC) - timedelta(hours=hours)

    counts: dict[str, int] = {}
    sources: set[str] = set()
    total = 0

    async for event in store.replay(start=start):
        counts[event.type] = counts.get(event.type, 0) + 1
        sources.add(event.source)
        total += 1
        if total >= 1000:  # Cap processing
            break

    lines = [f"Event statistics for the last {hours} hours:"]
    lines.append(f"- Total events: {total}")
    lines.append(f"- Unique sources: {len(sources)}")
    lines.append("- By type:")
    for event_type, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"  - {event_type}: {count}")

    return "\n".join(lines)


@summary_agent.tool
async def get_error_rate(
    ctx: RunContext[ReflexDeps],
    hours: int = 1,
) -> str:
    """Calculate error rate for recent events.

    Args:
        ctx: Run context with dependencies
        hours: Number of hours to analyze (default 1)

    Returns:
        Error rate information
    """
    store = ctx.deps.store
    start = datetime.now(UTC) - timedelta(hours=hours)

    total = 0
    errors = 0

    async for event in store.replay(start=start):
        total += 1
        # Consider lifecycle events with action='error' as errors
        if event.type == "lifecycle" and hasattr(event, "action"):
            if event.action == "error":  # type: ignore[union-attr]
                errors += 1
        if total >= 1000:
            break

    if total == 0:
        return f"No events in the last {hours} hour(s)"

    rate = (errors / total) * 100
    return f"Error rate: {rate:.2f}% ({errors} errors out of {total} events)"
