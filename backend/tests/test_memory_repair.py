import asyncio
from pathlib import Path

from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.memory.indexer import run_memory_indexer
from asistente.memory.conversation_store import ConversationStore
from asistente.storage.database import Database
from asistente.storage.migrations import migrate, MIGRATIONS


class Embeddings:
    model = 'test-v1'
    fail = False

    def embed(self, text, task_type):
        if self.fail:
            raise RuntimeError('offline')
        return [1.0, 0.0]


def make_store(tmp_path):
    db = Database(tmp_path / 'memory.sqlite3')
    migrate(db)
    return db, ExplicitMemoryStore(db)


def test_upgrade_preserves_memories(tmp_path):
    db = Database(tmp_path / 'old.sqlite3')
    with db.connect() as c:
        for version, script in enumerate(MIGRATIONS[:-1], 1):
            c.executescript(script)
            c.execute('INSERT INTO schema_migrations(version) VALUES (?)', (version,))
    saved = ExplicitMemoryStore(db).add('Mi color favorito es azul')
    migrate(db)
    migrate(db)
    assert ExplicitMemoryStore(db).list() == [saved]
    with db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM memory_embeddings').fetchone()[0] == 0


def test_offline_save_retry_semantic_reopen_and_delete(tmp_path, caplog):
    db, store = make_store(tmp_path)
    provider = Embeddings()
    provider.fail = True
    store.embeddings = provider
    saved = store.add('Mi color favorito es azul')
    assert store.index_pending() == 0
    assert store.retrieve('azul') == [saved]
    assert 'retry later' in caplog.text
    assert 'lexical recall' in caplog.text
    provider.fail = False
    assert store.index_pending() == 1
    reopened = ExplicitMemoryStore(Database(db.path), provider)
    assert reopened.retrieve('preferencia cromatica') == [saved]
    assert reopened.index_pending() == 0
    assert reopened.delete(saved.id)
    with db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM memory_embeddings').fetchone()[0] == 0


def test_old_records_batch_and_model_change(tmp_path):
    db, store = make_store(tmp_path)
    for i in range(3):
        store.add(f'Recuerdo {i}')
    provider = Embeddings()
    store.embeddings = provider
    assert store.index_pending(batch_size=2) == 2
    assert store.index_pending(batch_size=2) == 1
    replacement = Embeddings()
    replacement.model = 'test-v2'
    store.embeddings = replacement
    assert store.index_pending() == 3
    with db.connect() as c:
        assert {r[0] for r in c.execute('SELECT model FROM memory_embeddings')} == {'test-v2'}


def test_delete_during_embedding(tmp_path):
    db, store = make_store(tmp_path)
    saved = store.add('Un recuerdo')
    class DeletingProvider(Embeddings):
        def embed(self, text, task_type):
            store.delete(saved.id)
            return super().embed(text, task_type)
    store.embeddings = DeletingProvider()
    assert store.index_pending() == 0
    assert store.list() == []


def test_background_retries_and_stops(tmp_path):
    _, store = make_store(tmp_path)
    store.add('Recuerdo pendiente')
    provider = Embeddings()
    store.embeddings = provider
    async def scenario():
        task = asyncio.create_task(run_memory_indexer(store, interval=0.01))
        try:
            for _ in range(100):
                with store.database.connect() as c:
                    if c.execute('SELECT COUNT(*) FROM memory_embeddings').fetchone()[0]:
                        break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError('Background indexer did not run')
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    asyncio.run(scenario())


def test_conversation_survives_restart(tmp_path):
    db, _ = make_store(tmp_path)
    ConversationStore(db).save_turn('Hola', 'Buenos dias')
    history = ConversationStore(Database(db.path)).load_history()
    assert [m.content for m in history] == ['Hola', 'Buenos dias']
