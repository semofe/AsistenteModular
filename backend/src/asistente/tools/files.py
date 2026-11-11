"""Lectura segura de documentos dentro de carpetas autorizadas por el usuario."""

from __future__ import annotations

import json
import os
from time import monotonic
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
import unicodedata
import xml.etree.ElementTree as ElementTree

from asistente.access.catalog import normalize_name
from asistente.config.settings import FileAccessPreferenceStore
from asistente.tools.search import EXTENSION_CATEGORIES


_OPENABLE_EXTENSIONS = {
    ".json", ".md", ".ppt", ".pptx",
    *(extension for extensions in EXTENSION_CATEGORIES.values() for extension in extensions),
}

# Windows normally exposes these folders with English directory names, while
# the assistant accepts Spanish names in commands (for example, "en escritorio").
_FOLDER_LOCATION_ALIASES = {
    "escritorio": "desktop",
    "documentos": "documents",
    "descargas": "downloads",
    "imagenes": "pictures",
    "fotos": "pictures",
    "videos": "videos",
    "musica": "music",
}


class FileAccessError(ValueError):
    pass


class FileIndexEntry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.path.name,
            "path": str(self.path),
            "extension": self.path.suffix.casefold().lstrip("."),
        }


class FileAccessService:
    MAX_BYTES = 2_000_000
    MAX_CHARACTERS = 24_000

    MAX_INDEXED_FILES = 10_000

    def __init__(self, preferences: FileAccessPreferenceStore, index_path: Path) -> None:
        self.preferences = preferences
        self.index_path = index_path

    def refresh_index(self) -> list[dict[str, str]]:
        preferences = self.preferences.get()
        extensions = set(preferences["extensions"])
        entries: list[FileIndexEntry] = []
        for configured_folder in preferences["folders"]:
            try:
                folder = Path(str(configured_folder)).resolve(strict=True)
            except OSError:
                continue
            # Desktop often contains source trees and dependency folders. Index only
            # files placed directly on it, matching the fast Desktop search policy.
            try:
                candidates = folder.iterdir() if normalize_name(folder.name) == "desktop" else folder.rglob("*")
            except OSError:
                continue
            for candidate in candidates:
                if len(entries) >= self.MAX_INDEXED_FILES:
                    break
                try:
                    if candidate.is_file() and candidate.suffix.casefold().lstrip(".") in extensions:
                        entries.append(FileIndexEntry(candidate.resolve(strict=True)))
                except OSError:
                    continue
        entries.sort(key=lambda entry: entry.path.name.casefold())
        serialized = [entry.to_dict() for entry in entries]
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.index_path)
        return serialized

    def index(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [entry for entry in data if isinstance(entry, dict) and isinstance(entry.get("path"), str)]

    def resolve_from_request(self, text: str) -> str | None:
        if explicit := explicit_path_from_request(text):
            return explicit
        if not _is_file_read_request(text):
            return None
        query = _normalize_name(text)
        query_tokens = {token for token in query.split() if token not in _QUERY_STOP_WORDS}
        if not query_tokens:
            return None
        candidates: list[tuple[int, dict[str, str]]] = []
        for entry in self.index():
            name = _normalize_name(Path(entry["path"]).stem)
            name_tokens = set(name.split())
            compact_name = "".join(name.split())
            score = sum(
                3 if token in name_tokens or token == compact_name
                else 2 if token in compact_name or any(token in name_token for name_token in name_tokens)
                else 0
                for token in query_tokens
            )
            if score:
                candidates.append((score, entry))
        candidates.sort(key=lambda item: (-item[0], item[1]["name"].casefold()))
        if not candidates or candidates[0][0] < 3:
            raise FileAccessError("No encontré un archivo autorizado con ese nombre. Actualiza el índice o prueba con más palabras del nombre.")
        if len(candidates) > 1 and candidates[1][0] == candidates[0][0]:
            names = ", ".join(item[1]["name"] for item in candidates[:3])
            raise FileAccessError(f"Encontré varios archivos: {names}. Indica más palabras del nombre.")
        return candidates[0][1]["path"]

    def find_openable(self, requested: str) -> list[Path]:
        query = requested.removeprefix("archivo ")
        name, separator, location = query.rpartition(" en ")
        if not separator:
            name, location = query, ""
        location = location.removeprefix("la carpeta ").removeprefix("carpeta ")
        if not name:
            return []
        normalized_location = _normalize_name(location)
        location_names = {
            normalized_location,
            _FOLDER_LOCATION_ALIASES.get(normalized_location, normalized_location),
        } - {""}

        full_query: set[Path] = set()
        exact: set[Path] = set()
        partial: set[Path] = set()
        deadline = monotonic() + 3
        for configured_folder in self.preferences.get()["folders"]:
            try:
                folder = Path(configured_folder).expanduser().resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            # Desktop must remain quick even when it contains a development project
            # (and therefore large directories such as node_modules). Whether or
            # not the user says "en escritorio", only consider direct files there.
            if normalize_name(folder.name) == "desktop":
                try:
                    directories = [(str(folder), [], [item.name for item in folder.iterdir() if item.is_file()])]
                except OSError:
                    continue
            else:
                directories = os.walk(folder)
            for directory, _, filenames in directories:
                if monotonic() > deadline:
                    raise FileAccessError("La búsqueda tardó demasiado.")
                parent = Path(directory)
                in_location = not location_names or any(
                    normalize_name(part) in location_names for part in parent.parts
                )
                for filename in filenames:
                    if monotonic() > deadline:
                        raise FileAccessError("La búsqueda tardó demasiado.")
                    candidate = parent / filename
                    if candidate.suffix.casefold() not in _OPENABLE_EXTENSIONS:
                        continue
                    stem = normalize_name(candidate.stem)
                    full_name = normalize_name(filename)
                    if query in {stem, full_name}:
                        matches = full_query
                    elif not in_location:
                        continue
                    elif name in {stem, full_name}:
                        matches = exact
                    elif f" {name} " in f" {stem} ":
                        matches = partial
                    else:
                        continue
                    try:
                        target = candidate.resolve(strict=True)
                    except (OSError, RuntimeError):
                        continue
                    if (
                        target.is_relative_to(folder)
                        and target.suffix.casefold() in _OPENABLE_EXTENSIONS
                        and target.is_file()
                    ):
                        matches.add(target)
        return sorted(full_query or exact or partial, key=lambda path: str(path).casefold())

    def read(self, target: str) -> tuple[Path, str]:
        path = self._authorized_path(target)
        if path.stat().st_size > self.MAX_BYTES:
            raise FileAccessError("El archivo supera el límite de 2 MB para lectura.")
        if path.suffix.casefold() == ".docx":
            content = self._read_docx(path)
        else:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")
            except OSError as exc:
                raise FileAccessError("No pude leer el archivo seleccionado.") from exc
        content = content.strip()
        if not content:
            raise FileAccessError("El archivo no contiene texto legible.")
        if len(content) > self.MAX_CHARACTERS:
            content = content[: self.MAX_CHARACTERS] + "\n\n[Contenido recortado por seguridad.]"
        return path, content

    def _authorized_path(self, target: str) -> Path:
        try:
            path = Path(target.strip().strip('"')).expanduser().resolve(strict=True)
        except OSError as exc:
            raise FileAccessError("El archivo indicado no existe.") from exc
        if not path.is_file():
            raise FileAccessError("La ruta indicada no corresponde a un archivo.")
        preferences = self.preferences.get()
        folders = [Path(str(folder)).expanduser() for folder in preferences["folders"]]
        if not folders:
            raise FileAccessError("Primero autoriza una carpeta en Ajustes > Lectura de archivos.")
        try:
            allowed = any(path.is_relative_to(folder.resolve(strict=True)) for folder in folders)
        except OSError as exc:
            raise FileAccessError("Una de las carpetas autorizadas ya no está disponible.") from exc
        if not allowed:
            raise FileAccessError("Ese archivo está fuera de las carpetas autorizadas.")
        extension = path.suffix.casefold().lstrip(".")
        if extension not in set(preferences["extensions"]):
            raise FileAccessError(f"No está permitido leer archivos .{extension or 'sin extensión'}.")
        return path

    @staticmethod
    def _read_docx(path: Path) -> str:
        try:
            with ZipFile(path) as document:
                xml = document.read("word/document.xml")
        except (OSError, KeyError, BadZipFile) as exc:
            raise FileAccessError("No pude extraer texto de este archivo DOCX.") from exc
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise FileAccessError("El DOCX tiene un formato inválido.") from exc
        paragraphs = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n".join(paragraphs)


def explicit_path_from_request(text: str) -> str | None:
    """Obtiene una ruta local citada por el usuario, sin inferir ni explorar rutas."""
    quoted = re.search(r'["“]([A-Za-z]:[\\/][^"”]+)["”]', text)
    if quoted:
        return quoted.group(1).strip()
    plain = re.search(r"([A-Za-z]:[\\/][^\r\n]+)", text)
    return plain.group(1).strip().rstrip(".,;:!?") if plain else None


_QUERY_STOP_WORDS = {
    "a", "al", "archivo", "de", "del", "el", "en", "esta", "este", "la", "las", "lee",
    "leelo", "leer", "los", "me", "mi", "por", "puedes", "que", "resume", "resumeme",
    "revisa", "un", "una", "y",
}


def _normalize_name(value: str) -> str:
    value = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", value)
    value = unicodedata.normalize("NFD", value)
    value = "".join(character for character in value if unicodedata.category(character) != "Mn")
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).casefold().split())


def _is_file_read_request(text: str) -> bool:
    normalized = _normalize_name(text)
    return bool(re.search(r"\b(lee|leer|leelo|resume|resumeme|revisa|analiza)\b", normalized))
