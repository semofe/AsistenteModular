"""Mensajes versionados compartidos por HTTP y WebSocket."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ClientMessage(BaseModel):
    version: Literal[1] = 1
    type: Literal["user_text", "clear_conversation", "ping"]
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)


class ServerMessage(BaseModel):
    version: Literal[1] = 1
    type: Literal[
        "assistant_state", "assistant_text", "conversation_cleared", "pong", "error"
    ]
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

