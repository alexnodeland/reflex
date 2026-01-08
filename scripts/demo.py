#!/usr/bin/env python
"""Interactive demo script for Reflex.

Demonstrates the event-driven architecture with real-time WebSocket communication.

Usage:
    python scripts/demo.py           # Run full demo
    python scripts/demo.py --ws      # Interactive WebSocket mode

Requires the server to be running (make dev).
"""

import argparse
import asyncio
import sys

import httpx

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/demo-client"


async def check_health() -> bool:
    """Check if the server is running."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_URL}/health", timeout=5.0)
            return resp.status_code == 200
        except httpx.ConnectError:
            return False


async def publish_event(client: httpx.AsyncClient, event: dict) -> dict:
    """Publish an event to the server."""
    resp = await client.post(f"{API_URL}/events", json=event, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def get_health_detailed() -> dict:
    """Get detailed health status."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/health/detailed", timeout=5.0)
        return resp.json()


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


async def demo_http_api():
    """Demo: HTTP API for publishing events."""
    print_header("HTTP Event Publishing")

    async with httpx.AsyncClient() as client:
        # WebSocket event
        event = {
            "type": "ws.message",
            "source": "demo:http-client",
            "connection_id": "demo-001",
            "content": "Hello from HTTP API!",
        }
        print(f"\n  POST /events")
        print(f"  Type: {event['type']}")
        print(f"  Content: {event['content']}")

        result = await publish_event(client, event)
        print(f"  ✓ Published: {result['id'][:8]}...")

        # HTTP event
        event = {
            "type": "http.request",
            "source": "demo:webhook",
            "method": "POST",
            "path": "/webhook/stripe",
            "headers": {"Stripe-Signature": "t=123,v1=abc"},
            "body": {"type": "payment.succeeded", "amount": 9900},
        }
        print(f"\n  POST /events")
        print(f"  Type: {event['type']}")
        print(f"  Simulating: {event['method']} {event['path']}")

        result = await publish_event(client, event)
        print(f"  ✓ Published: {result['id'][:8]}...")


async def demo_websocket():
    """Demo: WebSocket real-time communication."""
    print_header("WebSocket Real-Time Events")

    try:
        import websockets
    except ImportError:
        print("\n  [!] Install websockets for this demo: pip install websockets")
        print("  Skipping WebSocket demo...")
        return

    print(f"\n  Connecting to {WS_URL}...")

    try:
        import json

        async with websockets.connect(WS_URL) as ws:
            print("  ✓ Connected!")

            # Send messages (must be JSON with "content" field)
            messages = [
                "First real-time message",
                "Second message with data: {'key': 'value'}",
                "Third message - demonstrating streaming",
            ]

            for i, msg in enumerate(messages, 1):
                print(f"\n  → Sending: {msg[:40]}...")
                await ws.send(json.dumps({"content": msg}))

                # Brief pause to show real-time nature
                await asyncio.sleep(0.3)

                # Check for response (non-blocking)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(response)
                    if "ack" in data:
                        print(f"  ← Ack: {data['ack'][:8]}...")
                    else:
                        print(f"  ← Response: {response[:50]}...")
                except asyncio.TimeoutError:
                    print("  (event queued for processing)")

            print("\n  ✓ WebSocket demo complete")

    except Exception as e:
        print(f"  [!] WebSocket error: {e}")
        print("  Make sure the server is running with: make dev")


async def demo_event_burst():
    """Demo: High-throughput event publishing."""
    print_header("Event Burst (Throughput Demo)")

    count = 20
    print(f"\n  Publishing {count} events rapidly...")

    async with httpx.AsyncClient() as client:
        start = asyncio.get_event_loop().time()

        tasks = []
        for i in range(count):
            event = {
                "type": "ws.message",
                "source": f"demo:burst-{i:03d}",
                "connection_id": f"burst-{i:03d}",
                "content": f"Burst event #{i + 1}",
            }
            tasks.append(publish_event(client, event))

        results = await asyncio.gather(*tasks)
        elapsed = asyncio.get_event_loop().time() - start

        print(f"  ✓ Published {len(results)} events in {elapsed:.2f}s")
        print(f"  Throughput: {len(results) / elapsed:.1f} events/sec")


async def show_system_status():
    """Show current system status."""
    print_header("System Status")

    health = await get_health_detailed()

    print(f"\n  Overall: {health['status'].upper()}")
    print()

    for indicator in health["indicators"]:
        status = "✓" if indicator["status"] == "healthy" else "✗"
        name = indicator["name"].ljust(12)
        message = indicator.get("message") or ""
        latency = indicator.get("latency_ms")
        latency_str = f" ({latency:.1f}ms)" if latency else ""
        print(f"  {status} {name} {message}{latency_str}")


async def interactive_websocket():
    """Interactive WebSocket mode - type messages to send."""
    print_header("Interactive WebSocket Mode")
    print("\n  Type messages to send. Press Ctrl+C to exit.\n")

    try:
        import websockets
    except ImportError:
        print("  [!] Install websockets: pip install websockets")
        return

    import json

    try:
        async with websockets.connect(WS_URL) as ws:
            print(f"  Connected to {WS_URL}")
            print("  " + "─" * 40)

            async def receiver():
                try:
                    async for message in ws:
                        data = json.loads(message)
                        if "ack" in data:
                            print(f"\n  ← Ack: {data['ack'][:8]}...")
                        elif "error" in data:
                            print(f"\n  ← Error: {data['error']}")
                        else:
                            print(f"\n  ← {message}")
                        print("  > ", end="", flush=True)
                except websockets.ConnectionClosed:
                    pass

            # Start receiver task
            recv_task = asyncio.create_task(receiver())

            try:
                while True:
                    print("  > ", end="", flush=True)
                    # Read from stdin in executor to not block
                    loop = asyncio.get_event_loop()
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    line = line.strip()

                    if line:
                        await ws.send(json.dumps({"content": line}))
                        print(f"  → Sent: {line}")

            except (KeyboardInterrupt, EOFError):
                print("\n\n  Disconnecting...")
                recv_task.cancel()

    except Exception as e:
        print(f"  [!] Error: {e}")


async def main():
    """Run the demo."""
    parser = argparse.ArgumentParser(description="Reflex Demo Script")
    parser.add_argument("--ws", action="store_true", help="Interactive WebSocket mode")
    args = parser.parse_args()

    print("═" * 50)
    print("  REFLEX DEMO")
    print("  Real-time Event-Driven AI Agent Framework")
    print("═" * 50)

    # Check server
    print("\nConnecting to server...")
    if not await check_health():
        print(f"✗ Server not running at {API_URL}")
        print("  Start it with: make dev")
        sys.exit(1)
    print("✓ Server is healthy")

    if args.ws:
        await interactive_websocket()
    else:
        # Show initial status
        await show_system_status()

        # Run demos
        await demo_http_api()
        await demo_websocket()
        await demo_event_burst()

        # Show final status
        await asyncio.sleep(0.5)
        await show_system_status()

        print("\n" + "═" * 50)
        print("  Demo complete!")
        print()
        print("  Try interactive mode:")
        print("    python scripts/demo.py --ws")
        print()
        print("  Or use wscat:")
        print("    wscat -c ws://localhost:8000/ws/my-client")
        print("═" * 50)


if __name__ == "__main__":
    asyncio.run(main())
