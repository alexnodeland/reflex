# Bruno API Collection

This directory contains a [Bruno](https://www.usebruno.com/) collection for testing the Reflex API.

## Setup

1. Install Bruno from [usebruno.com](https://www.usebruno.com/downloads)
2. Open Bruno and select **Open Collection**
3. Navigate to this `bruno/` directory

## Environments

| Environment | Base URL | Use Case |
|-------------|----------|----------|
| **docker** | `http://localhost:8000` | Default for `docker compose up` |
| **local** | `http://localhost:8000` | Local development |

Select an environment from the dropdown in Bruno before running requests.

## Available Requests

### Health

| Request | Method | Endpoint | Description |
|---------|--------|----------|-------------|
| Health Check | GET | `/health` | Basic health status |
| Health Detailed | GET | `/health/detailed` | Health with component indicators |

### Events

| Request | Method | Endpoint | Description |
|---------|--------|----------|-------------|
| Publish HTTP Request | POST | `/events` | Publish an `http.request` event |
| Publish WS Message | POST | `/events` | Publish a `websocket.message` event |
| Publish Timer Tick | POST | `/events` | Publish a `timer.tick` event |
| Publish Lifecycle | POST | `/events` | Publish a `lifecycle.*` event |
| List Dead-Letter Queue | GET | `/events/dlq` | View failed events in DLQ |
| Retry DLQ Event | POST | `/events/dlq/:id/retry` | Retry a failed event |

## Usage Tips

**Testing event flow:**
```
1. Run "Health Check" to verify server is running
2. Run "Publish HTTP Request" to send a test event
3. Check server logs to see the agent process the event
```

**Working with DLQ:**
```
1. Run "List Dead-Letter Queue" to see failed events
2. The request automatically stores the first event ID
3. Run "Retry DLQ Event" to reprocess it
```

## Event Payload Examples

All event requests include example payloads. Modify the JSON body to test different scenarios:

```json
{
  "type": "http.request",
  "source": "bruno:test",
  "method": "POST",
  "path": "/api/users",
  "headers": { "Content-Type": "application/json" },
  "body": { "username": "testuser" }
}
```

## Running from CLI

Bruno also supports CLI execution:

```bash
# Install Bruno CLI
npm install -g @usebruno/cli

# Run all requests
bru run --env docker

# Run specific folder
bru run events --env docker

# Run single request
bru run health/health-check.bru --env docker
```
