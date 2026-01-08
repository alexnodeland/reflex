"""Order Fraud Detection Example - E-commerce Fraud Prevention.

This example demonstrates an order fraud detection system that:
1. Receives order events from e-commerce platform
2. Analyzes orders for fraud signals using LLM
3. Uses tools to check user history, payment velocity, and geography
4. Takes action: approve, hold for review, or reject
5. Maintains event lineage for audit trails

Run with:
    python -m examples.fraud_detection.main

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


class FraudSignal(str, Enum):
    """Types of fraud signals."""

    HIGH_VELOCITY = "high_velocity"  # Many orders in short time
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"  # IP far from billing
    NEW_ACCOUNT = "new_account"  # Account created recently
    HIGH_VALUE = "high_value"  # Unusually large order
    MISMATCHED_INFO = "mismatched_info"  # Shipping != billing
    KNOWN_FRAUD_PATTERN = "known_fraud_pattern"
    SUSPICIOUS_ITEMS = "suspicious_items"  # High-risk products
    NONE = "none"


class FraudDecision(str, Enum):
    """Fraud review decisions."""

    APPROVE = "approve"
    HOLD = "hold"  # Manual review needed
    REJECT = "reject"
    CHALLENGE = "challenge"  # 3DS or verification needed


class FraudAnalysisResult(BaseModel):
    """LLM fraud analysis output."""

    risk_score: float = Field(ge=0.0, le=1.0)
    signals_detected: list[FraudSignal]
    decision: FraudDecision
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: str


# =============================================================================
# Custom Event Types
# =============================================================================


@EventRegistry.register
class OrderCreatedEvent(BaseEvent):
    """New order submitted."""

    type: Literal["order.created"] = "order.created"
    order_id: str
    user_id: str
    email: str
    total_amount: float
    currency: str
    items: list[dict]  # [{sku, name, quantity, price}]
    shipping_address: dict  # {country, city, zip, street}
    billing_address: dict
    payment_method: str  # "card", "paypal", "crypto"
    ip_address: str
    user_agent: str


@EventRegistry.register
class FraudCheckEvent(BaseEvent):
    """Fraud analysis result."""

    type: Literal["order.fraud_check"] = "order.fraud_check"
    order_id: str
    user_id: str
    risk_score: float
    signals: list[str]
    decision: str
    reasoning: str
    confidence: float


@EventRegistry.register
class OrderApprovedEvent(BaseEvent):
    """Order approved for processing."""

    type: Literal["order.approved"] = "order.approved"
    order_id: str
    user_id: str
    fraud_check_id: str
    processing_notes: str


@EventRegistry.register
class OrderHeldEvent(BaseEvent):
    """Order held for manual review."""

    type: Literal["order.held"] = "order.held"
    order_id: str
    user_id: str
    fraud_check_id: str
    hold_reason: str
    review_priority: str  # "low", "medium", "high"


@EventRegistry.register
class OrderRejectedEvent(BaseEvent):
    """Order rejected due to fraud."""

    type: Literal["order.rejected"] = "order.rejected"
    order_id: str
    user_id: str
    fraud_check_id: str
    rejection_reason: str
    notify_user: bool


@EventRegistry.register
class UserFlaggedEvent(BaseEvent):
    """User flagged for suspicious activity."""

    type: Literal["user.flagged"] = "user.flagged"
    user_id: str
    flag_reason: str
    flag_level: str  # "watch", "restricted", "blocked"
    related_order_ids: list[str]


# =============================================================================
# User History Simulation
# =============================================================================

USER_ORDER_HISTORY: dict[str, list[dict]] = {
    "user_trusted": [
        {"order_id": "ord_001", "amount": 150.0, "status": "completed"},
        {"order_id": "ord_002", "amount": 75.0, "status": "completed"},
        {"order_id": "ord_003", "amount": 200.0, "status": "completed"},
    ],
    "user_new": [],
    "user_suspicious": [
        {"order_id": "ord_100", "amount": 500.0, "status": "rejected"},
        {"order_id": "ord_101", "amount": 450.0, "status": "held"},
    ],
}

USER_ACCOUNT_AGE: dict[str, int] = {
    "user_trusted": 365,  # Days
    "user_new": 1,
    "user_suspicious": 7,
}

RECENT_ORDERS: dict[str, list[str]] = {}  # user_id -> [order_ids in last hour]


def record_order(user_id: str, order_id: str) -> int:
    """Record order and return count in last hour."""
    if user_id not in RECENT_ORDERS:
        RECENT_ORDERS[user_id] = []
    RECENT_ORDERS[user_id].append(order_id)
    return len(RECENT_ORDERS[user_id])


def get_order_velocity(user_id: str) -> int:
    """Get number of orders in the last hour."""
    return len(RECENT_ORDERS.get(user_id, []))


# =============================================================================
# AI-Powered Fraud Analyzer
# =============================================================================

fraud_analyzer = Agent(
    "anthropic:claude-sonnet-4-20250514",
    deps_type=ReflexDeps,
    result_type=FraudAnalysisResult,
    system_prompt="""You are a fraud analyst for an e-commerce platform.

Analyze orders for fraud signals and make a decision:
- APPROVE: Low risk, proceed with order
- HOLD: Medium risk, needs manual review
- REJECT: High risk, likely fraudulent
- CHALLENGE: Request additional verification (3DS, email confirm)

Risk signals to check:
1. HIGH_VELOCITY: More than 3 orders in an hour is suspicious
2. GEOGRAPHIC_ANOMALY: IP location far from billing address
3. NEW_ACCOUNT: Account less than 7 days old with large order
4. HIGH_VALUE: Order > $500 for accounts with no history
5. MISMATCHED_INFO: Shipping address very different from billing
6. SUSPICIOUS_ITEMS: High-resale items (electronics, gift cards)

Decision guidelines:
- Score < 0.3: APPROVE
- Score 0.3-0.6: CHALLENGE or HOLD based on signals
- Score 0.6-0.8: HOLD for review
- Score > 0.8: REJECT

Use the tools to gather user history before making a decision.
Be firm but fair - false positives hurt legitimate customers.""",
)


@fraud_analyzer.tool
async def get_user_order_history(ctx: RunContext[ReflexDeps], user_id: str) -> str:
    """Get user's order history."""
    history = USER_ORDER_HISTORY.get(user_id, [])
    if not history:
        return f"User {user_id}: No previous orders (new customer)."

    total = sum(o["amount"] for o in history)
    completed = sum(1 for o in history if o["status"] == "completed")
    rejected = sum(1 for o in history if o["status"] == "rejected")

    return (
        f"User {user_id} history:\n"
        f"  Total orders: {len(history)}\n"
        f"  Completed: {completed}, Rejected: {rejected}\n"
        f"  Lifetime value: ${total:.2f}"
    )


@fraud_analyzer.tool
async def get_user_account_age(ctx: RunContext[ReflexDeps], user_id: str) -> str:
    """Get user's account age in days."""
    age = USER_ACCOUNT_AGE.get(user_id, 0)
    if age == 0:
        return f"User {user_id}: Account not found or just created."
    return f"User {user_id}: Account is {age} days old."


@fraud_analyzer.tool
async def check_order_velocity(ctx: RunContext[ReflexDeps], user_id: str) -> str:
    """Check how many orders user has placed recently."""
    count = get_order_velocity(user_id)
    if count == 0:
        return f"User {user_id}: No recent orders in the last hour."
    return f"User {user_id}: {count} order(s) in the last hour."


@fraud_analyzer.tool
async def check_ip_location(ctx: RunContext[ReflexDeps], ip_address: str) -> str:
    """Get approximate location for IP address."""
    # Simulated IP geolocation
    ip_locations = {
        "192.168.1.1": "New York, US",
        "10.0.0.1": "London, UK",
        "172.16.0.1": "Lagos, NG",
        "8.8.8.8": "Mountain View, US",
    }
    location = ip_locations.get(ip_address, "Unknown location")
    return f"IP {ip_address} is located in: {location}"


# =============================================================================
# Fraud Detection Agent
# =============================================================================


async def analyze_order_fraud(ctx: AgentContext) -> dict:
    """Analyze order for fraud using LLM."""
    event: OrderCreatedEvent = ctx.event

    # Record this order for velocity tracking
    record_order(event.user_id, event.order_id)

    # Build context for LLM
    items_desc = ", ".join(f"{i['name']} (${i['price']})" for i in event.items[:5])
    context = f"""
Order Details:
  Order ID: {event.order_id}
  User ID: {event.user_id}
  Email: {event.email}
  Amount: ${event.total_amount:.2f} {event.currency}
  Items: {items_desc}
  Payment: {event.payment_method}
  IP: {event.ip_address}
  Shipping: {event.shipping_address.get("city")}, {event.shipping_address.get("country")}
  Billing: {event.billing_address.get("city")}, {event.billing_address.get("country")}
"""

    try:
        result = await fraud_analyzer.run(
            f"Analyze this order for fraud:\n{context}",
            deps=ctx.deps,
        )
        analysis = result.data
    except Exception as e:
        # On AI failure, hold for manual review
        analysis = FraudAnalysisResult(
            risk_score=0.5,
            signals_detected=[],
            decision=FraudDecision.HOLD,
            reasoning=f"AI analysis failed: {e}",
            confidence=0.0,
            recommended_action="Manual review required due to system error",
        )

    # Publish fraud check result
    fraud_check = ctx.derive_event(
        FraudCheckEvent,
        order_id=event.order_id,
        user_id=event.user_id,
        risk_score=analysis.risk_score,
        signals=[s.value for s in analysis.signals_detected],
        decision=analysis.decision.value,
        reasoning=analysis.reasoning,
        confidence=analysis.confidence,
    )
    await ctx.publish(fraud_check)

    print(f"\n🔍 [FRAUD CHECK] Order {event.order_id}")
    print(f"   Risk Score: {analysis.risk_score:.0%}")
    print(f"   Decision: {analysis.decision.value.upper()}")
    print(f"   Signals: {[s.value for s in analysis.signals_detected]}")
    print(f"   Confidence: {analysis.confidence:.0%}")

    return {
        "order_id": event.order_id,
        "risk_score": analysis.risk_score,
        "decision": analysis.decision.value,
        "fraud_check_id": fraud_check.id,
    }


fraud_detection_agent = SimpleAgent(analyze_order_fraud)


# =============================================================================
# Decision Handlers
# =============================================================================


async def handle_fraud_decision(ctx: AgentContext) -> dict:
    """Process fraud check decision."""
    event: FraudCheckEvent = ctx.event

    if event.decision == FraudDecision.APPROVE.value:
        approved = ctx.derive_event(
            OrderApprovedEvent,
            order_id=event.order_id,
            user_id=event.user_id,
            fraud_check_id=event.id,
            processing_notes=f"Auto-approved. Risk: {event.risk_score:.0%}",
        )
        await ctx.publish(approved)
        print(f"\n✅ [APPROVED] Order {event.order_id}")
        return {"action": "approved", "order_id": event.order_id}

    elif event.decision == FraudDecision.HOLD.value:
        priority = "high" if event.risk_score > 0.7 else "medium"
        held = ctx.derive_event(
            OrderHeldEvent,
            order_id=event.order_id,
            user_id=event.user_id,
            fraud_check_id=event.id,
            hold_reason=event.reasoning,
            review_priority=priority,
        )
        await ctx.publish(held)
        print(f"\n⏸️  [HELD] Order {event.order_id} - Priority: {priority}")
        return {"action": "held", "order_id": event.order_id, "priority": priority}

    elif event.decision == FraudDecision.REJECT.value:
        rejected = ctx.derive_event(
            OrderRejectedEvent,
            order_id=event.order_id,
            user_id=event.user_id,
            fraud_check_id=event.id,
            rejection_reason=event.reasoning,
            notify_user=event.risk_score < 0.95,  # Don't notify obvious fraud
        )
        await ctx.publish(rejected)

        # Flag user if high risk
        if event.risk_score > 0.8:
            flagged = ctx.derive_event(
                UserFlaggedEvent,
                user_id=event.user_id,
                flag_reason=f"High-risk order rejected: {event.reasoning}",
                flag_level="restricted" if event.risk_score > 0.9 else "watch",
                related_order_ids=[event.order_id],
            )
            await ctx.publish(flagged)

        print(f"\n❌ [REJECTED] Order {event.order_id}")
        return {"action": "rejected", "order_id": event.order_id}

    else:  # CHALLENGE
        held = ctx.derive_event(
            OrderHeldEvent,
            order_id=event.order_id,
            user_id=event.user_id,
            fraud_check_id=event.id,
            hold_reason=f"Verification required: {event.reasoning}",
            review_priority="medium",
        )
        await ctx.publish(held)
        print(f"\n🔐 [CHALLENGE] Order {event.order_id} - Verification needed")
        return {"action": "challenge", "order_id": event.order_id}


decision_handler = SimpleAgent(handle_fraud_decision)


# =============================================================================
# User Flag Handler
# =============================================================================


async def handle_user_flag(ctx: AgentContext) -> dict:
    """Handle user flagging for fraud watch."""
    event: UserFlaggedEvent = ctx.event

    print(f"\n🚩 [USER FLAGGED] {event.user_id}")
    print(f"   Level: {event.flag_level.upper()}")
    print(f"   Reason: {event.flag_reason}")
    print(f"   Related orders: {event.related_order_ids}")

    # In production: update user record, notify fraud team

    return {"flagged": True, "user_id": event.user_id, "level": event.flag_level}


flag_handler = SimpleAgent(handle_user_flag)


# =============================================================================
# Trigger Registration
# =============================================================================


@trigger(
    name="fraud-analyzer",
    filter=type_filter("order.created"),
    trigger_func=immediate_trigger(),
    agent=fraud_detection_agent,
    priority=20,
    scope_key=lambda e: f"user:{e.user_id}",  # Serialize per user
)
def fraud_analysis_trigger():
    """Analyze new orders for fraud - serialized per user."""
    pass


@trigger(
    name="fraud-decision-handler",
    filter=type_filter("order.fraud_check"),
    trigger_func=immediate_trigger(),
    agent=decision_handler,
    priority=15,
)
def decision_trigger():
    """Process fraud check decisions."""
    pass


@trigger(
    name="user-flag-handler",
    filter=type_filter("user.flagged"),
    trigger_func=immediate_trigger(),
    agent=flag_handler,
    priority=10,
)
def flag_trigger():
    """Handle user flagging."""
    pass


# =============================================================================
# Demo Runner
# =============================================================================


async def demo():
    """Run an interactive demonstration."""
    print("=" * 60)
    print("🛡️  Order Fraud Detection Example")
    print("=" * 60)

    # Show registered components
    registry = get_registry()
    print(f"\nRegistered triggers: {len(registry.triggers)}")
    for t in registry.triggers:
        print(f"  • {t.name} (priority: {t.priority})")

    print("\nRegistered event types:")
    for name in EventRegistry.type_names():
        if "order" in name or "user" in name:
            print(f"  • {name}")

    # Simulate orders
    print("\n" + "-" * 60)
    print("Simulated Order Flow:")
    print("-" * 60)

    sample_orders = [
        {
            "order_id": "ord_10001",
            "user_id": "user_trusted",
            "email": "trusted@example.com",
            "total_amount": 89.99,
            "items": [{"name": "Book", "price": 29.99}],
            "shipping": {"city": "New York", "country": "US"},
            "billing": {"city": "New York", "country": "US"},
            "ip": "192.168.1.1",
        },
        {
            "order_id": "ord_10002",
            "user_id": "user_new",
            "email": "newuser@temp.com",
            "total_amount": 1299.99,
            "items": [{"name": "iPhone", "price": 999.99}],
            "shipping": {"city": "Lagos", "country": "NG"},
            "billing": {"city": "New York", "country": "US"},
            "ip": "172.16.0.1",
        },
        {
            "order_id": "ord_10003",
            "user_id": "user_suspicious",
            "email": "suspicious@example.com",
            "total_amount": 499.99,
            "items": [{"name": "Gift Card", "price": 499.99}],
            "shipping": {"city": "London", "country": "UK"},
            "billing": {"city": "London", "country": "UK"},
            "ip": "10.0.0.1",
        },
    ]

    for order in sample_orders:
        print(f"\n📦 Order {order['order_id']}")
        print(f"   User: {order['user_id']}")
        print(f"   Amount: ${order['total_amount']}")
        print(f"   Items: {order['items'][0]['name']}")
        print(f"   Ship to: {order['shipping']['city']}, {order['shipping']['country']}")

        event = OrderCreatedEvent(
            source=f"checkout:{order['user_id']}",
            order_id=order["order_id"],
            user_id=order["user_id"],
            email=order["email"],
            total_amount=order["total_amount"],
            currency="USD",
            items=order["items"],
            shipping_address=order["shipping"],
            billing_address=order["billing"],
            payment_method="card",
            ip_address=order["ip"],
            user_agent="Mozilla/5.0",
        )
        print(f"   Event ID: {event.id}")

    print("\n" + "=" * 60)
    print("Fraud Detection Flow:")
    print("  1. OrderCreatedEvent received")
    print("  2. Fraud analyzer checks user history, velocity, geography")
    print("  3. LLM assigns risk score and decision")
    print("  4. FraudCheckEvent published")
    print("  5. Decision handler: approve/hold/reject/challenge")
    print("  6. High-risk users flagged for monitoring")
    print()
    print("Key Feature: scope_key=user:{user_id}")
    print("  → Orders from same user processed sequentially")
    print("  → Prevents race conditions in velocity checks")
    print()
    print("To run the full system:")
    print("  1. Start PostgreSQL: docker-compose up -d")
    print("  2. Run migrations: alembic upgrade head")
    print("  3. Start API: uvicorn reflex.api.app:app --reload")
    print("  4. POST orders to /events")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
