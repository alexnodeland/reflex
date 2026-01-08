# Incident Response Example

A PagerDuty-like incident management system with AI-powered triage and automated escalation.

## What This Example Demonstrates

1. **Full Incident Lifecycle**: Alert → Incident → Escalation → Resolution → Postmortem
2. **AI-Powered Triage**: LLM determines severity, category, and runbook
3. **Escalation Chain**: Automatic escalation through on-call levels
4. **Alert Deduplication**: Prevents alert storms from creating multiple incidents
5. **Runbook Integration**: Suggests and optionally auto-executes remediation
6. **Postmortem Automation**: Triggers postmortem for high-severity incidents

## Architecture

```
Monitoring Alert → AlertEvent
                      │
                      ▼
                  Deduplication (5min)
                      │
                      ▼
              ┌───────────────┐
              │ Triage Agent  │
              │ (LLM)         │
              └───────┬───────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
 IncidentCreatedEvent      RunbookSuggestedEvent
         │                         │
         ▼                         ▼
 EscalationEvent              Auto-execute?
         │                    (if confidence > 80%)
         ▼
 NotificationEvent
 (Slack, SMS, Phone)
         │
         ▼
 AcknowledgmentEvent ←── On-call responds
         │
         ▼
 IncidentResolvedEvent
         │
         ▼
 PostmortemRequestedEvent
 (SEV1/SEV2 only)
```

## Event Types

| Event | Description |
|-------|-------------|
| `alert.fired` | Raw alert from monitoring |
| `incident.created` | New incident created |
| `incident.updated` | Status change |
| `incident.escalation` | Escalation to next level |
| `incident.acknowledged` | On-call acknowledged |
| `incident.runbook_suggested` | Runbook matched |
| `incident.resolved` | Incident closed |
| `incident.postmortem_requested` | Postmortem triggered |

## Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| SEV1 | Critical outage, data loss | Immediate, all hands |
| SEV2 | Significant impact | Immediate response |
| SEV3 | Limited impact | Business hours |
| SEV4 | Minor issue | Best effort |

## Escalation Chain

```
PRIMARY (5 min) → SECONDARY (10 min) → MANAGER (15 min) → EXECUTIVE
```

| Level | Who | Channels |
|-------|-----|----------|
| Primary | On-call engineer | Slack, SMS |
| Secondary | Backup engineer | Slack, SMS, Phone |
| Manager | Engineering manager | Slack, Phone |
| Executive | VP Engineering | Phone |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or use Docker)
- Anthropic API key (for Claude)

### Setup

```bash
# From the repository root
cd reflex

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL
docker-compose up -d

# Run database migrations
alembic upgrade head

# Set environment variables
export ANTHROPIC_API_KEY="your-key-here"
```

### Run the Demo

```bash
# Run the demo script
python -m examples.incident_response.main
```

### Start the Full System

```bash
# Terminal 1: Start the API server
uvicorn reflex.api.app:app --reload
```

### Test Alerts

```bash
# Critical database alert
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "alert.fired",
    "source": "prometheus:user-service",
    "alert_id": "alert_001",
    "alert_name": "DatabaseConnectionFailure",
    "service": "user-service",
    "severity": "critical",
    "message": "Cannot connect to primary database",
    "labels": {"env": "production", "db": "postgres-primary"}
  }'

# Warning alert (high CPU)
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "alert.fired",
    "source": "prometheus:api-gateway",
    "alert_id": "alert_002",
    "alert_name": "HighCPUUsage",
    "service": "api-gateway",
    "severity": "warning",
    "message": "CPU usage above 90% for 5 minutes",
    "labels": {"env": "production", "region": "us-east-1"}
  }'

# Acknowledge incident
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "incident.acknowledged",
    "source": "oncall:alice",
    "incident_id": "INC-00001",
    "acknowledged_by": "alice",
    "response_time_seconds": 120
  }'

# Resolve incident
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "incident.resolved",
    "source": "oncall:alice",
    "incident_id": "INC-00001",
    "resolution_summary": "Restarted database connection pool",
    "resolved_by": "alice",
    "time_to_resolve_minutes": 15,
    "root_cause": "Connection pool exhaustion due to slow queries"
  }'
```

## Key Components

### Alert Deduplication

```python
alert_dedupe = dedupe_filter(
    key_func=lambda e: f"{e.alert_name}:{e.service}",
    window_seconds=300,  # 5 minutes
)
```

Prevents alert storms from creating multiple incidents. Same alert from same service within 5 minutes is ignored.

### AI Triage with Tools

```python
triage_agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    result_type=TriageResult,
)

@triage_agent.tool
async def get_service_dependencies(ctx, service: str) -> str:
    """Get service dependency information."""

@triage_agent.tool
async def get_recent_deployments(ctx, service: str) -> str:
    """Check recent deployments for the service."""

@triage_agent.tool
async def get_available_runbooks(ctx) -> str:
    """List available runbooks."""
```

The LLM can investigate before triaging.

### Runbook Matching

```python
RUNBOOKS = {
    "database_connection": {
        "id": "rb_001",
        "title": "Database Connection Issues",
        "auto_executable": False,
    },
    "high_cpu": {
        "id": "rb_002",
        "title": "High CPU Usage",
        "auto_executable": True,
    },
}
```

AI matches alerts to runbooks. High-confidence matches can auto-execute.

### Postmortem Automation

```python
# Request postmortem for SEV1/SEV2
if severity in (Severity.SEV1, Severity.SEV2):
    postmortem = ctx.derive_event(
        PostmortemRequestedEvent,
        incident_id=event.incident_id,
        services=services,
        assignee=event.resolved_by,
    )
    await ctx.publish(postmortem)
```

## Extending This Example

### Add Escalation Timeouts

```python
@EventRegistry.register
class EscalationTimeoutEvent(BaseEvent):
    type: Literal["incident.escalation_timeout"] = "incident.escalation_timeout"
    incident_id: str
    current_level: str
    wait_time_seconds: int

# Use a timer trigger to check for unacknowledged incidents
@trigger(
    name="escalation-timeout-checker",
    filter=type_filter("timer.tick"),
    trigger_func=immediate_trigger(),
)
```

### Add Slack Integration

```python
async def send_slack_notification(channel: str, message: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/chat.postMessage",
            json={"channel": channel, "text": message},
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
        )
```

### Add Metric Correlation

```python
@triage_agent.tool
async def get_service_metrics(ctx: RunContext[ReflexDeps], service: str) -> str:
    """Get current metrics for service."""
    # Query Prometheus/Datadog
    return "CPU: 92%, Memory: 78%, Latency p99: 250ms"
```

### Add Auto-Remediation

```python
@EventRegistry.register
class RemediationExecutedEvent(BaseEvent):
    type: Literal["incident.remediation_executed"] = "incident.remediation_executed"
    incident_id: str
    runbook_id: str
    result: str  # "success", "failed"
    output: str

# When runbook.auto_execute is True and confidence > 0.8
# Execute the runbook steps automatically
```

## Production Considerations

1. **PagerDuty/OpsGenie Integration**: Real notification routing
2. **Slack/Teams Integration**: Rich incident updates
3. **Metrics Integration**: Correlate with Prometheus/Datadog
4. **Runbook Automation**: Execute remediation scripts
5. **SLA Tracking**: Measure TTR, MTTA by severity
6. **On-Call Management**: Integrate with scheduling system

## Metrics to Track

| Metric | Description |
|--------|-------------|
| MTTA | Mean Time to Acknowledge |
| MTTR | Mean Time to Resolve |
| Incidents by Severity | Distribution of SEV1-4 |
| Escalation Rate | % that escalate beyond primary |
| Auto-Resolution Rate | % resolved by runbooks |

## Related Examples

- [Log Anomaly Detection](../log_anomaly/) - Alert source
- [Support Bot](../support_bot/) - Similar escalation patterns

See [docs/extending.md](../../docs/extending.md) for more details.
