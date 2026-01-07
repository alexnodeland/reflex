"""WebSocket endpoint for real-time event streaming.

Provides a WebSocket endpoint for clients to send messages
that are published as events.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from reflex.core.events import WebSocketEvent

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


class WebSocketMessage(BaseModel):
    """Expected message format from WebSocket clients."""

    content: str


class WebSocketAck(BaseModel):
    """Acknowledgment sent back to clients."""

    ack: str


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
) -> None:
    """WebSocket endpoint for real-time messaging.

    Accepts a WebSocket connection, receives messages, publishes them
    as WebSocketEvents, and sends acknowledgments back to the client.

    Protocol:
        Client → Server: {"content": "message text"}
        Server → Client: {"ack": "event_id"}

    Args:
        websocket: The WebSocket connection
        client_id: Unique identifier for this client
    """
    await websocket.accept()
    logger.info("WebSocket connected: client_id=%s", client_id)

    # Get the store from app state
    store = websocket.app.state.store

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            try:
                # Validate message format
                message = WebSocketMessage.model_validate(data)

                # Create and publish event
                event = WebSocketEvent(
                    source=f"ws:{client_id}",
                    connection_id=client_id,
                    content=message.content,
                )
                await store.publish(event)

                # Send acknowledgment
                ack = WebSocketAck(ack=event.id)
                await websocket.send_json(ack.model_dump())

                logger.debug(
                    "WebSocket message processed: client_id=%s, event_id=%s",
                    client_id,
                    event.id,
                )

            except ValidationError as e:
                # Send error for invalid message format
                await websocket.send_json(
                    {"error": "Invalid message format", "details": e.errors()}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: client_id=%s", client_id)
    except Exception as e:
        logger.exception("WebSocket error: client_id=%s, error=%s", client_id, e)
        # Try to close gracefully
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            logger.debug("Failed to close WebSocket gracefully: client_id=%s", client_id)
