"""Content Moderation Example - Real-time AI-Powered Moderation.

This example demonstrates a real-time content moderation system that:
1. Receives messages via WebSocket (chat, comments, posts)
2. Filters spam using rate limiting and deduplication
3. Classifies content using an LLM for policy violations
4. Takes action: approve, warn, remove, or ban
5. Generates periodic moderation reports

Run with:
    python -m examples.content_moderation.main

Or start the API server:
    uvicorn reflex.api.app:app --reload
"""

from __future__ import annotations

import asyncio
import hashlib
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

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
    periodic_summary_trigger,
    rate_limit_filter,
    trigger,
    type_filter,
)

# =============================================================================
# Enums and Models
# =============================================================================


class ViolationType(str, Enum):
    """Content policy violation types."""

    NONE = "none"
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    ADULT_CONTENT = "adult_content"
    MISINFORMATION = "misinformation"
    SELF_HARM = "self_harm"
    ILLEGAL_ACTIVITY = "illegal_activity"


class ModerationAction(str, Enum):
    """Actions taken by moderation system."""

    APPROVE = "approve"
    WARN = "warn"
    REMOVE = "remove"
    SHADOW_BAN = "shadow_ban"
    BAN = "ban"
    ESCALATE = "escalate"


class ContentCategory(str, Enum):
    """Content categories for context-aware moderation."""

    CHAT = "chat"
    COMMENT = "comment"
    POST = "post"
    USERNAME = "username"
    PROFILE = "profile"


class ModerationResult(BaseModel):
    """LLM moderation decision output."""

    violation_type: ViolationType
    severity: float = Field(ge=0.0, le=1.0, description="0=benign, 1=severe")
    confidence: float = Field(ge=0.0, le=1.0)
    action: ModerationAction
    reasoning: str
    flagged_phrases: list[str] = Field(default_factory=list)


# =============================================================================
# Custom Event Types
# =============================================================================


@EventRegistry.register
class ContentSubmittedEvent(BaseEvent):
    """User-submitted content for moderation."""

    type: Literal["content.submitted"] = "content.submitted"
    content_id: str
    user_id: str
    room_id: str  # chat room, forum, etc.
    category: str  # chat, comment, post, username, profile
    content: str
    metadata: dict = Field(default_factory=dict)  # additional context


@EventRegistry.register
class ModerationDecisionEvent(BaseEvent):
    """Moderation decision for content."""

    type: Literal["moderation.decision"] = "moderation.decision"
    content_id: str
    user_id: str
    room_id: str
    violation_type: str
    severity: float
    action: str
    reasoning: str
    original_content: str


@EventRegistry.register
class UserWarningEvent(BaseEvent):
    """Warning issued to user."""

    type: Literal["moderation.warning"] = "moderation.warning"
    user_id: str
    warning_type: str
    message: str
    warning_count: int


@EventRegistry.register
class UserBanEvent(BaseEvent):
    """User banned from platform/room."""

    type: Literal["moderation.ban"] = "moderation.ban"
    user_id: str
    room_id: str | None  # None = platform-wide
    ban_type: str  # "temporary", "permanent", "shadow"
    duration_hours: int | None
    reason: str


@EventRegistry.register
class ContentRemovedEvent(BaseEvent):
    """Content removed from platform."""

    type: Literal["moderation.removed"] = "moderation.removed"
    content_id: str
    user_id: str
    room_id: str
    reason: str
    appeal_available: bool = True


@EventRegistry.register
class ModerationReportEvent(BaseEvent):
    """Periodic moderation summary report."""

    type: Literal["moderation.report"] = "moderation.report"
    period_start: datetime
    period_end: datetime
    total_reviewed: int
    violations_by_type: dict[str, int]
    actions_taken: dict[str, int]
    top_flagged_users: list[str]


# =============================================================================
# User Reputation Tracking (simulated)
# =============================================================================

# In production, this would be in a database
USER_WARNINGS: dict[str, int] = {}
USER_VIOLATIONS: dict[str, list[str]] = {}


def get_user_warning_count(user_id: str) -> int:
    """Get current warning count for user."""
    return USER_WARNINGS.get(user_id, 0)


def increment_user_warning(user_id: str) -> int:
    """Increment and return new warning count."""
    USER_WARNINGS[user_id] = USER_WARNINGS.get(user_id, 0) + 1
    return USER_WARNINGS[user_id]


def record_user_violation(user_id: str, violation_type: str) -> None:
    """Record a violation for user history."""
    if user_id not in USER_VIOLATIONS:
        USER_VIOLATIONS[user_id] = []
    USER_VIOLATIONS[user_id].append(violation_type)


# =============================================================================
# AI-Powered Content Moderator
# =============================================================================

content_moderator = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=ReflexDeps,
    result_type=ModerationResult,
    system_prompt="""You are a content moderator for a community platform.

Analyze content for policy violations and determine appropriate action.

Violation types (from least to most severe):
- none: Content is acceptable
- spam: Repetitive, promotional, or off-topic
- harassment: Targeted attacks on individuals
- hate_speech: Discrimination based on protected characteristics
- violence: Threats or glorification of violence
- adult_content: Sexual or mature content
- misinformation: Demonstrably false claims that could cause harm
- self_harm: Content promoting self-harm or suicide
- illegal_activity: Content promoting illegal actions

Actions (escalating):
- approve: Content is fine
- warn: Minor issue, educate user
- remove: Remove content but no punishment
- shadow_ban: Hide content without notifying user
- ban: Remove and ban user
- escalate: Needs human review (edge cases)

Consider:
1. Context matters - "kill it" in gaming is different from threats
2. User history affects action severity
3. Severity 0.7+ with harassment/hate/violence → remove or ban
4. Repeat offenders get escalated actions
5. When uncertain, escalate to human review

Be fair but firm. Protect the community.""",
)


@content_moderator.tool
async def get_user_history(ctx: RunContext[ReflexDeps], user_id: str) -> str:
    """Get user's moderation history."""
    warnings = get_user_warning_count(user_id)
    violations = USER_VIOLATIONS.get(user_id, [])

    if not warnings and not violations:
        return f"User {user_id}: Clean record, no previous violations."

    return f"User {user_id}: {warnings} warnings, violations: {violations}"


@content_moderator.tool
async def check_spam_patterns(ctx: RunContext[ReflexDeps], content: str) -> str:
    """Check for common spam patterns."""
    spam_indicators = []

    # Check for excessive caps
    if len(content) > 10 and sum(1 for c in content if c.isupper()) / len(content) > 0.7:
        spam_indicators.append("excessive_caps")

    # Check for repeated characters
    for i in range(len(content) - 4):
        if len(set(content[i : i + 5])) == 1:
            spam_indicators.append("repeated_chars")
            break

    # Check for URLs (simplified)
    if "http" in content.lower() or "www." in content.lower():
        spam_indicators.append("contains_url")

    if spam_indicators:
        return f"Spam indicators found: {', '.join(spam_indicators)}"
    return "No spam patterns detected."


# =============================================================================
# Content Moderation Agent
# =============================================================================


async def moderate_content(ctx: AgentContext) -> dict:
    """Moderate submitted content using AI."""
    event: ContentSubmittedEvent = ctx.event

    # Use AI to analyze content
    try:
        result = await content_moderator.run(
            f"Category: {event.category}\nRoom: {event.room_id}\nContent: {event.content}",
            deps=ctx.deps,
        )
        decision = result.data
    except Exception as e:
        # On AI failure, escalate to human review
        decision = ModerationResult(
            violation_type=ViolationType.NONE,
            severity=0.0,
            confidence=0.0,
            action=ModerationAction.ESCALATE,
            reasoning=f"AI moderation failed: {e}",
        )

    # Publish moderation decision
    decision_event = ctx.derive_event(
        ModerationDecisionEvent,
        content_id=event.content_id,
        user_id=event.user_id,
        room_id=event.room_id,
        violation_type=decision.violation_type.value,
        severity=decision.severity,
        action=decision.action.value,
        reasoning=decision.reasoning,
        original_content=event.content[:200],  # Truncate for storage
    )
    await ctx.publish(decision_event)

    # Take action based on decision
    if decision.action == ModerationAction.WARN:
        warning_count = increment_user_warning(event.user_id)
        record_user_violation(event.user_id, decision.violation_type.value)

        warning = ctx.derive_event(
            UserWarningEvent,
            user_id=event.user_id,
            warning_type=decision.violation_type.value,
            message=f"Your message was flagged for {decision.violation_type.value}. "
            f"This is warning {warning_count}.",
            warning_count=warning_count,
        )
        await ctx.publish(warning)

        # Auto-escalate after 3 warnings
        if warning_count >= 3:
            decision = ModerationResult(
                violation_type=decision.violation_type,
                severity=decision.severity,
                confidence=decision.confidence,
                action=ModerationAction.BAN,
                reasoning=f"Auto-ban: {warning_count} warnings reached",
            )

    if decision.action == ModerationAction.REMOVE:
        record_user_violation(event.user_id, decision.violation_type.value)

        removed = ctx.derive_event(
            ContentRemovedEvent,
            content_id=event.content_id,
            user_id=event.user_id,
            room_id=event.room_id,
            reason=decision.reasoning,
        )
        await ctx.publish(removed)

    if decision.action in (ModerationAction.BAN, ModerationAction.SHADOW_BAN):
        record_user_violation(event.user_id, decision.violation_type.value)

        ban_type = "shadow" if decision.action == ModerationAction.SHADOW_BAN else "temporary"
        duration = 24 if decision.severity < 0.8 else None  # None = permanent

        ban = ctx.derive_event(
            UserBanEvent,
            user_id=event.user_id,
            room_id=event.room_id if decision.severity < 0.9 else None,
            ban_type=ban_type,
            duration_hours=duration,
            reason=decision.reasoning,
        )
        await ctx.publish(ban)

    return {
        "content_id": event.content_id,
        "action": decision.action.value,
        "violation": decision.violation_type.value,
        "severity": decision.severity,
        "confidence": decision.confidence,
    }


moderation_agent = SimpleAgent(moderate_content)


# =============================================================================
# Action Handlers
# =============================================================================


async def handle_content_removal(ctx: AgentContext) -> dict:
    """Handle content removal - notify user, update UI."""
    event: ContentRemovedEvent = ctx.event

    print(f"\n🗑️  [REMOVED] Content {event.content_id}")
    print(f"   User: {event.user_id}")
    print(f"   Room: {event.room_id}")
    print(f"   Reason: {event.reason}")

    # In production: send WebSocket message to remove from UI

    return {"removed": True, "content_id": event.content_id}


removal_handler = SimpleAgent(handle_content_removal)


async def handle_user_ban(ctx: AgentContext) -> dict:
    """Handle user ban - disconnect, notify."""
    event: UserBanEvent = ctx.event

    scope = f"room {event.room_id}" if event.room_id else "platform-wide"
    duration = f"{event.duration_hours}h" if event.duration_hours else "permanent"

    print(f"\n🚫 [BAN] User {event.user_id}")
    print(f"   Scope: {scope}")
    print(f"   Type: {event.ban_type} ({duration})")
    print(f"   Reason: {event.reason}")

    # In production: disconnect WebSocket, update user record

    return {"banned": True, "user_id": event.user_id}


ban_handler = SimpleAgent(handle_user_ban)


async def handle_warning(ctx: AgentContext) -> dict:
    """Handle user warning - notify user."""
    event: UserWarningEvent = ctx.event

    print(f"\n⚠️  [WARNING] User {event.user_id}")
    print(f"   Type: {event.warning_type}")
    print(f"   Count: {event.warning_count}/3")
    print(f"   Message: {event.message}")

    return {"warned": True, "user_id": event.user_id}


warning_handler = SimpleAgent(handle_warning)


# =============================================================================
# Report Generator
# =============================================================================


async def generate_moderation_report(ctx: AgentContext) -> dict:
    """Generate periodic moderation summary."""
    # In production, this would aggregate from database

    print("\n📊 [REPORT] Moderation Summary")
    print("   Period: Last hour")
    print(f"   Users with warnings: {len(USER_WARNINGS)}")
    print(f"   Total warnings issued: {sum(USER_WARNINGS.values())}")

    if USER_VIOLATIONS:
        print("   Violations by type:")
        violation_counts: dict[str, int] = {}
        for violations in USER_VIOLATIONS.values():
            for v in violations:
                violation_counts[v] = violation_counts.get(v, 0) + 1
        for vtype, count in sorted(violation_counts.items(), key=lambda x: -x[1]):
            print(f"     • {vtype}: {count}")

    return {"report_generated": True}


report_agent = SimpleAgent(generate_moderation_report)


# =============================================================================
# Trigger Registration
# =============================================================================


# Rate limit: max 10 messages per 60 seconds per user
# Dedupe: ignore duplicate messages within 30 seconds
content_filter = (
    type_filter("content.submitted")
    & rate_limit_filter(max_events=10, window_seconds=60)
    & dedupe_filter(
        key_func=lambda e: hashlib.sha256(f"{e.user_id}:{e.content}".encode()).hexdigest(),
        window_seconds=30,
    )
)


@trigger(
    name="content-moderator",
    filter=content_filter,
    trigger_func=immediate_trigger(),
    agent=moderation_agent,
    priority=20,
    scope_key=lambda e: f"room:{e.room_id}",
)
def moderation_trigger():
    """Moderate submitted content with AI and rate limiting."""
    pass


@trigger(
    name="removal-handler",
    filter=type_filter("moderation.removed"),
    trigger_func=immediate_trigger(),
    agent=removal_handler,
    priority=15,
)
def removal_trigger():
    """Handle content removal notifications."""
    pass


@trigger(
    name="ban-handler",
    filter=type_filter("moderation.ban"),
    trigger_func=immediate_trigger(),
    agent=ban_handler,
    priority=15,
)
def ban_trigger():
    """Handle user ban processing."""
    pass


@trigger(
    name="warning-handler",
    filter=type_filter("moderation.warning"),
    trigger_func=immediate_trigger(),
    agent=warning_handler,
    priority=10,
)
def warning_trigger():
    """Handle user warning notifications."""
    pass


@trigger(
    name="moderation-report",
    filter=type_filter("moderation.decision"),
    trigger_func=periodic_summary_trigger(
        event_count=100,  # Every 100 decisions
        max_interval_seconds=3600,  # Or every hour
    ),
    agent=report_agent,
    priority=1,
)
def report_trigger():
    """Generate periodic moderation reports."""
    pass


# =============================================================================
# Demo Runner
# =============================================================================


async def demo():
    """Run an interactive demonstration."""
    print("=" * 60)
    print("🛡️  Content Moderation Example")
    print("=" * 60)

    # Show registered components
    registry = get_registry()
    print(f"\nRegistered triggers: {len(registry.triggers)}")
    for t in registry.triggers:
        print(f"  • {t.name} (priority: {t.priority})")

    print("\nRegistered event types:")
    for name in EventRegistry.type_names():
        if "content" in name or "moderation" in name:
            print(f"  • {name}")

    # Simulate content moderation
    print("\n" + "-" * 60)
    print("Simulated Content Moderation:")
    print("-" * 60)

    sample_content = [
        ("user001", "room_general", "chat", "Hey everyone! How's it going?"),
        ("user002", "room_general", "chat", "Check out my store at spam-site.com!!!"),
        ("user003", "room_gaming", "chat", "GG! That was an amazing kill streak!"),
        ("user004", "room_general", "chat", "You're such an idiot, go away"),
        ("user001", "room_general", "chat", "Anyone want to play later?"),
        ("spammer", "room_general", "chat", "FREE MONEY FREE MONEY FREE MONEY"),
    ]

    for user_id, room_id, category, content in sample_content:
        print(f"\n📝 [{user_id}] in {room_id}: {content[:50]}...")
        event = ContentSubmittedEvent(
            source=f"ws:{user_id}",
            content_id=f"msg_{hash(content) % 10000:04d}",
            user_id=user_id,
            room_id=room_id,
            category=category,
            content=content,
        )
        print(f"   Event ID: {event.id}")

    print("\n" + "=" * 60)
    print("Filter Pipeline:")
    print("  1. Rate Limit: Max 10 msgs/user/minute (prevents spam floods)")
    print("  2. Deduplication: Ignore repeated messages within 30s")
    print("  3. AI Moderation: Classify content and take action")
    print()
    print("To run the full system:")
    print("  1. Start PostgreSQL: docker-compose up -d")
    print("  2. Run migrations: alembic upgrade head")
    print("  3. Start API: uvicorn reflex.api.app:app --reload")
    print("  4. Submit content via HTTP or WebSocket")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
