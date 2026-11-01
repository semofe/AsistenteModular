"""Canal en tiempo real entre Electron y el motor de Asistente Modular."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from asistente.api.schemas import ClientMessage, ServerMessage
from asistente.core.orchestrator import Orchestrator


def create_websocket_router(orchestrator: Orchestrator) -> APIRouter:
    router = APIRouter()

    async def send(socket: WebSocket, message: ServerMessage) -> None:
        await socket.send_text(message.model_dump_json())

    @router.websocket("/ws")
    async def assistant_socket(socket: WebSocket) -> None:
        await socket.accept()
        await send(socket, ServerMessage(type="assistant_state", payload={"state": "idle"}))
        try:
            while True:
                raw = await socket.receive_text()
                try:
                    message = ClientMessage.model_validate_json(raw)
                    if message.type == "ping":
                        await send(socket, ServerMessage(type="pong", request_id=message.request_id))
                        continue
                    if message.type == "clear_conversation":
                        orchestrator.clear_conversation()
                        await send(
                            socket,
                            ServerMessage(
                                type="conversation_cleared",
                                request_id=message.request_id,
                            ),
                        )
                        continue

                    await send(
                        socket,
                        ServerMessage(
                            type="assistant_state",
                            request_id=message.request_id,
                            payload={"state": "processing"},
                        ),
                    )
                    reply = await orchestrator.handle_text(
                        str(message.payload.get("text", ""))
                    )
                    await send(
                        socket,
                        ServerMessage(
                            type="assistant_text",
                            request_id=message.request_id,
                            payload={
                                "text": reply.text,
                                "speech_fragments": reply.speech_fragments,
                                "client_action": reply.client_action,
                                "sources": [
                                    {"title": source.title, "url": source.url}
                                    for source in (reply.sources or [])
                                ],
                                "usage": {
                                    "input_tokens": reply.input_tokens,
                                    "output_tokens": reply.output_tokens,
                                    "thinking_tokens": reply.thinking_tokens,
                                    "total_tokens": reply.total_tokens,
                                    "session_tokens": reply.session_tokens,
                                },
                            },
                        ),
                    )
                    await send(
                        socket,
                        ServerMessage(
                            type="assistant_state",
                            request_id=message.request_id,
                            payload={"state": "idle"},
                        ),
                    )
                except (ValidationError, ValueError) as exc:
                    await send(
                        socket,
                        ServerMessage(
                            type="error",
                            payload={"code": "invalid_message", "message": str(exc)},
                        ),
                    )
                except Exception as exc:
                    await send(
                        socket,
                        ServerMessage(
                            type="error",
                            request_id=getattr(message, "request_id", None),
                            payload={"code": "processing_error", "message": str(exc)},
                        ),
                    )
                    await send(socket, ServerMessage(type="assistant_state", payload={"state": "idle"}))
        except WebSocketDisconnect:
            return

    return router
