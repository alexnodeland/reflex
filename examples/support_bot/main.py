"""Customer Support Bot Example - AI-Powered Support with Escalation.

This example demonstrates a real-time customer support system that:
1. Receives chat messages via WebSocket
2. Classifies customer intent using an LLM agent
3. Responds to simple queries automatically
4. Escalates complex issues to human agents
5. Tracks conversation state and handles timeouts

Run with:
    python -m examples.support_bot.main

Or start the API server:
    uvicorn reflex.api.app:app --reload
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from reflex import (
    AgentContext,
    BaseEvent,
    EventRegistry,
    ReflexDeps,
    SimpleAgent,
    get_registry,
    immediate_trigger,
    trigger,
    type_filter,
)

# =============================================================================
# Enums and Models
# =============================================================================


class IntentType(str, Enum):
    """Customer intent classification."""

    GREETING = "greeting"
    FAQ = "faq"
    ORDER_STATUS = "order_status"
    TECHNICAL_ISSUE = "technical_issue"
    BILLING = "billing"
    COMPLAINT = "complaint"
    ESCALATION_REQUEST = "escalation_request"
    UNKNOWN = "unknown"


class ConversationStatus(str, Enum):
    """Conversation state."""

    ACTIVE = "active"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    TIMED_OUT = "timed_out"


class ClassificationResult(BaseModel):
    """LLM classification output."""

    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human: bool = False
    suggested_response: str
    reasoning: str


# =============================================================================
# Custom Event Types
# =============================================================================


@EventRegistry.register
class ChatMessageEvent(BaseEvent):
    """Incoming customer chat message."""

    type: Literal["chat.message"] = "chat.message"
    conversation_id: str
    user_id: str
    message: str
    is_customer: bool = True


@EventRegistry.register
class BotResponseEvent(BaseEvent):
    """Bot response to customer."""

    type: Literal["chat.bot_response"] = "chat.bot_response"
    conversation_id: str
    user_id: str
    message: str
    intent_detected: str
    confidence: float


@EventRegistry.register
class EscalationEvent(BaseEvent):
    """Escalation to human agent."""

    type: Literal["support.escalation"] = "support.escalation"
    conversation_id: str
    user_id: str
    reason: str
    priority: str  # "low", "medium", "high", "urgent"
    context_summary: str
    recent_messages: list[str]


@EventRegistry.register
class EscalationTimeoutEvent(BaseEvent):
    """Escalation not acknowledged in time."""

    type: Literal["support.escalation_timeout"] = "support.escalation_timeout"
    conversation_id: str
    escalation_id: str
    wait_time_seconds: int


@EventRegistry.register
class ConversationResolvedEvent(BaseEvent):
    """Conversation marked as resolved."""

    type: Literal["support.resolved"] = "support.resolved"
    conversation_id: str
    user_id: str
    resolution_type: str  # "bot_handled", "human_resolved", "customer_left"
    satisfaction_score: int | None = None


# =============================================================================
# FAQ Knowledge Base (simulated)
# =============================================================================

FAQ_RESPONSES = {
    "shipping": "Standard shipping takes 3-5 business days. Express shipping is 1-2 days.",
    "returns": "You can return items within 30 days. Visit example.com/returns",
    "hours": "Our support team is available 24/7 via chat, or call Mon-Fri 9am-6pm EST.",
    "payment": "We accept Visa, Mastercard, PayPal, and Apple Pay.",
    "cancel": "To cancel an order, please provide your order number and I'll help you.",
}


# =============================================================================
# AI-Powered Intent Classification Agent
# =============================================================================

intent_classifier = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=ReflexDeps,
    result_type=ClassificationResult,
    system_prompt="""You are a customer support intent classifier for an e-commerce company.

Analyze the customer message and determine:
1. The primary intent (greeting, faq, order_status, technical_issue, billing,
   complaint, escalation_request, unknown)
2. Your confidence level (0.0 to 1.0)
3. Whether a human agent is needed (complex issues, complaints, billing disputes)
4. A suggested response

Guidelines:
- Greetings: Be warm and helpful
- FAQ: Answer directly if you know the answer
- Order status: Ask for order number if not provided
- Technical issues: Gather details, escalate if complex
- Billing: Always escalate billing disputes to humans
- Complaints: Acknowledge, apologize, escalate if serious
- Escalation requests: Always honor explicit requests for human agents

Be concise but helpful. Never make up order information.""",
)


@intent_classifier.tool
async def lookup_faq(ctx: RunContext[ReflexDeps], topic: str) -> str:
    """Look up FAQ information for common topics."""
    topic_lower = topic.lower()
    for key, response in FAQ_RESPONSES.items():
        if key in topic_lower:
            return response
    return "No FAQ found for this topic. Consider escalating to a human agent."


@intent_classifier.tool
async def get_conversation_history(
    ctx: RunContext[ReflexDeps],
    conversation_id: str,
    limit: int = 5,
) -> str:
    """Get recent messages from the conversation."""
    # In production, this would query the event store
    return f"[Simulated] Last {limit} messages for conversation {conversation_id}"


# =============================================================================
# Support Bot Agent
# =============================================================================


async def handle_chat_message(ctx: AgentContext) -> dict:
    """Process incoming chat messages and respond or escalate."""
    event: ChatMessageEvent = ctx.event
    message = event.message.strip()

    # Skip bot messages
    if not event.is_customer:
        return {"skipped": True, "reason": "Not a customer message"}

    # Use AI to classify intent and generate response
    try:
        result = await intent_classifier.run(
            f"Customer message: {message}",
            deps=ctx.deps,
        )
        classification = result.data
    except Exception as e:
        # Fallback on AI failure - escalate to human
        classification = ClassificationResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            requires_human=True,
            suggested_response="I'm having trouble. Let me connect you with a team member.",
            reasoning=f"AI classification failed: {e}",
        )

    # Determine if escalation is needed
    should_escalate = (
        classification.requires_human
        or classification.intent == IntentType.ESCALATION_REQUEST
        or classification.intent == IntentType.COMPLAINT
        or classification.confidence < 0.5
    )

    if should_escalate:
        # Create escalation event
        priority = "high" if classification.intent == IntentType.COMPLAINT else "medium"
        if classification.intent == IntentType.ESCALATION_REQUEST:
            priority = "high"

        escalation = ctx.derive_event(
            EscalationEvent,
            conversation_id=event.conversation_id,
            user_id=event.user_id,
            reason=classification.reasoning,
            priority=priority,
            context_summary=f"Intent: {classification.intent.value}, "
            f"Confidence: {classification.confidence}",
            recent_messages=[message],
        )
        await ctx.publish(escalation)

        # Still send a response to the customer
        response = ctx.derive_event(
            BotResponseEvent,
            conversation_id=event.conversation_id,
            user_id=event.user_id,
            message="I'm connecting you with a specialist who can better assist. Please hold.",
            intent_detected=classification.intent.value,
            confidence=classification.confidence,
        )
        await ctx.publish(response)

        return {
            "action": "escalated",
            "intent": classification.intent.value,
            "priority": priority,
            "escalation_id": escalation.id,
        }

    # Send bot response
    response = ctx.derive_event(
        BotResponseEvent,
        conversation_id=event.conversation_id,
        user_id=event.user_id,
        message=classification.suggested_response,
        intent_detected=classification.intent.value,
        confidence=classification.confidence,
    )
    await ctx.publish(response)

    return {
        "action": "responded",
        "intent": classification.intent.value,
        "confidence": classification.confidence,
    }


support_bot_agent = SimpleAgent(handle_chat_message)


# =============================================================================
# Escalation Handler Agent
# =============================================================================


async def handle_escalation(ctx: AgentContext) -> dict:
    """Process escalation events - notify human agents."""
    event: EscalationEvent = ctx.event

    print(f"\n🚨 [ESCALATION] Priority: {event.priority.upper()}")
    print(f"   Conversation: {event.conversation_id}")
    print(f"   User: {event.user_id}")
    print(f"   Reason: {event.reason}")
    print(f"   Context: {event.context_summary}")

    # In production, this would:
    # - Send notification to agent queue
    # - Update CRM system
    # - Start escalation timer

    return {
        "notified": True,
        "escalation_id": event.id,
        "priority": event.priority,
    }


escalation_agent = SimpleAgent(handle_escalation)


# =============================================================================
# Response Logger Agent (for demo visibility)
# =============================================================================


async def log_bot_response(ctx: AgentContext) -> dict:
    """Log bot responses for demo visibility."""
    event: BotResponseEvent = ctx.event

    print(f"\n🤖 [BOT] To: {event.user_id}")
    print(f"   Intent: {event.intent_detected} (confidence: {event.confidence:.0%})")
    print(f"   Message: {event.message}")

    return {"logged": True}


response_logger = SimpleAgent(log_bot_response)


# =============================================================================
# Trigger Registration
# =============================================================================


@trigger(
    name="support-bot",
    filter=type_filter("chat.message"),
    trigger_func=immediate_trigger(),
    agent=support_bot_agent,
    priority=10,
    scope_key=lambda e: f"conversation:{e.conversation_id}",
)
def support_bot_trigger():
    """Handle incoming chat messages with AI-powered support bot."""
    pass


@trigger(
    name="escalation-handler",
    filter=type_filter("support.escalation"),
    trigger_func=immediate_trigger(),
    agent=escalation_agent,
    priority=20,
)
def escalation_trigger():
    """Process escalation events."""
    pass


@trigger(
    name="response-logger",
    filter=type_filter("chat.bot_response"),
    trigger_func=immediate_trigger(),
    agent=response_logger,
    priority=1,
)
def response_log_trigger():
    """Log all bot responses."""
    pass


# =============================================================================
# Demo Runner
# =============================================================================


async def demo():
    """Run an interactive demonstration."""
    print("=" * 60)
    print("🎧 Customer Support Bot Example")
    print("=" * 60)

    # Show registered components
    registry = get_registry()
    print(f"\nRegistered triggers: {len(registry.triggers)}")
    for t in registry.triggers:
        print(f"  • {t.name} (priority: {t.priority})")

    print("\nRegistered event types:")
    for name in EventRegistry.type_names():
        if "chat" in name or "support" in name:
            print(f"  • {name}")

    # Simulate conversation
    print("\n" + "-" * 60)
    print("Simulated Conversation Flow:")
    print("-" * 60)

    sample_messages = [
        ("user123", "conv001", "Hi there!"),
        ("user123", "conv001", "What's your return policy?"),
        ("user456", "conv002", "My order hasn't arrived and it's been 2 weeks!"),
        ("user789", "conv003", "I want to speak to a human please"),
        ("user123", "conv001", "Can you check order #12345?"),
    ]

    for user_id, conv_id, message in sample_messages:
        print(f"\n📨 [{user_id}] {message}")
        event = ChatMessageEvent(
            source=f"ws:{user_id}",
            conversation_id=conv_id,
            user_id=user_id,
            message=message,
        )
        print(f"   Event ID: {event.id}")
        print(f"   Timestamp: {event.timestamp}")

    print("\n" + "=" * 60)
    print("To run the full system:")
    print("  1. Start PostgreSQL: docker-compose up -d")
    print("  2. Run migrations: alembic upgrade head")
    print("  3. Start API: uvicorn reflex.api.app:app --reload")
    print("  4. Connect via WebSocket: ws://localhost:8000/ws/<user_id>")
    print('  5. Send messages: {"content": "Hello!"}')
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
