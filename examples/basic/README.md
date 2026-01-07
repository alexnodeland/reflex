# Basic Reflex Example

A simple error monitoring system that demonstrates core Reflex concepts.

## What This Example Does

1. **Custom Events**: Defines `ErrorEvent` and `AlertEvent` types
2. **Error Threshold Trigger**: Alerts after 3 errors in 60 seconds
3. **AI-Powered Agent**: Classifies error severity (simplified for demo)
4. **Event Chaining**: Error events trigger alert events

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or use Docker)
- OpenAI API key (optional, for AI features)

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
export OPENAI_API_KEY="your-key-here"  # Optional
```

### Run the Demo

```bash
# Run the demo script
python -m examples.basic.main
```

### Start the Full System

```bash
# Terminal 1: Start the API server
uvicorn reflex.api.app:app --reload

# Terminal 2: Watch logs (optional)
docker-compose logs -f
```

### Publish Test Events

```bash
# Publish an error event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "app.error",
    "source": "production-api",
    "service": "auth-service",
    "error_code": "AUTH_001",
    "message": "Failed to validate token",
    "severity": 7
  }'

# Repeat 3 times within 60 seconds to trigger an alert
```

## Code Structure

```
examples/basic/
├── main.py          # Main example code
└── README.md        # This file
```

### Key Components

#### Custom Events

```python
@EventRegistry.register
class ErrorEvent(BaseEvent):
    type: Literal["app.error"] = "app.error"
    service: str
    error_code: str
    message: str
    severity: int = 1
```

#### Trigger Registration

```python
@trigger(
    name="error-threshold-alert",
    filter=type_filter("app.error") & source_filter("production-*"),
    trigger_func=error_threshold_trigger(threshold=3, window_seconds=60),
    agent=error_alert_agent,
    scope_key=lambda e: f"service:{e.service}",
)
def error_threshold_handler():
    pass
```

#### Agent Implementation

```python
async def classify_and_alert(ctx: AgentContext) -> dict:
    event = ctx.event
    severity = "high" if event.severity >= 8 else "medium"

    alert = ctx.derive_event(
        AlertEvent,
        title=f"Error Alert: {event.service}",
        description=f"Multiple errors: {event.message}",
        severity=severity,
    )
    await ctx.publish(alert)

    return {"alert_id": alert.id}
```

## Next Steps

- Add more event types for your domain
- Implement custom filters for complex routing
- Add AI-powered analysis with PydanticAI
- Set up monitoring with the `/health/detailed` endpoint

See [docs/extending.md](../../docs/extending.md) for more details.
