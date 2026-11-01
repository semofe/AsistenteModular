"""Mensajes configurables para resultados de herramientas locales."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_ACTION_RESPONSES: dict[str, str] = {
    "success": "¡Hecho!",
    "not_found": "No tengo acceso a esa aplicación.",
    "failed": "No pude completar la acción.",
    "unclear": "Perdón, ¿puedes repetirlo?",
    "confirm": "¿Quieres abrir {targets}?",
    "confirm_bare_open": "¿Abrir {targets}?",
    "cancelled": "Entendido.",
    "unsupported": "Esa función todavía no está disponible.",
    "not_running": "No encuentro esa aplicación abierta.",
    "confirm_close": "¿Quieres cerrar {targets}?",
    "confirm_shutdown": "¿Deseas apagar la PC?",
    "confirm_minimize": "¿Quieres minimizar {targets}?",
}

LEGACY_MESSAGES = {
    "not_found": "No encontré ese acceso.",
}


class ActionResponseStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, str]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        for key, legacy_value in LEGACY_MESSAGES.items():
            if saved.get(key) == legacy_value:
                saved[key] = DEFAULT_ACTION_RESPONSES[key]
        return {
            key: str(saved.get(key, fallback)).strip() or fallback
            for key, fallback in DEFAULT_ACTION_RESPONSES.items()
        }

    def message(self, key: str) -> str:
        return self.get().get(key, DEFAULT_ACTION_RESPONSES["failed"])

    def ensure(self) -> None:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        changed = False
        for key, value in DEFAULT_ACTION_RESPONSES.items():
            if key not in saved or saved.get(key) == LEGACY_MESSAGES.get(key):
                saved[key] = value
                changed = True
        if not changed:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(self.path)
        except OSError:
            temporary.unlink(missing_ok=True)
