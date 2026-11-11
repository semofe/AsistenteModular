"""Canal en tiempo real entre Electron y el motor de Asistente Modular."""

from __future__ import annotations

import asyncio
from time import perf_counter

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
        active_requests: dict[str, asyncio.Task[None]] = {}

        async def process_request(message: ClientMessage) -> None:
            try:
                await send(socket, ServerMessage(type="assistant_state", request_id=message.request_id, payload={"state": "processing"}))
                started_at = perf_counter()
                reply = await orchestrator.handle_text(str(message.payload.get("text", "")))
                response_time_ms = round((perf_counter() - started_at) * 1000)
                await send(socket, ServerMessage(type="assistant_text", request_id=message.request_id, payload={
                    "text": reply.text, "speech_fragments": reply.speech_fragments,
                    "client_action": reply.client_action,
                    "sources": [{"title": source.title, "url": source.url} for source in (reply.sources or [])],
                    "usage": {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
                              "thinking_tokens": reply.thinking_tokens, "total_tokens": reply.total_tokens,
                              "session_tokens": reply.session_tokens, "response_time_ms": response_time_ms},
                }))
                await send(socket, ServerMessage(type="assistant_state", request_id=message.request_id, payload={"state": "idle"}))
            except asyncio.CancelledError:
                await send(socket, ServerMessage(type="response_cancelled", request_id=message.request_id))
                await send(socket, ServerMessage(type="assistant_state", request_id=message.request_id, payload={"state": "idle"}))
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                await send(socket, ServerMessage(type="error", request_id=message.request_id, payload={"code": "processing_error", "message": str(exc)}))
                await send(socket, ServerMessage(type="assistant_state", request_id=message.request_id, payload={"state": "idle"}))
            finally:
                active_requests.pop(message.request_id, None)

        try:
            while True:
                raw = await socket.receive_text()
                try:
                    message = ClientMessage.model_validate_json(raw)
                except ValidationError as exc:
                    await send(
                        socket,
                        ServerMessage(
                            type="error",
                            payload={"code": "invalid_message", "message": str(exc)},
                        ),
                    )
                    continue

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
                if message.type == "cancel_response":
                    if active_request := active_requests.get(str(message.payload.get("request_id", ""))):
                        active_request.cancel()
                    continue
                if message.type == "user_text":
                    active_requests[message.request_id] = asyncio.create_task(process_request(message))
        except WebSocketDisconnect:
            for task in active_requests.values():
                task.cancel()

    return router
