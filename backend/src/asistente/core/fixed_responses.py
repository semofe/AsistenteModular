"""Respuestas locales deterministas para intenciones conocidas."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


@dataclass(frozen=True, slots=True)
class FixedResponse:
    intent: str
    response: str


class FixedResponseMatcher:
    def __init__(
        self,
        path: Path,
        variable_provider: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.path = path
        self.variable_provider = variable_provider

    def _variables(self) -> dict[str, str]:
        return self.variable_provider() if self.variable_provider else {}

    @staticmethod
    def _render_response(template: str, variables: dict[str, str]) -> str:
        for key, value in variables.items():
            template = template.replace(f"{{{key}}}", value)
        return template

    @staticmethod
    def _render_pattern(template: str, variables: dict[str, str]) -> str:
        for key, value in variables.items():
            template = template.replace(f"{{{key}}}", re.escape(normalize_text(value)))
        return template

    def match(self, text: str) -> FixedResponse | None:
        normalized = normalize_text(text)
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        variables = self._variables()
        for rule in document.get("rules", []):
            response = self._render_response(
                str(rule.get("response", "")).strip(), variables
            )
            intent = str(rule.get("id", "fixed_response")).strip()
            if not response:
                continue
            for pattern in rule.get("patterns", []):
                try:
                    rendered_pattern = self._render_pattern(str(pattern), variables)
                    if re.fullmatch(rendered_pattern, normalized, flags=re.IGNORECASE):
                        return FixedResponse(intent=intent, response=response)
                except re.error:
                    continue
        return None
