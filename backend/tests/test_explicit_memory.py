from pathlib import Path

from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.storage.database import Database
from asistente.storage.migrations import migrate


def test_explicit_memory_works_without_embeddings(tmp_path: Path) -> None:
    database = Database(tmp_path / "asistente.sqlite3")
    migrate(database)
    memories = ExplicitMemoryStore(database)

    saved = memories.add("Mi nombre es Alex.")

    assert saved.content == "Mi nombre es Alex."
    assert memories.retrieve("nombre") == [saved]
