"""Preferencias editables que no contienen secretos."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_VOICE_PREFERENCES: dict[str, object] = {
    "engine": "edge",
    "edge_voice": "es-MX-DaliaNeural",
    "elevenlabs_voice_id": "",
    "fish_reference_id": "",
    "custom_endpoint": "",
    "custom_voice": "",
    "custom_model": "",
    "rvc_enabled": False,
    "voice_output": True,
}


DEFAULT_CONVERSATION_PREFERENCES: dict[str, object] = {
    "web_search_enabled": True,
}

DEFAULT_FILE_ACCESS_PREFERENCES: dict[str, object] = {
    "folders": [],
    "extensions": ["txt", "md", "csv", "json", "docx"],
}


class VoicePreferenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, object]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        return {**DEFAULT_VOICE_PREFERENCES, **saved}

    def save(self, values: dict[str, object]) -> dict[str, object]:
        allowed = set(DEFAULT_VOICE_PREFERENCES)
        clean = {key: value for key, value in values.items() if key in allowed}
        result = {**DEFAULT_VOICE_PREFERENCES, **clean}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)
        return result


class ConversationPreferenceStore:
    """Preferencias de conversación persistentes y sin secretos."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, object]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        return {**DEFAULT_CONVERSATION_PREFERENCES, **saved}

    def save(self, values: dict[str, object]) -> dict[str, object]:
        result = {"web_search_enabled": bool(values.get("web_search_enabled", True))}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return result


class FileAccessPreferenceStore:
    """Lista explícita de carpetas y extensiones que Asistente Modular puede leer."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, object]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        return {
            "folders": list(saved.get("folders", DEFAULT_FILE_ACCESS_PREFERENCES["folders"])),
            "extensions": list(saved.get("extensions", DEFAULT_FILE_ACCESS_PREFERENCES["extensions"])),
        }

    def save(self, values: dict[str, object]) -> dict[str, object]:
        folders = values.get("folders", [])
        extensions = values.get("extensions", [])
        if not isinstance(folders, list) or not isinstance(extensions, list):
            raise ValueError("Las carpetas y extensiones deben ser listas.")
        clean_folders = sorted({str(folder).strip() for folder in folders if str(folder).strip()})
        clean_extensions = sorted({str(extension).strip().lower().lstrip(".") for extension in extensions if str(extension).strip()})
        if len(clean_folders) > 30 or len(clean_extensions) > 30:
            raise ValueError("Puedes configurar hasta 30 carpetas y 30 tipos de archivo.")
        if any(not extension.replace("_", "").replace("-", "").isalnum() for extension in clean_extensions):
            raise ValueError("Hay una extensión con un formato no válido.")
        result = {"folders": clean_folders, "extensions": clean_extensions}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return result


DEFAULT_LLM_PREFERENCES = {
    "provider": "gemini",
    "gemini_model": "gemini-3.6-flash",
    "ollama_model": "llama3.2:1b",
    "llama_cpp_model": "Qwen3-8B-64k-Josiefied-Uncensored-NEO-Max-D_AU-Q4_K_M-imat",
}

class LLMPreferenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, str]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        return {**DEFAULT_LLM_PREFERENCES, **{k: v for k, v in saved.items() if k in DEFAULT_LLM_PREFERENCES}}

    def save(self, values: dict[str, str]) -> dict[str, str]:
        result = {**self.get(), **values}
        if result["provider"] not in ("gemini", "ollama", "llama_cpp"):
            raise ValueError("Proveedor desconocido.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return result
