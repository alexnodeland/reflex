# Scaling

Strategies for scaling Reflex beyond single-instance deployments.

## Current Architecture (PostgreSQL LISTEN/NOTIFY)

The default implementation uses PostgreSQL's LISTEN/NOTIFY for real-time event delivery. This is suitable for:

- **Single-region deployments**
- **Moderate throughput** (thousands of events/second)
- **Teams wanting minimal infrastructure**

## Horizontal Scaling

The current design supports multiple concurrent consumers:

```yaml
# docker-compose.yml - Scale consumers
services:
  agent:
    deploy:
      replicas: 3
```

Events are claimed with `FOR UPDATE SKIP LOCKED`, preventing duplicate processing.

## Scaling Beyond PostgreSQL

For higher scale requirements, the EventStore interface is designed to be swappable.

### Redis Streams (Recommended for high throughput)

```python
# Future: Redis-backed EventStore
class RedisEventStore:
    """Drop-in replacement using Redis Streams."""
    async def publish(self, event): ...
    async def subscribe(self, event_types): ...
```

Benefits of Redis Streams:

- **Higher throughput**: 100k+ events/second
- **Consumer groups**: Built-in load balancing across consumers
- **Persistence**: Optional persistence with AOF/RDB
- **Pub/Sub**: Native support for fan-out patterns

### Migration Path

1. Implement `RedisEventStore` with same interface
2. Add `EVENT_BACKEND` config option (`postgres` | `redis`)
3. Swap implementation in dependency injection
4. PostgreSQL remains for event history/replay

## Scaling Considerations

1. **Horizontal Scaling**: Run multiple API instances behind a load balancer
2. **Event Processing**: Run multiple agent loop instances (locking prevents duplicates)
3. **Database Pooling**: Configure pool size based on instance count:
   ```
   DATABASE_POOL_SIZE=5
   DATABASE_POOL_MAX_OVERFLOW=10
   ```
