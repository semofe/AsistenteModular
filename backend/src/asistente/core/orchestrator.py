"""Punto de entrada de conversación de Asistente Modular."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
from datetime import datetime, timedelta

from asistente.config.assistant_profile import AssistantProfileStore
from asistente.core.fixed_responses import FixedResponseMatcher
from asistente.memory.explicit_memory import ExplicitMemoryStore
from asistente.automation.scheduler import ScheduleStore
from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult, SourceCitation
from asistente.tools.files import FileAccessError, FileAccessService
from asistente.tools.registry import AccessToolService
from asistente.tools.websites import parse_platform_search
from asistente.memory.conversation_store import ConversationStore, estimate_tokens
from asistente.tools.file_dispatcher import FileToolService, TOOL_INSTRUCTIONS


@dataclass(slots=True)
class AssistantReply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    session_tokens: int = 0
    speech_fragments: list[str] | None = None
    client_action: str | None = None
    sources: list[SourceCitation] | None = None


class Orchestrator:
    def __init__(
        self,
        provider: ChatProvider | None,
        personality_path: Path,
        fixed_responses_path: Path | None = None,
        assistant_profile: AssistantProfileStore | None = None,
        access_tools: AccessToolService | None = None,
        memory_store: ExplicitMemoryStore | None = None,
        schedule_store: ScheduleStore | None = None,
        file_access: FileAccessService | None = None,
        max_history_messages: int = 20,
        max_history_tokens: int = 12000,
        conversation_store: ConversationStore | None = None,
        file_tools: FileToolService | None = None,
    ) -> None:
        self.provider = provider
        self.personality_path = personality_path
        self.assistant_profile = assistant_profile
        self.access_tools = access_tools
        self.memory_store = memory_store
        self.schedule_store = schedule_store
        self.file_access = file_access
        self.fixed_responses = (
            FixedResponseMatcher(
                fixed_responses_path,
                assistant_profile.variables if assistant_profile else None,
            )
            if fixed_responses_path
            else None
        )
        self.history: deque[ChatMessage] = deque(maxlen=max_history_messages)
        self.session_tokens = 0
        self.max_history_tokens = max_history_tokens
        self.conversation_store = conversation_store
        self.file_tools = file_tools
        if conversation_store is not None:
            self.history.extend(conversation_store.load_history())

    def _extend_history(self, messages: list[ChatMessage]) -> None:
        self.history.extend(messages)
        while self.history and sum(estimate_tokens(m.content) for m in self.history) > self.max_history_tokens:
            self.history.popleft()
            if self.history:
                self.history.popleft()
        if self.conversation_store is not None and len(messages) == 2:
            self.conversation_store.save_turn(messages[0].content, messages[1].content)

    def _personality(self) -> str:
        try:
            personality = self.personality_path.read_text(encoding="utf-8").strip()
        except OSError:
            personality = (
                "Eres {assistant_name}, una asistente útil, clara y amable. "
                "Responde en español."
            )
        variables = self.assistant_profile.variables() if self.assistant_profile else {}
        for key, value in variables.items():
            personality = personality.replace(f"{{{key}}}", value)
        return personality


    @staticmethod
    def _local_time_context() -> str:
        now = datetime.now().astimezone()
        return (
            "Contexto fiable del equipo: la fecha y hora local actuales son "
            f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')}. Úsalo para responder "
            "consultas relativas a fecha y hora; no afirmes que no tienes acceso a ella."
        )

    @staticmethod
    def _current_time_reply(text: str) -> str | None:
        normalized = " ".join(re.sub(r"[^a-záéíóúüñ0-9]+", " ", text.lower()).split())
        asks_date = bool(re.search(r"\b(fecha|dia|día)\s+(actual|de hoy|es hoy)\b|\bqu[eé] fecha|\bqu[eé] dia", normalized))
        asks_time = bool(re.search(r"\b(hora|horario)\s+(actual|es)\b|\bque hora", normalized))
        if not (asks_date or asks_time):
            return None
        now = datetime.now().astimezone()
        weekdays = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
        months = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        date = f"{weekdays[now.weekday()]} {now.day} de {months[now.month - 1]} de {now.year}"
        if asks_date and asks_time:
            return f"Hoy es {date} y son las {now:%H:%M}."
        if asks_time:
            return f"Son las {now:%H:%M}."
        return f"Hoy es {date}."

    async def handle_text(self, text: str) -> AssistantReply:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("El mensaje está vacío.")
        if self.file_tools is not None:
            confirmed = await self.file_tools.confirm(clean_text)
            if confirmed is not None:
                self._extend_history([ChatMessage(role="user", content=clean_text), ChatMessage(role="assistant", content=confirmed)])
                return AssistantReply(text=confirmed, session_tokens=self.session_tokens)
        assistant_name = self.assistant_profile.get()["name"] if self.assistant_profile else ""
        web_request = parse_platform_search(clean_text, assistant_name)
        file_request = self.file_tools is not None and (
            self.file_tools.is_request(clean_text) or self.file_tools.awaiting_details
        ) and not web_request
        if current_time := self._current_time_reply(clean_text):
            self._extend_history([
                ChatMessage(role="user", content=clean_text),
                ChatMessage(role="assistant", content=current_time),
            ])
            return AssistantReply(text=current_time, session_tokens=self.session_tokens)
        if self.memory_store is not None:
            captured = await asyncio.to_thread(self.memory_store.capture_from_command, clean_text)
            if captured is not None:
                response = "Lo recordaré."
                self._extend_history([
                    ChatMessage(role="user", content=clean_text),
                    ChatMessage(role="assistant", content=response),
                ])
                return AssistantReply(text=response, session_tokens=self.session_tokens)
        scheduled = self._handle_schedule_command(clean_text)
        if scheduled is not None:
            self._extend_history([ChatMessage(role="user", content=clean_text), ChatMessage(role="assistant", content=scheduled)])
            return AssistantReply(text=scheduled, session_tokens=self.session_tokens)
        if self.access_tools is not None and not file_request:
            if web_request and web_request[0] == "website":
                local = await asyncio.to_thread(self.access_tools.handle, clean_text, assistant_name)
            else:
                local = self.access_tools.handle(clean_text, assistant_name)
            if local.handled:
                self._extend_history(
                    [
                        ChatMessage(role="user", content=clean_text),
                        ChatMessage(role="assistant", content=local.response),
                    ]
                )
                return AssistantReply(
                    text=local.response,
                    session_tokens=self.session_tokens,
                    speech_fragments=local.speech_fragments,
                    client_action=local.client_action,
                )
        fixed = self.fixed_responses.match(clean_text) if self.fixed_responses else None
        if fixed:
            user_message = ChatMessage(role="user", content=clean_text)
            self._extend_history(
                [user_message, ChatMessage(role="assistant", content=fixed.response)]
            )
            return AssistantReply(text=fixed.response, session_tokens=self.session_tokens)
        if self.provider is None:
            return AssistantReply(
                text=(
                    "Gemini todavía no está configurado. Añade tu clave API en Ajustes "
                    "o define GEMINI_API_KEY y reinicia el backend."
                )
            )

        user_message = ChatMessage(role="user", content=clean_text)
        file_context = ""
        if self.file_access is not None and not file_request:
            try:
                requested_path = self.file_access.resolve_from_request(clean_text)
                if requested_path is not None:
                    path, content = self.file_access.read(requested_path)
                    file_context = (
                        f"Contenido autorizado del archivo local {path.name}. "
                        "Úsalo solamente para responder la petición actual del usuario:\n\n"
                        f"{content}"
                    )
            except FileAccessError as exc:
                return AssistantReply(text=str(exc), session_tokens=self.session_tokens)
        recalled = await asyncio.to_thread(self.memory_store.retrieve, clean_text) if self.memory_store else []
        memory_context = ""
        if recalled:
            memory_context = "Recuerdos explícitos del usuario (úsalos solo si son pertinentes):\n" + "\n".join(
                f"- {memory.content}" for memory in recalled
            )
        messages = [
            ChatMessage(role="system", content=self._personality()),
            ChatMessage(role="system", content=self._local_time_context()),
            ChatMessage(
                role="system",
                content=(
                    "Adapta la extensión de la respuesta a la petición del usuario. "
                    "Las acciones sobre el "
                    "equipo las confirma exclusivamente el sistema de herramientas. "
                    "Nunca afirmes que abriste, ejecutaste, creaste o modificaste algo. "
                    "Si el mensaje no es comprensible o no permite inferir una petición, "
                    "responde exactamente: Perdón, ¿puedes repetirlo?"
                ),
            ),
            *([ChatMessage(role="system", content=file_context)] if file_context else []),
            *([ChatMessage(role="system", content=memory_context)] if memory_context else []),
            *([ChatMessage(role="system", content=TOOL_INSTRUCTIONS)] if file_request else []),
            *self.history,
            user_message,
        ]
        result: GenerationResult = await self.provider.generate(messages)
        if file_request and self.file_tools is not None:
            tool_response = await self.file_tools.handle(result.text)
            if tool_response is not None:
                result.text = tool_response
        if not file_request and self.access_tools is not None and re.match(
            r"^\s*[¡!¿?]*(?:hecho|listo|abriendo)\b",
            result.text,
            flags=re.IGNORECASE,
        ):
            result.text = self.access_tools.failure_message()
        elif not file_request and self.access_tools is not None and re.search(
            r"(?:no\s+(?:puedo|podemos|me\s+es\s+posible|tengo\s+(?:la\s+)?capacidad\s+de)\s+"
            r"(?:abrir|acceder|ejecutar|iniciar)|no\s+tengo\s+acceso\s+(?:directo\s+)?a)",
            result.text,
            flags=re.IGNORECASE,
        ) and re.search(
            r"(?:aplicacion|aplicación|programa|archivo|carpeta|equipo|pc|computadora)",
            result.text,
            flags=re.IGNORECASE,
        ):
            result.text = self.access_tools.not_found_message()
        elif not file_request and self.access_tools is not None and re.search(
            r"(?:no (?:entendi|entendí|comprendi|comprendí)|"
            r"(?:puedes|podrias|podrías) repetir|no tiene sentido|"
            r"no (?:queda|esta|está) claro)",
            result.text,
            flags=re.IGNORECASE,
        ):
            result.text = self.access_tools.unclear_message()
        self._extend_history(
            [user_message, ChatMessage(role="assistant", content=result.text)]
        )
        self.session_tokens += result.total_tokens
        return AssistantReply(
            text=result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            thinking_tokens=result.thinking_tokens,
            total_tokens=result.total_tokens,
            session_tokens=self.session_tokens,
        )

    def clear_conversation(self) -> None:
        self.history.clear()
        self.session_tokens = 0
        if self.conversation_store is not None:
            self.conversation_store.clear()
        if self.file_tools is not None:
            self.file_tools.pending = None
            self.file_tools.awaiting_details = False

    def _handle_schedule_command(self, text: str) -> str | None:
        """Comandos de agenda que no necesitan consumir tokens."""
        if self.schedule_store is None:
            return None
        reminder = re.match(
            r"^\s*(?:oye\s+\w+[, ]+)?(?:recuerdame|recuérdame)\s+(.+?)\s+(?:a las|a la)\s+(\d{1,2})(?::(\d{2}))?\s*$",
            text, flags=re.IGNORECASE,
        )
        if reminder:
            title, hour, minute = reminder.group(1), int(reminder.group(2)), int(reminder.group(3) or 0)
            if hour > 23 or minute > 59:
                return "La hora no es válida."
            now = datetime.now().astimezone()
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            self.schedule_store.add_reminder(title, due.isoformat())
            return "Recordatorio guardado."
        routine = re.match(
            r"^\s*(?:oye\s+\w+[, ]+)?(?:crea|programa)\s+(?:una\s+)?rutina\s+(.+?)\s+(?:a las|a la)\s+(\d{1,2})(?::(\d{2}))?\s+(?:abre|abrir)\s+(.+?)\s*$",
            text, flags=re.IGNORECASE,
        )
        if routine and self.access_tools is not None:
            name, hour, minute, targets = routine.groups()
            hour_value, minute_value = int(hour), int(minute or 0)
            if hour_value > 23 or minute_value > 59:
                return "La hora no es válida."
            access_ids: list[str] = []
            for target in re.split(r"\s+(?:y|e)\s+|\s*,\s*", targets):
                exact_entry = self.access_tools.catalog.resolve_exact(target)
                match = None if exact_entry is not None else self.access_tools.catalog.match(target)
                if exact_entry is None and match is None:
                    return self.access_tools.not_found_message()
                access_ids.append(exact_entry.id if exact_entry is not None else match.entry.id)
            self.schedule_store.add_routine(name, f"{hour_value:02d}:{minute_value:02d}", list(range(7)), access_ids)
            return "Rutina guardada."
        return None
