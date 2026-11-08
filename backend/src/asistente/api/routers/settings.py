"""Settings HTTP endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from asistente.config.assistant_profile import AssistantProfileStore
from asistente.config.activation import ActivationSettingsStore
from asistente.core.orchestrator import Orchestrator
from asistente.config.settings import LLMPreferenceStore
from asistente.api.http_schemas import ActivationSettingsRequest, AssistantProfileRequest, LLMConfigRequest
from collections.abc import Callable


def create_settings_router(
    orchestrator: Orchestrator | None,
    assistant_profile: AssistantProfileStore | None,
    activation_settings: ActivationSettingsStore | None,
    llm_preferences: LLMPreferenceStore | None,
    apply_llm: Callable[[], None]
) -> APIRouter:
    router = APIRouter()

    @router.get("/llm/config")
    async def get_llm_config() -> dict[str, str]:
        return llm_preferences.get()

    @router.put("/llm/config")
    async def save_llm_config(request: LLMConfigRequest) -> dict[str, str]:
        saved = llm_preferences.save(request.model_dump())
        apply_llm()
        return saved

    @router.get("/assistant/profile")
    async def get_assistant_profile() -> dict[str, str]:
        if assistant_profile is None:
            raise HTTPException(status_code=503, detail="El perfil no está disponible.")
        return assistant_profile.rendered()

    @router.put("/assistant/profile")
    async def save_assistant_profile(
        request: AssistantProfileRequest,
    ) -> dict[str, str]:
        if assistant_profile is None:
            raise HTTPException(status_code=503, detail="El perfil no está disponible.")
        try:
            saved = await asyncio.to_thread(assistant_profile.save_name, request.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if orchestrator is not None:
            orchestrator.clear_conversation()
        return saved

    @router.get("/activation")
    async def get_activation_settings() -> dict[str, object]:
        if activation_settings is None or assistant_profile is None:
            raise HTTPException(status_code=503, detail="La activación por voz no está disponible.")
        return activation_settings.rendered(assistant_profile.get()["name"])

    @router.put("/activation")
    async def save_activation_settings(
        request: ActivationSettingsRequest,
    ) -> dict[str, object]:
        if activation_settings is None or assistant_profile is None:
            raise HTTPException(status_code=503, detail="La activación por voz no está disponible.")
        await asyncio.to_thread(
            activation_settings.save,
            request.enabled,
            request.inactivity_seconds,
            request.show_on_wake,
            request.hide_on_timeout,
        )
        return activation_settings.rendered(assistant_profile.get()["name"])

    return router
