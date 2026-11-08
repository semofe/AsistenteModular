"""Conversation HTTP endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter
from asistente.config.settings import ConversationPreferenceStore
from asistente.core.orchestrator import Orchestrator
from asistente.providers.gemini import GeminiProvider
from asistente.api.http_schemas import ConversationPreferencesRequest


def create_conversation_router(
    orchestrator: Orchestrator | None,
    conversation_preferences: ConversationPreferenceStore | None
) -> APIRouter:
    router = APIRouter()

    @router.get("/conversation/history")
    async def get_conversation_history() -> dict[str, object]:
        return {"messages": [{"role": m.role, "content": m.content} for m in orchestrator.history]} if orchestrator else {"messages": []}

    @router.get("/conversation/preferences")
    async def get_conversation_preferences() -> dict[str, object]:
        return await asyncio.to_thread(conversation_preferences.get)

    @router.put("/conversation/preferences")
    async def save_conversation_preferences(
        request: ConversationPreferencesRequest,
    ) -> dict[str, object]:
        saved = await asyncio.to_thread(
            conversation_preferences.save, request.model_dump()
        )
        if isinstance(getattr(orchestrator, "provider", None), GeminiProvider):
            orchestrator.provider.web_search_enabled = bool(saved["web_search_enabled"])
        return saved

    return router
