"""Perfil central editable del asistente."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_PROFILE: dict[str, str] = {
    "name": "Asistente",
    "language": "es",
    "wake_phrase": "Oye {assistant_name}",
}


class AssistantProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict[str, str]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        result = {**DEFAULT_PROFILE, **saved}
        result["name"] = str(result["name"]).strip() or DEFAULT_PROFILE["name"]
        return result

    def rendered(self) -> dict[str, str]:
        profile = self.get()
        return {
            **profile,
            "wake_phrase": profile["wake_phrase"].replace(
                "{assistant_name}", profile["name"]
            ),
        }

    def variables(self) -> dict[str, str]:
        return {"assistant_name": self.get()["name"]}

    def save_name(self, name: str) -> dict[str, str]:
        clean_name = " ".join(name.split())
        if not 1 <= len(clean_name) <= 40:
            raise ValueError("El nombre debe tener entre 1 y 40 caracteres.")
        profile = self.get()
        profile["name"] = clean_name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)
        return self.rendered()
