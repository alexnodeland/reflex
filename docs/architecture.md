# Architecture

Reflex is an event-driven AI agent framework using PostgreSQL LISTEN/NOTIFY for real-time pub/sub.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │WebSocket │  │   HTTP   │  │  Health  │  │   Agent Loop     │ │
│  │ Handler  │  │ Endpoints│  │  Checks  │  │   (Background)   │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────────┬─────────┘ │
└───────┼─────────────┼───────────────────────────────┼───────────┘
        │             │                               │
        v             v                               v
┌─────────────────────────────────────────────────────────────────┐
│                        EventStore                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   publish() │  │ subscribe() │  │  ack() / nack()         │  │
│  │             │  │  (LISTEN/   │  │  (exponential backoff)  │  │
│  │             │  │   NOTIFY)   │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            v
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  events table (id, type, payload, status, attempts...)  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Event Flow

1. **Ingestion**: Events arrive via WebSocket or HTTP
2. **Persistence**: EventStore persists to PostgreSQL and fires NOTIFY
3. **Processing**: Agent loop receives events via subscribe()
4. **Execution**: PydanticAI agent processes with tools
5. **Completion**: Events are ack'd (completed) or nack'd (retry with backoff)

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| EventStore | `src/reflex/infra/store.py` | Persistent event queue with pub/sub |
| Events | `src/reflex/core/events.py` | Pydantic models with discriminated unions |
| EventRegistry | `src/reflex/core/events.py` | Runtime event type registration |
| Triggers | `src/reflex/agent/triggers.py` | Filter + agent connections |
| Filters | `src/reflex/agent/filters.py` | Event matching predicates |
| Dependencies | `src/reflex/core/deps.py` | Focused dependency containers |
| Errors | `src/reflex/core/errors.py` | Structured error handling |
| Agent | `src/reflex/agent/agents.py` | PydanticAI agent with tools |
| API | `src/reflex/api/app.py` | FastAPI with WebSocket support |
| Config | `src/reflex/config.py` | Pydantic-settings configuration |

## Module Organization

- `src/reflex/infra/` - Infrastructure (EventStore, database, observability) - keep stable
- `src/reflex/core/` - Core types (events, deps, errors) - extend carefully
- `src/reflex/agent/` - Agent logic (triggers, filters, agents) - primary extension point
- `src/reflex/api/` - FastAPI routes and middleware
