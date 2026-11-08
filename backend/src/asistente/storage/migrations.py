"""Migraciones incrementales de la base local."""

from __future__ import annotations

from asistente.storage.database import Database


MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS access_entries (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        kind TEXT NOT NULL CHECK(kind IN ('application', 'file', 'folder')),
        target TEXT NOT NULL,
        aliases_json TEXT NOT NULL DEFAULT '[]',
        arguments_json TEXT NOT NULL DEFAULT '[]',
        working_directory TEXT,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS access_entries_name
        ON access_entries(name COLLATE NOCASE);
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    ALTER TABLE access_entries ADD COLUMN spoken_name TEXT;
    """,
    """
    ALTER TABLE access_entries ADD COLUMN close_policy TEXT NOT NULL DEFAULT 'process'
        CHECK(close_policy IN ('process', 'window'));

    CREATE TABLE IF NOT EXISTS browser_config (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        name TEXT NOT NULL,
        activation_word TEXT NOT NULL,
        executable TEXT NOT NULL,
        aliases_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS website_shortcuts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        url TEXT NOT NULL,
        aliases_json TEXT NOT NULL DEFAULT '[]',
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS website_shortcuts_name
        ON website_shortcuts(name COLLATE NOCASE);
    """,
    """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        normalized_content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS memories_updated_at ON memories(updated_at DESC);

    CREATE TABLE IF NOT EXISTS reminders (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        due_at TEXT NOT NULL,
        action_type TEXT NOT NULL DEFAULT 'notify'
            CHECK(action_type IN ('notify', 'open_access')),
        access_id TEXT REFERENCES access_entries(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending', 'completed', 'cancelled', 'failed')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    );
    CREATE INDEX IF NOT EXISTS reminders_due_at ON reminders(status, due_at);

    CREATE TABLE IF NOT EXISTS routines (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        time_of_day TEXT NOT NULL,
        days_json TEXT NOT NULL DEFAULT '[]',
        access_ids_json TEXT NOT NULL DEFAULT '[]',
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
        last_run_date TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS routines_name ON routines(name COLLATE NOCASE);
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        estimated_tokens INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_embeddings (
        memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
        model TEXT NOT NULL,
        vector_json TEXT NOT NULL
    );
    """,
]


def migrate(database: Database) -> None:
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {
            int(row[0])
            for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for version, script in enumerate(MIGRATIONS, start=1):
            if version in applied:
                continue
            connection.executescript(script)
            connection.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
            )
