"""Schedule HTTP endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from asistente.automation.scheduler import LocalScheduler, ScheduleStore
from asistente.api.http_schemas import ReminderRequest, RoutineRequest


def create_schedule_router(
    schedule_store: ScheduleStore | None,
    scheduler: LocalScheduler | None
) -> APIRouter:
    router = APIRouter()

    @router.get("/schedule/events")
    async def scheduled_events() -> dict[str, object]:
        if scheduler is None:
            raise HTTPException(status_code=503, detail="El programador no está disponible.")
        return {"events": scheduler.drain_events()}

    @router.get("/reminders")
    async def list_reminders() -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        entries = await asyncio.to_thread(schedule_store.list_reminders)
        return {"reminders": [entry.to_dict() for entry in entries]}

    @router.post("/reminders")
    async def add_reminder(request: ReminderRequest) -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        try:
            entry = await asyncio.to_thread(schedule_store.add_reminder, request.title, request.due_at, request.action_type, request.access_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/reminders/{reminder_id}")
    async def delete_reminder(reminder_id: str) -> dict[str, bool]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="La agenda no está disponible.")
        deleted = await asyncio.to_thread(schedule_store.delete_reminder, reminder_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recordatorio no encontrado.")
        return {"deleted": True}

    @router.get("/routines")
    async def list_routines() -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        entries = await asyncio.to_thread(schedule_store.list_routines)
        return {"routines": [entry.to_dict() for entry in entries]}

    @router.post("/routines")
    async def add_routine(request: RoutineRequest) -> dict[str, object]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        try:
            entry = await asyncio.to_thread(schedule_store.add_routine, request.name, request.time_of_day, request.days, request.access_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/routines/{routine_id}")
    async def delete_routine(routine_id: str) -> dict[str, bool]:
        if schedule_store is None:
            raise HTTPException(status_code=503, detail="Las rutinas no están disponibles.")
        deleted = await asyncio.to_thread(schedule_store.delete_routine, routine_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Rutina no encontrada.")
        return {"deleted": True}

    return router
