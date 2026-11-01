"""Almacenamiento persistente de conversaciones en SQLite con ventana deslizante."""

from __future__ import annotations

def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)
from asistente.providers.base import ChatMessage
from asistente.storage.database import Database


class ConversationStore:
    def __init__(
        self,
        database: Database,
        max_messages: int = 20,
        max_tokens: int = 12000,
    ) -> None:
        self.database = database
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def load_history(self) -> list[ChatMessage]:
        """Carga los mensajes más recientes respetando el límite de mensajes y de tokens."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, estimated_tokens
                FROM conversation_messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (self.max_messages,),
            ).fetchall()

        # rows vienen del más reciente al más antiguo. Invertir para orden cronológico
        chronological = list(reversed(rows))
        messages: list[ChatMessage] = []
        accumulated_tokens = 0

        # Iterar de atrás hacia adelante para garantizar que los más recientes entren en el límite de tokens
        selected: list[ChatMessage] = []
        for row in reversed(chronological):
            toks = row["estimated_tokens"] or estimate_tokens(row["content"])
            if (accumulated_tokens + toks) > self.max_tokens:
                break
            selected.append(ChatMessage(role=row["role"], content=row["content"]))
            accumulated_tokens += toks

        return list(reversed(selected))

    def save_turn(self, user_content: str, assistant_content: str) -> None:
        """Guarda el turno usuario-asistente y poda el historial si excede límites."""
        u_tokens = estimate_tokens(user_content)
        a_tokens = estimate_tokens(assistant_content)

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_messages (role, content, estimated_tokens)
                VALUES ('user', ?, ?)
                """,
                (user_content, u_tokens),
            )
            connection.execute(
                """
                INSERT INTO conversation_messages (role, content, estimated_tokens)
                VALUES ('assistant', ?, ?)
                """,
                (assistant_content, a_tokens),
            )
            self._prune(connection)

    def _prune(self, connection) -> None:
        """Poda mensajes antiguos para no exceder max_messages o max_tokens."""
        # 1. Poda por conteo de mensajes
        connection.execute(
            """
            DELETE FROM conversation_messages
            WHERE id NOT IN (
                SELECT id FROM conversation_messages
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (self.max_messages,),
        )

        # 2. Poda por tokens acumulados
        rows = connection.execute(
            "SELECT id, estimated_tokens FROM conversation_messages ORDER BY id DESC"
        ).fetchall()

        total = 0
        keep_ids: set[int] = set()
        for row in rows:
            t = row["estimated_tokens"]
            if (total + t) > self.max_tokens:
                break
            keep_ids.add(row["id"])
            total += t

        if len(keep_ids) < len(rows):
            placeholders = ",".join("?" for _ in keep_ids) if keep_ids else "0"
            connection.execute(
                f"DELETE FROM conversation_messages WHERE id NOT IN ({placeholders})",
                list(keep_ids),
            )

    def clear(self) -> int:
        with self.database.connect() as connection:
            result = connection.execute("DELETE FROM conversation_messages")
        return result.rowcount
