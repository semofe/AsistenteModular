"""Voice HTTP endpoints."""
from __future__ import annotations
import asyncio
import mimetypes
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from asistente.config.assistant_profile import AssistantProfileStore
from asistente.config.activation import ActivationSettingsStore
from asistente.access.catalog import AccessCatalog, normalize_name
from asistente.access.web_catalog import WebAccessCatalog
from asistente.config.settings import VoicePreferenceStore
from asistente.tools.registry import AccessToolService
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.voice.manager import VoiceError, VoiceManager
from asistente.voice.tts.edge import EdgeTTSSettings, stream_edge
from asistente.api.http_schemas import CredentialRequest, SynthesisRequest, VoicePreferencesRequest
from asistente.api.voice_helpers import _starts_with_wake, _vosk_command_grammar
from collections.abc import Callable


def create_voice_router(
    voice: VoiceManager,
    runtime_dir: Path,
    assistant_profile: AssistantProfileStore | None,
    access_catalog: AccessCatalog | None,
    access_tools: AccessToolService | None,
    web_catalog: WebAccessCatalog | None,
    activation_settings: ActivationSettingsStore | None,
    memory_store: ExplicitMemoryStore | None,
    preferences: VoicePreferenceStore,
    apply_llm: Callable[[], None]
) -> APIRouter:
    router = APIRouter()

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
                "abre, abrir, entra a, entra en, inicia, ejecuta, lanza, cierra, cierras, cerrar, "
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
            wake_only = ""
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
                        if not _starts_with_wake(recognized.text, wake_phrases):
                            return {"text": "", "engine": recognized.engine}
                        if candidate_ok:
                            if normalize_name(recognized.text) in {normalize_name(phrase) for phrase in wake_phrases}:
                                wake_only = recognized.text
                            else:
                                text = recognized.text
                                engine = recognized.engine
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
                try:
                    text = await asyncio.to_thread(voice.transcribe, input_path, hotwords)
                except VoiceError:
                    if not wake_only:
                        raise
            if context == "dormant" and not _starts_with_wake(text, wake_phrases):
                return {"text": wake_only, "engine": "vosk" if wake_only else engine}
            if not text and context == "manual":
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
