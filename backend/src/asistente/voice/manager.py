"""Coordina STT, Kokoro y la conversión RVC aislada."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from asistente.config.credentials import CredentialStore
from asistente.voice.cache import AudioCache
from asistente.voice.conversion.rvc import RVCSettings
from asistente.voice.stt.faster_whisper import FasterWhisperSettings
from asistente.voice.stt.vosk import VoskSettings
from asistente.voice.tts.base import TTSSettings
from asistente.voice.tts.edge import EdgeTTSSettings, list_spanish_voices, synthesize_edge
from asistente.voice.tts.cloud import (
    CloudTTSError,
    synthesize_custom,
    synthesize_elevenlabs,
    synthesize_fish,
)


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    path: Path
    provider: str
    cache_hit: bool
    fallback_from: str | None = None


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    text: str
    engine: str
    confidence: float = 0.0


class VoiceManager:
    def __init__(self, project_root: Path, data_root: Path | None = None) -> None:
        self.voice_root = Path(
            os.environ.get(
                "ASISTENTE_VOICE_ROOT",
                project_root.parent / "AsistenteModularData" / "voice",
            )
        )
        self.voice_python = Path(
            os.environ.get(
                "ASISTENTE_VOICE_PYTHON",
                self.voice_root / ".venv-voice" / "Scripts" / "python.exe",
            )
        )
        self.stt_python = (
            self.voice_python
            if self.voice_python.is_file() or "ASISTENTE_VOICE_PYTHON" in os.environ
            else Path(sys.executable)
        )
        stt_models = self.voice_root / "models"
        local_stt_models = project_root / "backend" / "runtime" / "stt" / "models"
        if not stt_models.is_dir() and "ASISTENTE_VOICE_ROOT" not in os.environ and local_stt_models.is_dir():
            stt_models = local_stt_models
        kokoro_root = self.voice_root / "models" / "kokoro"
        self.stt = FasterWhisperSettings(
            model=os.environ.get("ASISTENTE_STT_MODEL", "small"),
            beam_size=max(1, int(os.environ.get("ASISTENTE_STT_BEAM_SIZE", "5"))),
            cpu_threads=max(1, int(os.environ.get("ASISTENTE_STT_CPU_THREADS", "6"))),
            download_root=stt_models / "whisper"
        )
        self.vosk = VoskSettings(
            model_path=Path(
                os.environ.get(
                    "ASISTENTE_VOSK_MODEL",
                    stt_models / "vosk" / "vosk-model-small-es-0.42",
                )
            ),
            minimum_confidence=float(os.environ.get("ASISTENTE_VOSK_MIN_CONFIDENCE", "0.55")),
        )
        self.tts = TTSSettings(
            model_path=kokoro_root / "kokoro-v1_0.pth",
            config_path=kokoro_root / "config.json",
            voice_path=kokoro_root / "af_alloy.pt",
        )
        self.edge = EdgeTTSSettings(
            voice=os.environ.get("ASISTENTE_EDGE_VOICE", "es-MX-DaliaNeural")
        )
        rvc_root = self.voice_root / "rvc"
        voice_assets = project_root / "assets" / "voices" / "prueba"
        self.rvc = RVCSettings(
            enabled=os.environ.get("ASISTENTE_RVC_ENABLED", "0") == "1",
            python_path=rvc_root / ".venv" / "Scripts" / "python.exe",
            project_path=rvc_root,
            model_path=voice_assets / "HatsuneMikuOv2.pth",
            index_path=voice_assets / "added_IVF397_Flat_nprobe_1_HatsuneMikuOv2_v2.index",
            pitch=int(os.environ.get("ASISTENTE_RVC_PITCH", "8")),
        )
        self.worker = Path(__file__).with_name("worker.py")
        self.credentials = CredentialStore()
        self.cache = AudioCache(
            data_root / "cache" / "tts" if data_root else project_root / "runtime" / "tts-cache"
        )

    def _find_ffmpeg(self) -> Path:
        if configured := os.environ.get("ASISTENTE_FFMPEG_PATH"):
            candidate = Path(configured)
            if candidate.is_file():
                return candidate
        if discovered := shutil.which("ffmpeg"):
            return Path(discovered)
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        winget_root = local_app_data / "Microsoft" / "WinGet" / "Packages"
        candidates = sorted(
            winget_root.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]
        raise VoiceError(
            "No se encontró una instalación funcional de FFmpeg. "
            "Configura ASISTENTE_FFMPEG_PATH con la ruta de ffmpeg.exe."
        )

    def _normalize_audio(self, source: Path, destination: Path, sample_rate: int) -> None:
        try:
            ffmpeg = self._find_ffmpeg()
        except VoiceError:
            command = [
                str(self.stt_python), str(self.worker), "normalize-audio",
                "--input", str(source), "--output", str(destination),
                "--sample-rate", str(sample_rate),
            ]
        else:
            command = [
                str(ffmpeg), "-y", "-loglevel", "error", "-i", str(source),
                "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(destination),
            ]
        try:
            self._run(command)
        except (VoiceError, OSError, subprocess.TimeoutExpired) as exc:
            destination.unlink(missing_ok=True)
            detail = str(exc).splitlines()[-1]
            raise VoiceError(f"No se pudo preparar el audio: {detail}") from exc

    def _run(self, command: list[str], cwd: Path | None = None) -> str:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "RVC_FORCE_CPU": "1"}
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise VoiceError(detail[-1500:] or "El motor de voz falló.")
        return completed.stdout.strip()

    def transcribe(self, audio_path: Path, hotwords: str = "") -> str:
        command = [
                str(self.stt_python),
                str(self.worker),
                "transcribe",
                "--input",
                str(audio_path),
                "--model",
                self.stt.model,
                "--model-root",
                str(self.stt.download_root),
                "--device",
                self.stt.device,
                "--compute-type",
                self.stt.compute_type,
                "--language",
                self.stt.language,
                "--beam-size",
                str(self.stt.beam_size),
                "--cpu-threads",
                str(self.stt.cpu_threads),
            ]
        if hotwords:
            command.extend(["--hotwords", hotwords])
        try:
            output = self._run(command)
            return str(json.loads(output.splitlines()[-1])["text"]).strip()
        except OSError as exc:
            raise VoiceError(f"No se pudo iniciar Whisper con {self.stt_python}.") from exc
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("Whisper tardó demasiado en transcribir.") from exc
        except (IndexError, KeyError, json.JSONDecodeError) as exc:
            raise VoiceError("Whisper devolvió una respuesta inválida.") from exc

    def transcribe_vosk(
        self, audio_path: Path, grammar: list[str]
    ) -> RecognitionResult:
        if not self.vosk.model_path.is_dir():
            raise VoiceError(f"No se encontró el modelo de Vosk: {self.vosk.model_path}")
        grammar_path = audio_path.with_suffix(".vosk-grammar.json")
        try:
            grammar_path.write_text(json.dumps(grammar, ensure_ascii=False), encoding="utf-8")
            output = self._run(
                [
                    str(self.stt_python),
                    str(self.worker),
                    "transcribe-vosk",
                    "--input",
                    str(audio_path),
                    "--model",
                    str(self.vosk.model_path),
                    "--grammar",
                    str(grammar_path),
                    "--sample-rate",
                    str(self.vosk.sample_rate),
                ]
            )
            payload = json.loads(output.splitlines()[-1])
            return RecognitionResult(
                text=str(payload.get("text", "")).strip(),
                engine="vosk",
                confidence=float(payload.get("confidence", 0.0)),
            )
        except OSError as exc:
            raise VoiceError(f"No se pudo preparar el audio o iniciar Vosk con {self.stt_python}.") from exc
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("Vosk tardó demasiado en transcribir.") from exc
        except (IndexError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise VoiceError("Vosk devolvió una respuesta inválida.") from exc
        finally:
            grammar_path.unlink(missing_ok=True)

    def spanish_edge_voices(self) -> list[dict[str, str]]:
        return list_spanish_voices()

    def _cache_configuration(
        self,
        provider: str,
        voice: str | None,
        model: str | None,
        use_rvc: bool,
        endpoint: str | None = None,
    ) -> dict[str, object]:
        rvc_version = ""
        if use_rvc and self.rvc.model_path.exists():
            stat = self.rvc.model_path.stat()
            rvc_version = f"{stat.st_size}:{stat.st_mtime_ns}"
        def version(path: Path) -> str:
            if not path.is_file():
                return ""
            stat = path.stat()
            return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"

        return {
            "schema": 2,
            "edge_settings": asdict(self.edge) if provider == "edge" else {},
            "kokoro_files": [version(self.tts.model_path), version(self.tts.config_path), version(self.tts.voice_path)] if provider == "kokoro" else [],
            "kokoro_language": self.tts.language if provider == "kokoro" else "",
            "rvc_index": version(self.rvc.index_path) if use_rvc else "",
            "provider": provider,
            "voice": voice or "",
            "model": model or "",
            "endpoint": endpoint or "",
            "rvc": use_rvc,
            "rvc_pitch": self.rvc.pitch if use_rvc else 0,
            "rvc_model": rvc_version,
        }

    def _generate_base(
        self,
        text: str,
        output_path: Path,
        provider: str,
        voice: str | None,
        model: str | None,
        endpoint: str | None,
    ) -> Path:
        if provider == "edge":
            base_path = output_path.with_name(f"{output_path.stem}-edge.mp3")
            settings = EdgeTTSSettings(
                voice=voice or self.edge.voice,
                rate=self.edge.rate,
                volume=self.edge.volume,
                pitch=self.edge.pitch,
            )
            synthesize_edge(text, base_path, settings)
            return base_path
        if provider == "kokoro":
            base_path = output_path.with_name(f"{output_path.stem}-kokoro.wav")
            self._run(
                [
                    str(self.voice_python), str(self.worker), "synthesize",
                    "--text", text, "--output", str(base_path),
                    "--model", str(self.tts.model_path),
                    "--config", str(self.tts.config_path),
                    "--voice", str(self.tts.voice_path),
                    "--language", self.tts.language,
                ]
            )
            return base_path
        api_key = self.credentials.get(provider)
        if not api_key:
            raise CloudTTSError(f"No hay una API key configurada para {provider}.")
        if provider == "elevenlabs":
            return synthesize_elevenlabs(
                text, output_path, api_key, voice or "", model or "eleven_flash_v2_5"
            )
        if provider == "fish":
            return synthesize_fish(text, output_path, api_key, voice or "", model or "s2-pro")
        if provider == "custom":
            return synthesize_custom(
                text, output_path, api_key, endpoint or "", voice or "", model or ""
            )
        raise VoiceError(f"Motor TTS desconocido: {provider}")

    def synthesize(
        self,
        text: str,
        output_path: Path,
        use_rvc: bool,
        engine: str = "edge",
        voice: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ) -> SynthesisResult:
        configuration = self._cache_configuration(engine, voice, model, use_rvc, endpoint)
        cache_key = self.cache.key(text, configuration)
        if restored := self.cache.restore(cache_key, output_path):
            return SynthesisResult(restored, engine, True)

        actual_provider = engine
        fallback_from: str | None = None
        try:
            base_path = self._generate_base(
                text, output_path, engine, voice, model, endpoint
            )
        except Exception as exc:
            if engine == "edge":
                # Edge TTS usa un endpoint no autenticado que Microsoft puede
                # rechazar temporalmente con 403. Kokoro permite seguir hablando
                # sin red cuando el modelo y su entorno local están disponibles.
                fallback_from = "edge"
                actual_provider = "kokoro"
                fallback_configuration = self._cache_configuration(
                    "kokoro", None, None, use_rvc
                )
                cache_key = self.cache.key(text, fallback_configuration)
                if restored := self.cache.restore(cache_key, output_path):
                    return SynthesisResult(restored, "kokoro", True, fallback_from)
                try:
                    base_path = self._generate_base(
                        text, output_path, "kokoro", None, None, None
                    )
                except Exception as fallback_error:
                    raise VoiceError(
                        f"Edge TTS rechazó la conexión ({exc}) y Kokoro local tampoco estuvo disponible ({fallback_error})."
                    ) from fallback_error
            elif engine == "kokoro":
                raise VoiceError(f"{engine} no pudo generar la voz: {exc}") from exc
            else:
                fallback_from = engine
                actual_provider = "edge"
                fallback_configuration = self._cache_configuration(
                    "edge", self.edge.voice, None, use_rvc
                )
                cache_key = self.cache.key(text, fallback_configuration)
                if restored := self.cache.restore(cache_key, output_path):
                    return SynthesisResult(restored, "edge", True, fallback_from)
                try:
                    base_path = self._generate_base(
                        text, output_path, "edge", self.edge.voice, None, None
                    )
                except Exception as fallback_error:
                    raise VoiceError(
                        f"Falló {engine} ({exc}) y también Edge TTS ({fallback_error})."
                    ) from fallback_error
        if not use_rvc:
            self.cache.store(cache_key, base_path, actual_provider)
            return SynthesisResult(base_path, actual_provider, False, fallback_from)
        if not all(
            path.exists()
            for path in (self.rvc.python_path, self.rvc.model_path, self.rvc.index_path)
        ):
            raise VoiceError("El modelo o el entorno de RVC no está disponible.")
        env = {**os.environ, "PYTHONPATH": str(self.rvc.project_path), "RVC_FORCE_CPU": "1"}
        rvc_input = base_path
        if base_path.suffix.lower() != ".wav":
            rvc_input = output_path.with_name(f"{output_path.stem}-edge.wav")
            self._normalize_audio(base_path, rvc_input, 40000)
        command = [
            str(self.rvc.python_path), "-X", "utf8", "infer/cli.py",
            "--model", str(self.rvc.model_path), "--index", str(self.rvc.index_path),
            "--input", str(rvc_input), "--output", str(output_path),
            "--pitch", str(self.rvc.pitch), "--f0-method", "rmvpe",
            "--index-rate", str(self.rvc.index_rate),
        ]
        completed = subprocess.run(
            command, cwd=self.rvc.project_path, env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if completed.returncode != 0 or not output_path.exists():
            raise VoiceError((completed.stderr or completed.stdout)[-1500:])
        base_path.unlink(missing_ok=True)
        if rvc_input != base_path:
            rvc_input.unlink(missing_ok=True)
        self.cache.store(cache_key, output_path, actual_provider)
        return SynthesisResult(output_path, actual_provider, False, fallback_from)

    @staticmethod
    def _join_normalized_wavs(
        sources: list[Path], destination: Path, silence_ms: int = 90
    ) -> None:
        if not sources:
            raise VoiceError("No hay fragmentos de voz para unir.")
        with wave.open(str(sources[0]), "rb") as first:
            channels = first.getnchannels()
            width = first.getsampwidth()
            rate = first.getframerate()
        silence = b"\x00" * (rate * silence_ms // 1000) * channels * width
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(width)
            output.setframerate(rate)
            for index, source in enumerate(sources):
                with wave.open(str(source), "rb") as audio:
                    if (
                        audio.getnchannels(), audio.getsampwidth(), audio.getframerate()
                    ) != (channels, width, rate):
                        raise VoiceError("Los fragmentos de voz no tienen el mismo formato.")
                    output.writeframes(audio.readframes(audio.getnframes()))
                if index < len(sources) - 1:
                    output.writeframes(silence)

    def synthesize_fragments(
        self,
        fragments: list[str],
        output_path: Path,
        use_rvc: bool,
        engine: str = "edge",
        voice: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ) -> SynthesisResult:
        clean_fragments = [" ".join(item.split()) for item in fragments if item.strip()]
        if not clean_fragments or len(clean_fragments) > 12:
            raise VoiceError("La composición de voz no contiene fragmentos válidos.")
        configuration = {
            **self._cache_configuration(engine, voice, model, use_rvc, endpoint),
            "schema": 2,
            "composition": "fragments-90ms",
        }
        composite_text = json.dumps(clean_fragments, ensure_ascii=False)
        cache_key = self.cache.key(composite_text, configuration)
        if restored := self.cache.restore(cache_key, output_path):
            return SynthesisResult(restored, engine, True)

        generated: list[Path] = []
        normalized: list[Path] = []
        providers: list[str] = []
        fallbacks: list[str] = []
        try:
            for index, fragment in enumerate(clean_fragments):
                fragment_output = output_path.with_name(
                    f"{output_path.stem}-fragment-{index}.wav"
                )
                result = self.synthesize(
                    fragment, fragment_output, use_rvc, engine, voice, model, endpoint
                )
                generated.append(result.path)
                providers.append(result.provider)
                if result.fallback_from:
                    fallbacks.append(result.fallback_from)
                normalized_path = output_path.with_name(
                    f"{output_path.stem}-normalized-{index}.wav"
                )
                self._normalize_audio(result.path, normalized_path, 24000)
                normalized.append(normalized_path)
            self._join_normalized_wavs(normalized, output_path)
            actual_provider = providers[0] if providers else engine
            fallback_from = fallbacks[0] if fallbacks else None
            self.cache.store(cache_key, output_path, actual_provider)
            return SynthesisResult(output_path, actual_provider, False, fallback_from)
        finally:
            for path in {*generated, *normalized}:
                if path != output_path:
                    path.unlink(missing_ok=True)
