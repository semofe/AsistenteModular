"""Catálogo persistente de destinos autorizados por el usuario."""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from uuid import uuid4

from asistente.access.path_policy import validate_target
from asistente.storage.database import Database


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in plain).split())


@dataclass(frozen=True, slots=True)
class AccessEntry:
    id: str
    name: str
    kind: str
    target: str
    aliases: list[str]
    arguments: list[str]
    working_directory: str | None
    enabled: bool
    spoken_name: str = ""
    close_policy: str = "process"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AccessMatch:
    entry: AccessEntry
    query: str
    score: float


class AccessCatalog:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _entry(row: sqlite3.Row) -> AccessEntry:
        return AccessEntry(
            id=row["id"], name=row["name"], kind=row["kind"], target=row["target"],
            aliases=list(json.loads(row["aliases_json"])),
            arguments=list(json.loads(row["arguments_json"])),
            working_directory=row["working_directory"], enabled=bool(row["enabled"]),
            spoken_name=row["spoken_name"] or row["name"],
            close_policy=row["close_policy"],
        )

    def list(self) -> list[AccessEntry]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM access_entries ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._entry(row) for row in rows]

    def add(
        self, name: str, kind: str, target: str, aliases: list[str] | None = None,
        arguments: list[str] | None = None, working_directory: str | None = None,
        entry_id: str | None = None, spoken_name: str | None = None,
        close_policy: str = "process",
    ) -> AccessEntry:
        clean_name = " ".join(name.split())
        if not 1 <= len(clean_name) <= 80:
            raise ValueError("El nombre debe tener entre 1 y 80 caracteres.")
        path = validate_target(kind, target)
        clean_aliases = sorted(
            {" ".join(alias.split()) for alias in aliases or [] if alias.strip()},
            key=str.casefold,
        )
        if len(clean_aliases) > 20:
            raise ValueError("Un acceso admite como máximo 20 alias.")
        clean_arguments = list(arguments or [])
        if len(clean_arguments) > 20 or any(len(item) > 300 for item in clean_arguments):
            raise ValueError("Los argumentos de la aplicación no son válidos.")
        if close_policy not in {"process", "window"}:
            raise ValueError("La política de cierre no es válida.")
        if close_policy == "window" and kind != "application":
            raise ValueError("El cierre de ventana solo se aplica a aplicaciones.")
        identifier = entry_id or str(uuid4())
        clean_spoken_name = " ".join((spoken_name or clean_name).split())
        if not 1 <= len(clean_spoken_name) <= 120:
            raise ValueError("El nombre pronunciado debe tener entre 1 y 120 caracteres.")
        directory = str(validate_target("folder", working_directory)) if working_directory else None
        try:
            with self.database.connect() as connection:
                connection.execute(
                    """INSERT INTO access_entries
                    (id, name, kind, target, aliases_json, arguments_json, working_directory,
                     spoken_name, close_policy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (identifier, clean_name, kind, str(path),
                     json.dumps(clean_aliases, ensure_ascii=False),
                     json.dumps(clean_arguments, ensure_ascii=False), directory, clean_spoken_name,
                     close_policy),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe un acceso con ese nombre.") from exc
        return self.get(identifier)

    def get(self, entry_id: str) -> AccessEntry:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM access_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Acceso no encontrado.")
        return self._entry(row)

    def delete(self, entry_id: str) -> bool:
        with self.database.connect() as connection:
            result = connection.execute(
                "DELETE FROM access_entries WHERE id = ?", (entry_id,)
            )
        return result.rowcount > 0

    def add_alias(self, entry_id: str, alias: str) -> AccessEntry:
        entry = self.get(entry_id)
        clean_alias = " ".join(alias.split())
        if not clean_alias or len(clean_alias) > 120:
            return entry
        aliases = sorted(
            {*entry.aliases, clean_alias}, key=str.casefold
        )
        if len(aliases) > 20:
            return entry
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE access_entries SET aliases_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(aliases, ensure_ascii=False), entry_id),
            )
        return self.get(entry_id)

    def update_spoken_name(self, entry_id: str, spoken_name: str) -> AccessEntry:
        clean_name = " ".join(spoken_name.split())
        if not 1 <= len(clean_name) <= 120:
            raise ValueError("El nombre pronunciado debe tener entre 1 y 120 caracteres.")
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE access_entries SET spoken_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (clean_name, entry_id),
            )
        if result.rowcount == 0:
            raise KeyError("Acceso no encontrado.")
        return self.get(entry_id)

    def hotwords(self, max_characters: int = 1200) -> str:
        phrases: list[str] = []
        seen: set[str] = set()
        for entry in self.list():
            if not entry.enabled:
                continue
            for phrase in [entry.name, entry.spoken_name, *entry.aliases]:
                key = normalize_name(phrase)
                if key and key not in seen:
                    seen.add(key)
                    phrases.append(phrase)
        result = ", ".join(phrases)
        return result[:max_characters].rsplit(",", 1)[0] if len(result) > max_characters else result

    def match(self, spoken_name: str, minimum_score: float = 0.70) -> AccessMatch | None:
        wanted = normalize_name(spoken_name)
        if not wanted:
            return None
        scored: list[tuple[float, AccessEntry]] = []
        wanted_tokens = set(wanted.split())
        for entry in self.list():
            if not entry.enabled:
                continue
            best = 0.0
            for raw_candidate in [entry.name, entry.spoken_name, *entry.aliases]:
                candidate = normalize_name(raw_candidate)
                if not candidate:
                    continue
                if candidate == wanted:
                    best = 1.0
                    break
                similarity = SequenceMatcher(None, wanted, candidate).ratio()
                candidate_tokens = set(candidate.split())
                if len(candidate) >= 5 and candidate_tokens.issubset(wanted_tokens):
                    similarity = max(similarity, 0.82)
                best = max(best, similarity)
            if best >= minimum_score:
                scored.append((best, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return None
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.12:
            return None
        return AccessMatch(entry=scored[0][1], query=spoken_name, score=scored[0][0])

    def resolve(self, spoken_name: str) -> AccessEntry | None:
        wanted = normalize_name(spoken_name)
        if not wanted:
            return None
        enabled = [entry for entry in self.list() if entry.enabled]
        exact_entry = self._resolve_exact_from(wanted, enabled)
        if exact_entry is not None:
            return exact_entry
        exact_matches = self._exact_matches(wanted, enabled)
        if exact_matches:
            return None

        wanted_tokens = set(wanted.split())
        tolerant: list[AccessEntry] = []
        for entry in enabled:
            candidates = [normalize_name(candidate) for candidate in [entry.name, entry.spoken_name, *entry.aliases]]
            if any(
                len(candidate) >= 5 and set(candidate.split()).issubset(wanted_tokens)
                for candidate in candidates if candidate
            ):
                tolerant.append(entry)
        return tolerant[0] if len(tolerant) == 1 else None

    @staticmethod
    def _exact_matches(wanted: str, entries: list[AccessEntry]) -> list[AccessEntry]:
        return [
            entry for entry in entries
            if wanted in {normalize_name(candidate) for candidate in [entry.name, entry.spoken_name, *entry.aliases]}
        ]

    @classmethod
    def _resolve_exact_from(
        cls, wanted: str, entries: list[AccessEntry]
    ) -> AccessEntry | None:
        matches = cls._exact_matches(wanted, entries)
        return matches[0] if len(matches) == 1 else None

    def resolve_exact(self, spoken_name: str) -> AccessEntry | None:
        wanted = normalize_name(spoken_name)
        if not wanted:
            return None
        enabled = [entry for entry in self.list() if entry.enabled]
        return self._resolve_exact_from(wanted, enabled)
