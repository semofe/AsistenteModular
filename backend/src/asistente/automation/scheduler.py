"""Recordatorios y rutinas locales, sin depender de un modelo de lenguaje."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from uuid import uuid4

from asistente.storage.database import Database
from asistente.tools.registry import AccessToolService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Reminder:
    id: str
    title: str
    due_at: str
    action_type: str
    access_id: str | None
    status: str
    created_at: str
    completed_at: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Routine:
    id: str
    name: str
    time_of_day: str
    days: list[int]
    access_ids: list[str]
    enabled: bool
    last_run_date: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ScheduleStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _reminder(row: object) -> Reminder:
        return Reminder(**dict(row))

    @staticmethod
    def _routine(row: object) -> Routine:
        return Routine(
            id=row["id"], name=row["name"], time_of_day=row["time_of_day"],
            days=[int(day) for day in json.loads(row["days_json"])],
            access_ids=[str(value) for value in json.loads(row["access_ids_json"])],
            enabled=bool(row["enabled"]), last_run_date=row["last_run_date"],
        )

    def list_reminders(self) -> list[Reminder]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM reminders ORDER BY due_at ASC").fetchall()
        return [self._reminder(row) for row in rows]

    def add_reminder(self, title: str, due_at: str, action_type: str = "notify", access_id: str | None = None) -> Reminder:
        clean = " ".join(title.split())
        if not clean:
            raise ValueError("El recordatorio necesita un título.")
        due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due <= _utc_now():
            raise ValueError("La fecha del recordatorio debe estar en el futuro.")
        if action_type not in {"notify", "open_access"}:
            raise ValueError("Tipo de acción no válido.")
        if action_type == "open_access" and not access_id:
            raise ValueError("Selecciona el acceso que se debe abrir.")
        identifier = str(uuid4())
        now = _utc_now().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO reminders(id, title, due_at, action_type, access_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, clean, due.astimezone(timezone.utc).isoformat(), action_type, access_id, now),
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (identifier,)).fetchone()
        return self._reminder(row)

    def delete_reminder(self, identifier: str) -> bool:
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM reminders WHERE id = ?", (identifier,)).rowcount > 0

    def list_routines(self) -> list[Routine]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM routines ORDER BY time_of_day, name").fetchall()
        return [self._routine(row) for row in rows]

    def add_routine(self, name: str, time_of_day: str, days: list[int], access_ids: list[str]) -> Routine:
        try:
            datetime.strptime(time_of_day, "%H:%M")
        except ValueError as exc:
            raise ValueError("La hora debe usar el formato HH:MM.") from exc
        clean_days = sorted(set(int(day) for day in days))
        if any(day < 0 or day > 6 for day in clean_days):
            raise ValueError("Los días deben estar entre 0 (lunes) y 6 (domingo).")
        if not access_ids:
            raise ValueError("La rutina necesita al menos un acceso.")
        identifier = str(uuid4())
        now = _utc_now().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO routines(id, name, time_of_day, days_json, access_ids_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (identifier, " ".join(name.split()), time_of_day, json.dumps(clean_days), json.dumps(access_ids), now, now),
            )
            row = connection.execute("SELECT * FROM routines WHERE id = ?", (identifier,)).fetchone()
        return self._routine(row)

    def delete_routine(self, identifier: str) -> bool:
        with self.database.connect() as connection:
            return connection.execute("DELETE FROM routines WHERE id = ?", (identifier,)).rowcount > 0

    def due_reminders(self, now: datetime) -> list[Reminder]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reminders WHERE status = 'pending' AND due_at <= ?", (now.isoformat(),)
            ).fetchall()
        return [self._reminder(row) for row in rows]

    def complete_reminder(self, identifier: str, status: str = "completed") -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE reminders SET status = ?, completed_at = ? WHERE id = ?", (status, _utc_now().isoformat(), identifier))

    def due_routines(self, now: datetime) -> list[Routine]:
        clock = now.astimezone().strftime("%H:%M")
        today = now.astimezone().date().isoformat()
        weekday = now.astimezone().weekday()
        return [routine for routine in self.list_routines() if routine.enabled and routine.time_of_day == clock and weekday in routine.days and routine.last_run_date != today]

    def complete_routine(self, identifier: str, date: str) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE routines SET last_run_date = ?, updated_at = ? WHERE id = ?", (date, _utc_now().isoformat(), identifier))


class LocalScheduler:
    def __init__(self, store: ScheduleStore, access_tools: AccessToolService) -> None:
        self.store, self.access_tools = store, access_tools
        self._task: asyncio.Task[None] | None = None
        self.events: list[str] = []

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="asistente-local-scheduler")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(20)

    async def tick(self) -> None:
        now = _utc_now()
        for reminder in self.store.due_reminders(now):
            status = "completed"
            if reminder.action_type == "open_access" and reminder.access_id:
                try:
                    await asyncio.to_thread(self.access_tools.open, reminder.access_id)
                except Exception:
                    status = "failed"
            self.events.append(f"Recordatorio: {reminder.title}")
            self.events[:] = self.events[-50:]
            self.store.complete_reminder(reminder.id, status)
        date = now.astimezone().date().isoformat()
        for routine in self.store.due_routines(now):
            for access_id in routine.access_ids:
                try:
                    await asyncio.to_thread(self.access_tools.open, access_id)
                except Exception:
                    continue
            self.store.complete_routine(routine.id, date)
            self.events.append(f"Rutina ejecutada: {routine.name}")
            self.events[:] = self.events[-50:]

    def drain_events(self) -> list[str]:
        events = list(self.events)
        self.events.clear()
        return events
