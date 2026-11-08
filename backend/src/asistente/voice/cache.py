"""Caché local de audios sintetizados."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import unicodedata
from pathlib import Path


class AudioCache:
    def __init__(self, root: Path, max_bytes: int = 1024**3) -> None:
        self.root = root
        self.files = root / "files"
        self.database = root / "cache.sqlite3"
        self.max_bytes = max_bytes
        self.files.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS audio_cache (
                    cache_key TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    hits INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    @staticmethod
    def key(text: str, configuration: dict[str, object]) -> str:
        normalized = unicodedata.normalize("NFC", " ".join(text.split()))
        payload = json.dumps(
            {"text": normalized, **configuration},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def restore(self, cache_key: str, destination: Path) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT filename FROM audio_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if not row:
                return None
            source = self.files / row[0]
            if not source.is_file():
                connection.execute("DELETE FROM audio_cache WHERE cache_key = ?", (cache_key,))
                return None
            result = destination.with_suffix(source.suffix)
            shutil.copy2(source, result)
            connection.execute(
                "UPDATE audio_cache SET hits = hits + 1, last_used_at = CURRENT_TIMESTAMP WHERE cache_key = ?",
                (cache_key,),
            )
            return result

    def store(self, cache_key: str, source: Path, provider: str) -> None:
        filename = f"{cache_key}{source.suffix.lower()}"
        destination = self.files / filename
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO audio_cache
                   (cache_key, filename, provider, size_bytes, created_at, last_used_at, hits)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)""",
                (cache_key, filename, provider, destination.stat().st_size),
            )
        self.prune()

    def prune(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT cache_key, filename, size_bytes FROM audio_cache ORDER BY last_used_at DESC"
            ).fetchall()
            total = 0
            for cache_key, filename, size in rows:
                total += int(size)
                if total <= self.max_bytes:
                    continue
                (self.files / filename).unlink(missing_ok=True)
                connection.execute("DELETE FROM audio_cache WHERE cache_key = ?", (cache_key,))

    def clear(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT filename FROM audio_cache").fetchall()
            connection.execute("DELETE FROM audio_cache")
        for (filename,) in rows:
            (self.files / filename).unlink(missing_ok=True)

    def stats(self) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0), COALESCE(SUM(hits), 0) FROM audio_cache"
            ).fetchone()
        return {"files": int(row[0]), "bytes": int(row[1]), "hits": int(row[2])}

