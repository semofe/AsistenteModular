"""Memory HTTP endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.api.http_schemas import MemoryRequest


def create_memory_router(
    memory_store: ExplicitMemoryStore | None
) -> APIRouter:
    router = APIRouter()

    @router.get("/memories")
    async def list_memories() -> dict[str, object]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        entries = await asyncio.to_thread(memory_store.list)
        return {"memories": [entry.to_dict() for entry in entries]}

    @router.post("/memories")
    async def add_memory(request: MemoryRequest) -> dict[str, object]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        try:
            entry = await asyncio.to_thread(memory_store.add, request.content, request.category)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/memories/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        if memory_store is None:
            raise HTTPException(status_code=503, detail="La memoria no está disponible.")
        deleted = await asyncio.to_thread(memory_store.delete, memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recuerdo no encontrado.")
        return {"deleted": True}

    return router
