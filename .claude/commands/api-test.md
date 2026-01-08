---
description: Run Bruno API collection against running server
argument-hint: "[folder]"
---

# Run API Tests

Run Bruno API tests: **$ARGUMENTS**

## Prerequisites

1. Server must be running: `make dev`
2. Bruno CLI installed: `npm install -g @usebruno/cli`

## Commands

```bash
# Run all API tests
make api-test

# Run health checks only
make api-test-health

# Run event tests only
make api-test-events
```

## Available Test Folders

| Folder | Description |
|--------|-------------|
| `health` | Health check endpoints |
| `events` | Event publishing and DLQ |

## Manual Execution

```bash
# Run specific folder
bru run bruno/health --env docker

# Run single request
bru run bruno/health/health-check.bru --env docker

# Run all
bru run bruno --env docker
```

## Environments

| Environment | BASE_URL |
|-------------|----------|
| `docker` | `http://localhost:8000` |
| `local` | `http://localhost:8000` |

## What's Tested

### Health (`/health`)
- Basic health check
- Detailed health with component status

### Events (`/events`)
- Publish HTTP request event
- Publish WebSocket message event
- Publish timer tick event
- Publish lifecycle event
- List dead-letter queue
- Retry DLQ event

If a folder is specified, run only that folder. Otherwise, run all tests.
