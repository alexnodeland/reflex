"""Reflex - Real-time AI Agent Framework.

Reflex is a framework for building event-driven AI agents that respond
to real-time events with intelligent actions.

Quick Start:
    from reflex import Event, WebSocketEvent, trigger, type_filter
    from reflex.agent import alert_agent

    @trigger(
        name="error-alerts",
        filter=type_filter("error"),
        agent=alert_agent,
    )
    def handle_errors(event, context):
        return {"alert": True}

Core Types:
    - Event: Union of all event types (WebSocketEvent, HTTPEvent, etc.)
    - BaseEvent: Base class for custom events
    - EventRegistry: Register custom event types at runtime

Agent Components:
    - Agent: Protocol for agent implementations
    - Trigger: Connects filters to agents
    - EventFilter: Base class for event filters

Infrastructure:
    - EventStore: Event persistence with pub/sub
    - ReflexDeps: Dependency container for agents
"""

# Agent components - filters, triggers, agents
from reflex.agent import (
    Agent,
    AlertResponse,
    AndFilter,
    BaseAgent,
    DedupeFilter,
    EventFilter,
    Filter,
    FilterContext,
    KeywordFilter,
    NotFilter,
    OrFilter,
    RateLimitFilter,
    SimpleAgent,
    SourceFilter,
    SummaryResponse,
    Trigger,
    TriggerFunc,
    TriggerRegistry,
    TypeFilter,
    alert_agent,
    all_of,
    any_of,
    dedupe_filter,
    error_threshold_trigger,
    get_registry,
    immediate_trigger,
    keyword_filter,
    not_matching,
    periodic_summary_trigger,
    rate_limit_filter,
    register_trigger,
    run_loop,
    run_once,
    source_filter,
    summary_agent,
    trigger,
    type_filter,
)
from reflex.config import Settings, configure_settings, get_settings, settings

# Core types - events, context, dependencies
from reflex.core import (
    AgentContext,
    AgentError,
    BaseEvent,
    DecisionContext,
    ErrorCode,
    Event,
    EventMeta,
    EventNotFoundError,
    EventProtocol,
    EventRegistry,
    ExecutionContext,
    HTTPEvent,
    LifecycleEvent,
    LockError,
    NetworkContext,
    PublicationError,
    RateLimitError,
    ReflexDeps,
    ReflexError,
    StorageContext,
    StoreError,
    TimerEvent,
    ValidationError,
    WebSocketEvent,
    get_event_union,
)

__version__ = settings.version

__all__ = [
    "Agent",
    "AgentContext",
    "AgentError",
    "AlertResponse",
    "AndFilter",
    "BaseAgent",
    "BaseEvent",
    "DecisionContext",
    "DedupeFilter",
    "ErrorCode",
    "Event",
    "EventFilter",
    "EventMeta",
    "EventNotFoundError",
    "EventProtocol",
    "EventRegistry",
    "ExecutionContext",
    "Filter",
    "FilterContext",
    "HTTPEvent",
    "KeywordFilter",
    "LifecycleEvent",
    "LockError",
    "NetworkContext",
    "NotFilter",
    "OrFilter",
    "PublicationError",
    "RateLimitError",
    "RateLimitFilter",
    "ReflexDeps",
    "ReflexError",
    "Settings",
    "SimpleAgent",
    "SourceFilter",
    "StorageContext",
    "StoreError",
    "SummaryResponse",
    "TimerEvent",
    "Trigger",
    "TriggerFunc",
    "TriggerRegistry",
    "TypeFilter",
    "ValidationError",
    "WebSocketEvent",
    "__version__",
    "alert_agent",
    "all_of",
    "any_of",
    "configure_settings",
    "dedupe_filter",
    "error_threshold_trigger",
    "get_event_union",
    "get_registry",
    "get_settings",
    "immediate_trigger",
    "keyword_filter",
    "not_matching",
    "periodic_summary_trigger",
    "rate_limit_filter",
    "register_trigger",
    "run_loop",
    "run_once",
    "settings",
    "source_filter",
    "summary_agent",
    "trigger",
    "type_filter",
]
