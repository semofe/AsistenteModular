"""Recuerdos explícitos del usuario guardados localmente."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import logging
from threading import Lock
from datetime import datetime, timezone
import re
from uuid import uuid4

from asistente.storage.database import Database
from asistente.memory.embeddings import GeminiEmbeddingProvider


logger = logging.getLogger(__name__)


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[\wáéíóúüñ]+", value.casefold()))


@dataclass(frozen=True, slots=True)
class Memory:
    id: str
    content: str
    category: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class ExplicitMemoryStore:
    """Almacenamiento local y recuperación léxica de recuerdos editables."""

    def __init__(
        self,
        database: Database,
        embeddings: GeminiEmbeddingProvider | None = None,
    ) -> None:
        self.database = database
        self.embeddings = embeddings
        self._index_lock = Lock()

    @staticmethod
    def _row(row: object) -> Memory:
        return Memory(
            id=row["id"], content=row["content"], category=row["category"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def add(self, content: str, category: str = "general") -> Memory:
        clean = " ".join(content.split()).strip()
        if not clean:
            raise ValueError("El recuerdo no puede estar vacío.")
        if len(clean) > 1000:
            raise ValueError("El recuerdo puede tener como máximo 1000 caracteres.")
        identifier = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO memories(id, content, normalized_content, category, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, clean, normalize(clean), category.strip() or "general", now, now),
            )
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (identifier,)).fetchone()
        return self._row(row)

    def index_pending(self, batch_size: int = 10) -> int:
        """Index a bounded batch; failed records remain pending for the next retry."""
        provider = self.embeddings
        if provider is None or batch_size <= 0 or not self._index_lock.acquire(blocking=False):
            return 0
        indexed = 0
        try:
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT m.id, m.content FROM memories m "
                    "LEFT JOIN memory_embeddings e ON e.memory_id = m.id "
                    "WHERE e.memory_id IS NULL OR e.model != ? "
                    "ORDER BY m.created_at, m.id LIMIT ?",
                    (provider.model, batch_size),
                ).fetchall()
            for row in rows:
                if self.embeddings is not provider:
                    break
                try:
                    vector = provider.embed(row["content"], "RETRIEVAL_DOCUMENT")
                    if not vector or not all(math.isfinite(v) for v in vector) or not any(vector):
                        raise ValueError("Invalid embedding vector")
                    if self.embeddings is not provider:
                        break
                    # No database transaction is held during the remote request.
                    # INSERT SELECT handles deletion while the request is in flight.
                    with self.database.connect() as connection:
                        result = connection.execute(
                            "INSERT OR REPLACE INTO memory_embeddings(memory_id, model, vector_json) "
                            "SELECT id, ?, ? FROM memories WHERE id = ? AND content = ?",
                            (provider.model, json.dumps(vector), row["id"], row["content"]),
                        )
                        indexed += result.rowcount
                except Exception:
                    logger.warning("Memory embedding failed; batch will retry later", exc_info=True)
                    break
            return indexed
        finally:
            self._index_lock.release()

    def list(self) -> list[Memory]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM memories ORDER BY updated_at DESC, created_at DESC").fetchall()
        return [self._row(row) for row in rows]

    def delete(self, identifier: str) -> bool:
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM memories WHERE id = ?", (identifier,)).rowcount > 0

    def retrieve(self, query: str, limit: int = 5) -> list[Memory]:
        """RAG semántico en nube, con coincidencia léxica como respaldo."""
        if limit <= 0:
            return []
        provider = self.embeddings
        if provider is not None:
            try:
                query_vector = provider.embed(query, "RETRIEVAL_QUERY")
                with self.database.connect() as connection:
                    rows = connection.execute("SELECT memory_id, vector_json FROM memory_embeddings WHERE model = ?", (provider.model,)).fetchall()
                scores = {row["memory_id"]: sum(a * b for a, b in zip(query_vector, json.loads(row["vector_json"]))) / max(math.sqrt(sum(a * a for a in query_vector)) * math.sqrt(sum(b * b for b in json.loads(row["vector_json"]))), 1e-12) for row in rows}
                semantic = [memory for memory in self.list() if scores.get(memory.id, -1.0) >= 0.45]
                semantic.sort(key=lambda memory: scores[memory.id], reverse=True)
                if semantic:
                    return semantic[:limit]
            except Exception:
                logger.warning("Semantic recall failed; using lexical recall", exc_info=True)
        query_tokens = set(normalize(query).split())
        if not query_tokens:
            return []
        scored: list[tuple[float, Memory]] = []
        for memory in self.list():
            tokens = set(normalize(memory.content).split())
            overlap = query_tokens & tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1) + len(overlap) / max(len(tokens), 1)
            scored.append((score, memory))
        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return [memory for _, memory in scored[:limit]]

    def capture_from_command(self, text: str) -> Memory | None:
        """Detecta peticiones explícitas; nunca infiere recuerdos por su cuenta."""
        match = re.match(
            r"^\s*(?:oye\s+\w+\s*,?\s*)?(?:recuerda|recorda|guarda)\s+(?:que\s+)?(.+?)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        return self.add(match.group(1)) if match else None
