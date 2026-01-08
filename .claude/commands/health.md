---
description: Check system health and component status
---

# Check System Health

Check the health of the running Reflex system.

## Quick Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

## Detailed Health

```bash
curl http://localhost:8000/health/detailed
```

Shows status of all components:
```json
{
  "status": "healthy",
  "indicators": [
    {"name": "database", "status": "healthy", "message": "Connected"},
    {"name": "event_store", "status": "healthy", "message": "Operational"}
  ]
}
```

## Using Bruno

```bash
make api-test-health
```

## Docker Services Check

```bash
# Check all services
docker compose ps

# Check logs for issues
docker compose logs app --tail=50
docker compose logs db --tail=50
```

## Common Issues

### Database not ready
```bash
# Wait for DB to be healthy
docker compose up -d db
docker compose exec db pg_isready -U reflex
```

### App not starting
```bash
# Check app logs
docker compose logs app -f

# Restart app
docker compose restart app
```

### Port conflicts
```bash
# Check what's using port 8000
lsof -i :8000
```

Run the health checks and report any issues found.
