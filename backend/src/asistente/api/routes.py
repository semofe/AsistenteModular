"""Rutas HTTP para operaciones independientes y configuración."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from asistente.config.assistant_profile import AssistantProfileStore
from asistente.config.activation import ActivationSettingsStore
from asistente.access.catalog import AccessCatalog, normalize_name
from asistente.access.web_catalog import WebAccessCatalog
from asistente.access.path_policy import PathPolicyError
from asistente.config.settings import ConversationPreferenceStore, FileAccessPreferenceStore, VoicePreferenceStore
from asistente.core.orchestrator import Orchestrator
from asistente.providers.gemini import GeminiProvider
from asistente.providers.ollama import OllamaProvider
from asistente.config.settings import LLMPreferenceStore
from asistente.access.discovery_windows import sync_discovered_apps
from asistente.tools.registry import AccessToolService
from asistente.tools.files import FileAccessService
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.memory.embeddings import GeminiEmbeddingProvider
from asistente.automation.scheduler import LocalScheduler, ScheduleStore
from asistente.voice.manager import VoiceError, VoiceManager
from asistente.voice.tts.edge import EdgeTTSSettings, stream_edge


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    fragments: list[str] | None = Field(default=None, max_length=12)
    use_rvc: bool = False
    engine: str = Field(default="edge", pattern="^(edge|kokoro|elevenlabs|fish|custom)$")
    voice: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    endpoint: str | None = Field(default=None, max_length=500)


class CredentialRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)


class VoicePreferencesRequest(BaseModel):
    engine: str = Field(pattern="^(edge|kokoro|elevenlabs|fish|custom)$")
    edge_voice: str = Field(max_length=100)
    elevenlabs_voice_id: str = Field(max_length=100)
    fish_reference_id: str = Field(max_length=100)
    custom_endpoint: str = Field(max_length=500)
    custom_voice: str = Field(max_length=100)
    custom_model: str = Field(max_length=100)
    rvc_enabled: bool
    voice_output: bool


class LLMConfigRequest(BaseModel):
    provider: Literal["gemini", "ollama"]
    gemini_model: str = Field(min_length=1, max_length=150)
    ollama_model: str = Field(min_length=1, max_length=150)


class ConversationPreferencesRequest(BaseModel):
    web_search_enabled: bool


class FileAccessPreferencesRequest(BaseModel):
    folders: list[str] = Field(default_factory=list, max_length=30)
    extensions: list[str] = Field(default_factory=list, max_length=30)


READABLE_FILE_EXTENSIONS = {"txt", "md", "csv", "json", "docx"}


class AssistantProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class AccessEntryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["application", "file", "folder"]
    target: str = Field(min_length=1, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    spoken_name: str | None = Field(default=None, max_length=120)
    close_policy: Literal["process", "window"] = "process"


class SpokenNameRequest(BaseModel):
    spoken_name: str = Field(min_length=1, max_length=120)


class BrowserConfigRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    activation_word: str = Field(min_length=1, max_length=80)
    executable: str = Field(min_length=1, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class WebsiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class ActivationSettingsRequest(BaseModel):
    enabled: bool
    inactivity_seconds: int = Field(ge=30, le=1800)
    show_on_wake: bool = True
    hide_on_timeout: bool = True


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    category: str = Field(default="general", max_length=60)


class ReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: str = Field(min_length=16, max_length=50)
    action_type: Literal["notify", "open_access"] = "notify"
    access_id: str | None = None


class RoutineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    time_of_day: str = Field(min_length=5, max_length=5)
    days: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    access_ids: list[str] = Field(min_length=1, max_length=20)


def _vosk_command_grammar(
    assistant_name: str,
    wake_phrases: list[str],
    catalog_phrases: list[str],
    dormant: bool,
) -> list[str]:
    targets = list(dict.fromkeys(
        normalized
        for phrase in catalog_phrases
        if (normalized := normalize_name(phrase))
    ))
    action_prefixes = (
        "abre", "abrir", "inicia", "ejecuta", "lanza",
        "cierra", "cierras", "cerrar", "sierra", "siera", "ciera",
        "si era", "minimiza", "minimizar",
    )
    commands = [*targets]
    commands.extend(
        f"{action} {target}" for target in targets for action in action_prefixes
    )
    commands.extend([
        "cierra todo", "cierra todas las aplicaciones", "apaga la pc",
        "eso es todo", "esto es todo", "minimizate", "apagate", "cierrate",
    ])
    confirmations = [
        "si", "correcto", "confirmo", "hazlo", "adelante", "si hazlo",
        "no", "cancelar", "cancela", "dejalo", "no gracias",
    ]
    wakes = list(dict.fromkeys(
        normalized
        for phrase in [*wake_phrases, assistant_name]
        if (normalized := normalize_name(phrase))
    ))
    wake_commands = [f"{wake} {command}" for wake in wakes for command in commands]
    phrases = (
        [*wakes, *wake_commands]
        if dormant
        else [*commands, *confirmations, *wakes, *wake_commands]
    )
    return [*dict.fromkeys(phrases), "[unk]"]


def _starts_with_wake(text: str, wake_phrases: list[str]) -> bool:
    normalized = normalize_name(text)
    return any(
        normalized == wake or normalized.startswith(f"{wake} ")
        for phrase in wake_phrases
        if (wake := normalize_name(phrase))
    )


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
        else:
            orchestrator.provider = GeminiProvider(key, config["gemini_model"], bool(conversation_preferences.get()["web_search_enabled"]) if conversation_preferences else True) if key else None

    @router.get("/llm/config")
    async def get_llm_config() -> dict[str, str]:
        return llm_preferences.get()

    @router.put("/llm/config")
    async def save_llm_config(request: LLMConfigRequest) -> dict[str, str]:
        saved = llm_preferences.save(request.model_dump())
        apply_llm()
        return saved

    @router.post("/access/sync")
    async def sync_apps() -> dict[str, int]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="Catálogo no disponible.")
        added = await asyncio.to_thread(sync_discovered_apps, access_catalog)
        return {"added": added}

    @router.get("/conversation/history")
    async def get_conversation_history() -> dict[str, object]:
        return {"messages": [{"role": m.role, "content": m.content} for m in orchestrator.history]} if orchestrator else {"messages": []}

    @router.get("/files/preferences")
    async def file_access_configuration() -> dict[str, object]:
        if file_access_preferences is None:
            raise HTTPException(status_code=503, detail="La configuración de archivos no está disponible.")
        return file_access_preferences.get()

    @router.put("/files/preferences")
    async def save_file_access_configuration(
        request: FileAccessPreferencesRequest,
    ) -> dict[str, object]:
        if file_access_preferences is None:
            raise HTTPException(status_code=503, detail="La configuración de archivos no está disponible.")
        try:
            folders: list[str] = []
            for folder in request.folders:
                path = Path(folder).expanduser().resolve(strict=True)
                if not path.is_dir():
                    raise ValueError(f"La ruta no es una carpeta: {folder}")
                folders.append(str(path))
            unsupported = {
                extension.strip().lower().lstrip(".")
                for extension in request.extensions
                if extension.strip().lower().lstrip(".") not in READABLE_FILE_EXTENSIONS
            }
            if unsupported:
                raise ValueError(
                    "Tipos disponibles actualmente: "
                    + ", ".join(sorted(READABLE_FILE_EXTENSIONS))
                    + "."
                )
            saved = file_access_preferences.save({
                "folders": folders,
                "extensions": request.extensions,
            })
            if file_access is not None:
                await asyncio.to_thread(file_access.refresh_index)
            return saved
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/files/index")
    async def file_index() -> dict[str, object]:
        if file_access is None:
            raise HTTPException(status_code=503, detail="El índice de archivos no está disponible.")
        return {"files": file_access.index()}

    @router.post("/files/index/refresh")
    async def refresh_file_index() -> dict[str, object]:
        if file_access is None:
            raise HTTPException(status_code=503, detail="El índice de archivos no está disponible.")
        files = await asyncio.to_thread(file_access.refresh_index)
        return {"files": files}

    @router.get("/schedule/events")
    async def scheduled_events() -> dict[str, object]:
        if scheduler is None:
            raise HTTPException(status_code=503, detail="El programador no está disponible.")
        return {"events": scheduler.drain_events()}

    @router.get("/memories")
    async def list_memories() -> dict[str, object]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        entries = await asyncio.to_thread(memory_store.list)
        return {"memories": [entry.to_dict() for entry in entries]}

    @router.post("/memories")
    async def add_memory(request: MemoryRequest) -> dict[str, object]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        try:
            entry = await asyncio.to_thread(memory_store.add, request.content, request.category)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/memories/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        deleted = await asyncio.to_thread(memory_store.delete, memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recuerdo no encontrado.")
        return {"deleted": True}

    @router.get("/reminders")
    async def list_reminders() -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        entries = await asyncio.to_thread(schedule_store.list_reminders)
        return {"reminders": [entry.to_dict() for entry in entries]}

    @router.post("/reminders")
    async def add_reminder(request: ReminderRequest) -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        try:
            entry = await asyncio.to_thread(schedule_store.add_reminder, request.title, request.due_at, request.action_type, request.access_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/reminders/{reminder_id}")
    async def delete_reminder(reminder_id: str) -> dict[str, bool]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        deleted = await asyncio.to_thread(schedule_store.delete_reminder, reminder_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recordatorio no encontrado.")
        return {"deleted": True}

    @router.get("/routines")
    async def list_routines() -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        entries = await asyncio.to_thread(schedule_store.list_routines)
        return {"routines": [entry.to_dict() for entry in entries]}

    @router.post("/routines")
    async def add_routine(request: RoutineRequest) -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        try:
            entry = await asyncio.to_thread(schedule_store.add_routine, request.name, request.time_of_day, request.days, request.access_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/routines/{routine_id}")
    async def delete_routine(routine_id: str) -> dict[str, bool]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        deleted = await asyncio.to_thread(schedule_store.delete_routine, routine_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Rutina no encontrada.")
        return {"deleted": True}

    @router.get("/access")
    async def list_access_entries() -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        entries = await asyncio.to_thread(access_catalog.list)
        return {"entries": [entry.to_dict() for entry in entries]}

    @router.post("/access")
    async def add_access_entry(request: AccessEntryRequest) -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        try:
            entry = await asyncio.to_thread(
                access_catalog.add,
                request.name,
                request.kind,
                request.target,
                request.aliases,
                spoken_name=request.spoken_name,
                close_policy=request.close_policy,
            )
        except (ValueError, PathPolicyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.put("/access/{entry_id}/spoken-name")
    async def save_access_spoken_name(
        entry_id: str, request: SpokenNameRequest
    ) -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        try:
            entry = await asyncio.to_thread(
                access_catalog.update_spoken_name, entry_id, request.spoken_name
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/access/{entry_id}")
    async def delete_access_entry(entry_id: str) -> dict[str, bool]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        deleted = await asyncio.to_thread(access_catalog.delete, entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Acceso no encontrado.")
        return {"deleted": True}

    @router.post("/access/{entry_id}/open")
    async def open_access_entry(entry_id: str) -> dict[str, object]:
        if access_tools is None:
            raise HTTPException(status_code=503, detail="Las herramientas no están disponibles.")
        try:
            result = await asyncio.to_thread(access_tools.open, entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "opened": result.opened,
            "id": result.entry_id,
            "name": result.name,
            "kind": result.kind,
            "message": access_tools.success_message(),
        }

    @router.get("/browser")
    async def browser_configuration() -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        browser = await asyncio.to_thread(web_catalog.get_browser)
        websites = await asyncio.to_thread(web_catalog.list_websites)
        return {
            "browser": browser.to_dict() if browser else None,
            "websites": [website.to_dict() for website in websites],
        }

    @router.put("/browser")
    async def save_browser_configuration(request: BrowserConfigRequest) -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        try:
            browser = await asyncio.to_thread(
                web_catalog.save_browser, request.name, request.activation_word,
                request.executable, request.aliases,
            )
        except (ValueError, PathPolicyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return browser.to_dict()

    @router.delete("/browser")
    async def clear_browser_configuration() -> dict[str, bool]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        await asyncio.to_thread(web_catalog.clear_browser)
        return {"deleted": True}

    @router.post("/websites")
    async def add_website(request: WebsiteRequest) -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        try:
            website = await asyncio.to_thread(
                web_catalog.add_website, request.name, request.url, request.aliases
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return website.to_dict()

    @router.delete("/websites/{website_id}")
    async def delete_website(website_id: str) -> dict[str, bool]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        deleted = await asyncio.to_thread(web_catalog.delete_website, website_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Acceso web no encontrado.")
        return {"deleted": True}

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

    @router.get("/voice/config")
    async def voice_config() -> dict[str, object]:
        return {
            "stt_engine": "faster-whisper",
            "stt_model": voice.stt.model,
            "tts_engine": "edge",
            "edge_voice": voice.edge.voice,
            "available_engines": ["edge", "elevenlabs", "fish", "custom", "kokoro"],
            "tts_voice": voice.tts.voice_path.name,
            "rvc_available": voice.rvc.model_path.exists(),
            "rvc_default": voice.rvc.enabled,
            "rvc_pitch": voice.rvc.pitch,
            "credentials": voice.credentials.status(),
            "cache": voice.cache.stats(),
            "preferences": preferences.get(),
        }

    @router.put("/voice/preferences")
    async def save_preferences(request: VoicePreferencesRequest) -> dict[str, object]:
        return await asyncio.to_thread(preferences.save, request.model_dump())

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
    @router.put("/voice/credentials/{provider}")
    async def save_credential(provider: str, request: CredentialRequest) -> dict[str, object]:
        try:
            await asyncio.to_thread(voice.credentials.set, provider, request.api_key)
        except (ValueError, ImportError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if provider == "gemini":
            apply_llm()
        return {"provider": provider, "configured": True}

    @router.delete("/voice/credentials/{provider}")
    async def delete_credential(provider: str) -> dict[str, object]:
        try:
            await asyncio.to_thread(voice.credentials.delete, provider)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        configured = voice.credentials.get(provider) is not None
        if provider == "gemini":
            apply_llm()
            if memory_store is not None:
                memory_store.embeddings = None
        return {"provider": provider, "configured": configured}

    @router.get("/voice/cache")
    async def cache_stats() -> dict[str, int]:
        return await asyncio.to_thread(voice.cache.stats)

    @router.delete("/voice/cache")
    async def clear_cache() -> dict[str, int]:
        await asyncio.to_thread(voice.cache.clear)
        return voice.cache.stats()

    @router.get("/voice/edge-voices")
    async def edge_voices() -> dict[str, object]:
        try:
            voices = await asyncio.to_thread(voice.spanish_edge_voices)
            return {"voices": voices}
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"No se pudieron consultar las voces de Edge: {exc}"
            ) from exc

    @router.post("/voice/transcribe")
    async def transcribe(request: Request) -> dict[str, str]:
        context = request.query_params.get("context", "manual")
        if context not in {"manual", "active", "dormant"}:
            raise HTTPException(status_code=400, detail="Contexto de voz inválido.")
        content_type = request.headers.get("content-type", "audio/webm")
        suffix = ".ogg" if "ogg" in content_type else ".webm"
        input_path = runtime_dir / f"recording-{uuid4().hex}{suffix}"
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="La grabación está vacía.")
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="La grabación supera 15 MB.")
        input_path.write_bytes(data)
        try:
            catalog_words = ""
            web_words = ""
            hotwords = (
                "abre, abrir, inicia, ejecuta, lanza, cierra, cierras, cerrar, "
                "minimiza, minimizar, minimízate, eso es todo, esto es todo, gracias, "
                "apágate, ciérrate, apaga la PC, oye, ey, oeh"
            )
            if access_catalog is not None:
                catalog_words = await asyncio.to_thread(access_catalog.hotwords)
                if catalog_words:
                    hotwords = f"{hotwords}, {catalog_words}"
            if web_catalog is not None:
                web_words = await asyncio.to_thread(web_catalog.hotwords)
                if web_words:
                    hotwords = f"{hotwords}, {web_words}"
            if assistant_profile is not None:
                hotwords = f"{assistant_profile.get()['name']}, {hotwords}"
            text = ""
            engine = "faster-whisper"
            if context in {"active", "dormant"}:
                name = assistant_profile.get()["name"] if assistant_profile else "Asistente Modular"
                activation = (
                    activation_settings.rendered(name)
                    if activation_settings is not None
                    else {"wake_phrases": [f"Oye {name}", f"Ey {name}", name]}
                )
                wake_phrases = [str(item) for item in activation["wake_phrases"]]
                catalog_phrases = [
                    item.strip()
                    for item in f"{catalog_words},{web_words}".split(",")
                    if item.strip()
                ]
                grammar = _vosk_command_grammar(
                    name, wake_phrases, catalog_phrases, context == "dormant"
                )
                try:
                    recognized = await asyncio.to_thread(
                        voice.transcribe_vosk, input_path, grammar
                    )
                    candidate_ok = (
                        bool(recognized.text)
                        and "[unk]" not in recognized.text
                        and recognized.confidence >= voice.vosk.minimum_confidence
                    )
                    if context == "dormant":
                        if candidate_ok and _starts_with_wake(
                            recognized.text, wake_phrases
                        ):
                            text = recognized.text
                            engine = recognized.engine
                        else:
                            return {"text": "", "engine": recognized.engine}
                    elif (
                        candidate_ok
                        and access_tools is not None
                        and access_tools.recognizes(recognized.text, name)
                    ):
                        text = recognized.text
                        engine = recognized.engine
                except VoiceError:
                    # Si Vosk no está instalado, conserva el comportamiento anterior.
                    pass
            if not text:
                text = await asyncio.to_thread(voice.transcribe, input_path, hotwords)
            if not text:
                raise HTTPException(status_code=422, detail="No se detectó voz.")
            return {"text": text, "engine": engine}
        except VoiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            input_path.unlink(missing_ok=True)

    @router.post("/voice/synthesize", response_class=FileResponse)
    async def synthesize(request: SynthesisRequest) -> FileResponse:
        output_path = runtime_dir / f"speech-{uuid4().hex}.wav"
        def cleanup() -> None:
            # El identificador único limita la limpieza a esta solicitud.
            for path in runtime_dir.glob(f"{output_path.stem}*"):
                if path.is_file():
                    path.unlink(missing_ok=True)

        try:
            if request.fragments:
                result = await asyncio.to_thread(
                    voice.synthesize_fragments,
                    request.fragments,
                    output_path,
                    request.use_rvc,
                    request.engine,
                    request.voice,
                    request.model,
                    request.endpoint,
                )
            else:
                result = await asyncio.to_thread(
                    voice.synthesize,
                    request.text,
                    output_path,
                    request.use_rvc,
                    request.engine,
                    request.voice,
                    request.model,
                    request.endpoint,
                )
        except VoiceError as exc:
            cleanup()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception:
            cleanup()
            raise
        return FileResponse(
            result.path,
            media_type=mimetypes.guess_type(result.path.name)[0] or "application/octet-stream",
            filename="asistente-response.wav",
            headers={
                "X-Asistente-Modular-TTS-Provider": result.provider,
                "X-Asistente-Modular-Cache": "hit" if result.cache_hit else "miss",
                "X-Asistente-Modular-Fallback-From": result.fallback_from or "",
            },
            background=BackgroundTask(cleanup),
        )

    @router.post("/voice/stream")
    async def stream_speech(request: SynthesisRequest) -> StreamingResponse:
        if request.engine != "edge" or request.use_rvc:
            raise HTTPException(
                status_code=400,
                detail="El streaming directo solo está disponible para Edge TTS sin RVC.",
            )
        settings = EdgeTTSSettings(
            voice=request.voice or voice.edge.voice,
            rate=voice.edge.rate,
            volume=voice.edge.volume,
            pitch=voice.edge.pitch,
        )
        return StreamingResponse(
            stream_edge(request.text, settings),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

    return router
