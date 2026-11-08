"""Background indexing and retry of persistent memories."""
import asyncio
import logging

from asistente.memory.explicit_memory import ExplicitMemoryStore

logger = logging.getLogger(__name__)


async def run_memory_indexer(store: ExplicitMemoryStore, interval: float = 30.0) -> None:
    while True:
        try:
            await asyncio.to_thread(store.index_pending)
        except Exception:
            logger.exception("Memory indexing batch failed; retrying later")
        await asyncio.sleep(interval)
