"""Configuración local de un navegador y accesos web permitidos."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from asistente.access.catalog import normalize_name
from asistente.access.path_policy import validate_target
from asistente.storage.database import Database


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    name: str
    activation_word: str
    executable: str
    aliases: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WebsiteShortcut:
    id: str
    name: str
    url: str
    aliases: list[str]
    enabled: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_web_url(url: str) -> str:
    clean = url.strip()
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("El enlace debe ser una dirección HTTP o HTTPS válida.")
    if len(clean) > 2000:
        raise ValueError("El enlace es demasiado largo.")
    return clean


class WebAccessCatalog:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_browser(self) -> BrowserConfig | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM browser_config WHERE id = 1").fetchone()
        if row is None:
            return None
        return BrowserConfig(row["name"], row["activation_word"], row["executable"],
                             list(json.loads(row["aliases_json"])))

    def save_browser(self, name: str, activation_word: str, executable: str,
                     aliases: list[str] | None = None) -> BrowserConfig:
        clean_name = " ".join(name.split())
        clean_word = " ".join(activation_word.split())
        path = validate_target("application", executable)
        if path.suffix.casefold() != ".exe":
            raise ValueError("El navegador debe apuntar directamente a un archivo .exe.")
        if not clean_name or not clean_word:
            raise ValueError("El nombre y la palabra de activación son obligatorios.")
        clean_aliases = sorted({" ".join(a.split()) for a in aliases or [] if a.strip()},
                               key=str.casefold)
        with self.database.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO browser_config
                (id, name, activation_word, executable, aliases_json, updated_at)
                VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (clean_name, clean_word, str(path), json.dumps(clean_aliases, ensure_ascii=False)),
            )
        return self.get_browser()  # type: ignore[return-value]

    def clear_browser(self) -> bool:
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM browser_config WHERE id = 1").rowcount > 0

    def list_websites(self) -> list[WebsiteShortcut]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM website_shortcuts ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [WebsiteShortcut(row["id"], row["name"], row["url"],
                                list(json.loads(row["aliases_json"])), bool(row["enabled"]))
                for row in rows]

    def add_website(self, name: str, url: str, aliases: list[str] | None = None) -> WebsiteShortcut:
        clean_name = " ".join(name.split())
        if not 1 <= len(clean_name) <= 80:
            raise ValueError("El nombre debe tener entre 1 y 80 caracteres.")
        clean_aliases = sorted({" ".join(a.split()) for a in aliases or [] if a.strip()},
                               key=str.casefold)
        if len(clean_aliases) > 20:
            raise ValueError("Un acceso admite como máximo 20 alias.")
        identifier = str(uuid4())
        try:
            with self.database.connect() as connection:
                connection.execute(
                    "INSERT INTO website_shortcuts(id, name, url, aliases_json) VALUES (?, ?, ?, ?)",
                    (identifier, clean_name, validate_web_url(url),
                     json.dumps(clean_aliases, ensure_ascii=False)),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Ya existe un acceso web con ese nombre.") from exc
        return next(site for site in self.list_websites() if site.id == identifier)

    def delete_website(self, website_id: str) -> bool:
        with self.database.connect() as connection:
            return connection.execute(
                "DELETE FROM website_shortcuts WHERE id = ?", (website_id,)
            ).rowcount > 0

    def resolve_website(self, spoken_name: str) -> WebsiteShortcut | None:
        wanted = normalize_name(spoken_name)
        matches = [site for site in self.list_websites() if site.enabled and wanted in {
            normalize_name(site.name), *(normalize_name(alias) for alias in site.aliases)
        }]
        return matches[0] if len(matches) == 1 else None

    def browser_names(self) -> set[str]:
        browser = self.get_browser()
        if browser is None:
            return {"navegador", "explorador web"}
        return {"navegador", "explorador web", normalize_name(browser.name),
                normalize_name(browser.activation_word),
                *(normalize_name(alias) for alias in browser.aliases)}

    def hotwords(self, max_characters: int = 800) -> str:
        phrases: list[str] = []
        browser = self.get_browser()
        if browser:
            phrases.extend([browser.name, browser.activation_word, *browser.aliases])
        for site in self.list_websites():
            if site.enabled:
                phrases.extend([site.name, *site.aliases])
        return ", ".join(dict.fromkeys(phrases))[:max_characters]
