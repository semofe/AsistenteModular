"""Compose feature routers and shared application dependencies."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter
from asistente.config.assistant_profile import AssistantProfileStore
from asistente.config.activation import ActivationSettingsStore
from asistente.access.catalog import AccessCatalog
from asistente.access.web_catalog import WebAccessCatalog
from asistente.config.settings import ConversationPreferenceStore, FileAccessPreferenceStore, VoicePreferenceStore
from asistente.core.orchestrator import Orchestrator
from asistente.providers.gemini import GeminiProvider
from asistente.providers.ollama import OllamaProvider
from asistente.providers.llama_cpp import LlamaCppProvider
from asistente.config.settings import LLMPreferenceStore
from asistente.tools.registry import AccessToolService
from asistente.tools.files import FileAccessService
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.memory.embeddings import GeminiEmbeddingProvider
from asistente.automation.scheduler import LocalScheduler, ScheduleStore
from asistente.voice.manager import VoiceManager
from asistente.api.voice_helpers import _starts_with_wake, _vosk_command_grammar
from asistente.api.routers.settings import create_settings_router
from asistente.api.routers.access import create_access_router
from asistente.api.routers.conversation import create_conversation_router
from asistente.api.routers.files import create_files_router
from asistente.api.routers.schedule import create_schedule_router
from asistente.api.routers.memory import create_memory_router
from asistente.api.routers.voice import create_voice_router


def create_http_router(
    voice: VoiceManager,
    runtime_dir: Path,
    orchestrator: Orchestrator | None = None,
    gemini_model: str = "gemini-3.6-flash",
    assistant_profile: AssistantProfileStore | None = None,
    preferences_path: Path | None = None,
    access_catalog: AccessCatalog | None = None,
    access_tools: AccessToolService | None = None,
    web_catalog: WebAccessCatalog | None = None,
    activation_settings: ActivationSettingsStore | None = None,
    memory_store: ExplicitMemoryStore | None = None,
    schedule_store: ScheduleStore | None = None,
    scheduler: LocalScheduler | None = None,
    conversation_preferences: ConversationPreferenceStore | None = None,
    file_access_preferences: FileAccessPreferenceStore | None = None,
    file_access: FileAccessService | None = None,
    llm_preferences: LLMPreferenceStore | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    preferences = VoicePreferenceStore(
        preferences_path or runtime_dir.parent / "voice-preferences.json"
    )
    llm_preferences = llm_preferences or LLMPreferenceStore(runtime_dir.parent / "llm-preferences.json")

    def apply_llm() -> None:
        if orchestrator is None:
            return
        config = llm_preferences.get()
        key = voice.credentials.get("gemini")
        if memory_store is not None:
            memory_store.embeddings = GeminiEmbeddingProvider(key) if key and config["provider"] == "gemini" else None
        if config["provider"] == "ollama":
            orchestrator.provider = OllamaProvider(config["ollama_model"])
        elif config["provider"] == "llama_cpp":
            orchestrator.provider = LlamaCppProvider(config["llama_cpp_model"])
        else:
            orchestrator.provider = GeminiProvider(key, config["gemini_model"], bool(conversation_preferences.get()["web_search_enabled"]) if conversation_preferences else True) if key else None

    router.include_router(
        create_settings_router(
            orchestrator=orchestrator,
            assistant_profile=assistant_profile,
            activation_settings=activation_settings,
            llm_preferences=llm_preferences,
            apply_llm=apply_llm,
        )
    )
    router.include_router(
        create_access_router(
            access_catalog=access_catalog,
            access_tools=access_tools,
            web_catalog=web_catalog,
        )
    )
    router.include_router(
        create_conversation_router(
            orchestrator=orchestrator,
            conversation_preferences=conversation_preferences,
        )
    )
    router.include_router(
        create_files_router(
            file_access_preferences=file_access_preferences,
            file_access=file_access,
        )
    )
    router.include_router(create_schedule_router(schedule_store=schedule_store, scheduler=scheduler))
    router.include_router(create_memory_router(memory_store=memory_store))
    router.include_router(
        create_voice_router(
            voice=voice,
            runtime_dir=runtime_dir,
            assistant_profile=assistant_profile,
            access_catalog=access_catalog,
            access_tools=access_tools,
            web_catalog=web_catalog,
            activation_settings=activation_settings,
            memory_store=memory_store,
            preferences=preferences,
            apply_llm=apply_llm,
        )
    )
    return router
