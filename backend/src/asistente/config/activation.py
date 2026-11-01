"""Preferencias persistentes del ciclo de activación por voz."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_ACTIVATION: dict[str, object] = {
    "enabled": True,
    "wake_phrase": "Oye {assistant_name}",
    "wake_phrases": [
        "Oye {assistant_name}", "Ey {assistant_name}",
        "Oeh {assistant_name}", "{assistant_name}",
    ],
    "inactivity_seconds": 120,
    "show_on_wake": True,
    "hide_on_timeout": True,
}


class ActivationSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, object]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        result = {**DEFAULT_ACTIVATION, **saved}
        result["wake_phrase"] = "Oye {assistant_name}"
        result["wake_phrases"] = list(DEFAULT_ACTIVATION["wake_phrases"])
        result["inactivity_seconds"] = max(30, min(1800, int(result["inactivity_seconds"])))
        return result

    def save(self, enabled: bool, inactivity_seconds: int,
             show_on_wake: bool = True, hide_on_timeout: bool = True) -> dict[str, object]:
        settings = {
            "enabled": bool(enabled),
            "wake_phrase": "Oye {assistant_name}",
            "wake_phrases": list(DEFAULT_ACTIVATION["wake_phrases"]),
            "inactivity_seconds": max(30, min(1800, int(inactivity_seconds))),
            "show_on_wake": bool(show_on_wake),
            "hide_on_timeout": bool(hide_on_timeout),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return settings

    def rendered(self, assistant_name: str) -> dict[str, object]:
        settings = self.get()
        return {
            **settings,
            "wake_phrase": str(settings["wake_phrase"]).replace("{assistant_name}", assistant_name),
            "wake_phrases": [
                str(phrase).replace("{assistant_name}", assistant_name)
                for phrase in settings["wake_phrases"]  # type: ignore[union-attr]
            ],
            "wake_phrase_template": "Oye {assistant_name}",
        }
