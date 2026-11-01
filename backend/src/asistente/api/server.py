"""Servidor local HTTP/WebSocket de Asistente Modular."""

from __future__ import annotations

import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from asistente.api.routes import create_http_router
from asistente.api.websocket import create_websocket_router
from asistente.access.catalog import AccessCatalog
from asistente.access.web_catalog import WebAccessCatalog
from asistente.access.discovery_windows import builtin_windows_apps
from asistente.config.action_responses import ActionResponseStore
from asistente.config.activation import ActivationSettingsStore
from asistente.config.settings import ConversationPreferenceStore, FileAccessPreferenceStore
from asistente.config.assistant_profile import AssistantProfileStore
from asistente.config.paths import ensure_data_directories
from asistente.core.orchestrator import Orchestrator
from asistente.providers.gemini import GeminiProvider
from asistente.providers.ollama import OllamaProvider
from asistente.config.settings import LLMPreferenceStore
from asistente.memory.conversation_store import ConversationStore
from asistente.tools.file_dispatcher import FileToolService
from asistente.storage.database import Database
from asistente.storage.migrations import migrate
from asistente.tools.registry import AccessToolService
from asistente.tools.files import FileAccessService
from asistente.tools.websites import WebAccessService
from asistente.voice.manager import VoiceManager
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.memory.embeddings import GeminiEmbeddingProvider
from asistente.automation.scheduler import LocalScheduler, ScheduleStore


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "defaults"


def create_app() -> FastAPI:
    paths = ensure_data_directories()
    profile_path = paths["config"] / "assistant.json"
    if not profile_path.exists():
        shutil.copy2(DEFAULT_CONFIG / "assistant.json", profile_path)
    action_responses_path = paths["config"] / "action_responses.json"
    if not action_responses_path.exists():
        shutil.copy2(DEFAULT_CONFIG / "action_responses.json", action_responses_path)
    activation_path = paths["config"] / "activation.json"
    if not activation_path.exists():
        shutil.copy2(DEFAULT_CONFIG / "activation.json", activation_path)
    voice_preferences = paths["config"] / "voice-preferences.json"
    conversation_preferences = ConversationPreferenceStore(paths["config"] / "conversation-preferences.json")
    file_access_preferences = FileAccessPreferenceStore(paths["config"] / "file-access.json")
    legacy_preferences = PROJECT_ROOT / "runtime" / "voice-preferences.json"
    if not voice_preferences.exists() and legacy_preferences.exists():
        shutil.copy2(legacy_preferences, voice_preferences)

    assistant_profile = AssistantProfileStore(profile_path)
    activation_settings = ActivationSettingsStore(activation_path)
    database = Database(paths["data"] / "asistente.sqlite3")
    migrate(database)
    access_catalog = AccessCatalog(database)
    web_catalog = WebAccessCatalog(database)
    memory_store = ExplicitMemoryStore(database)
    schedule_store = ScheduleStore(database)
    with database.connect() as connection:
        seeded = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'builtin_access_seeded'"
        ).fetchone()
    if seeded is None:
        for builtin in builtin_windows_apps():
            if access_catalog.resolve(str(builtin["name"])) is None:
                try:
                    access_catalog.add(**builtin)
                except ValueError:
                    pass
        with database.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
                ("builtin_access_seeded", "1"),
            )
    action_responses = ActionResponseStore(action_responses_path)
    action_responses.ensure()
    access_tools = AccessToolService(access_catalog, action_responses, WebAccessService(web_catalog))
    file_access = FileAccessService(file_access_preferences, paths["config"] / "file-index.json")
    scheduler = LocalScheduler(schedule_store, access_tools)
    voice = VoiceManager(PROJECT_ROOT, paths["root"])
    api_key = voice.credentials.get("gemini")
    llm_preferences = LLMPreferenceStore(paths["config"] / "llm-preferences.json")
    llm_config = llm_preferences.get()
    model = llm_config["gemini_model"] if llm_preferences.path.exists() else os.environ.get("ASISTENTE_GEMINI_MODEL", llm_config["gemini_model"])
    if api_key and llm_config["provider"] == "gemini":
        memory_store.embeddings = GeminiEmbeddingProvider(api_key)
    provider = GeminiProvider(
        api_key, model, bool(conversation_preferences.get()["web_search_enabled"])
    ) if api_key else None
    if llm_config["provider"] == "ollama":
        provider = OllamaProvider(llm_config["ollama_model"])
    conversation_store = ConversationStore(database)
    orchestrator = Orchestrator(
        provider=provider,
        conversation_store=conversation_store,
        file_tools=FileToolService(),
        personality_path=DEFAULT_CONFIG / "personality.txt",
        fixed_responses_path=DEFAULT_CONFIG / "fixed_responses.json",
        assistant_profile=assistant_profile,
        access_tools=access_tools,
        memory_store=memory_store,
        schedule_store=schedule_store,
        file_access=file_access,
    )
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()
    app = FastAPI(
        title=f"{assistant_profile.get()['name']} Local API", version="0.1.0", lifespan=lifespan
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=[
            "X-Asistente-Modular-TTS-Provider",
            "X-Asistente-Modular-Cache",
            "X-Asistente-Modular-Fallback-From",
        ],
    )
    app.include_router(create_websocket_router(orchestrator))
    app.include_router(
        create_http_router(
            voice,
            paths["cache"] / "voice",
            orchestrator,
            model,
            assistant_profile,
            voice_preferences,
            access_catalog,
            access_tools,
            web_catalog,
            activation_settings,
            memory_store,
            schedule_store,
            scheduler,
            conversation_preferences,
            file_access_preferences,
            file_access,
            llm_preferences,
        )
    )

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "assistant": assistant_profile.get()["name"],
            "provider": "ollama" if isinstance(orchestrator.provider, OllamaProvider) else "gemini",
            "model": getattr(orchestrator.provider, "model", model),
            "provider_configured": orchestrator.provider is not None,
            "stt_engine": "hybrid_vosk_whisper",
            "vosk_ready": voice.vosk.model_path.is_dir(),
        }

    return app


app = create_app()


def main() -> None:
    uvicorn.run("asistente.api.server:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
