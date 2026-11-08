"""Servicio local que conecta comandos con el catálogo permitido."""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import monotonic

from asistente.access.catalog import AccessCatalog, AccessEntry, AccessMatch, normalize_name
from asistente.automation.local_parser import (
    has_uncertain_open_cue,
    is_probable_local_action,
    is_explicit_open_request,
    is_hide_assistant_command,
    is_quit_assistant_command,
    is_shutdown_command,
    parse_close_command,
    parse_probable_close_command,
    parse_minimize_command,
    parse_probable_minimize_command,
    parse_open_command,
    parse_probable_open_command,
    split_open_targets,
    is_likely_conversation_after_wake,
    wake_phrase_remainder,
)
from asistente.config.action_responses import ActionResponseStore
from asistente.tools.applications import (
    CloseResult,
    MinimizeResult,
    OpenResult,
    close_entry,
    minimize_entry,
    open_entry,
)
from asistente.tools.files import FileAccessError, FileAccessService
from asistente.tools.websites import WebAccessService, parse_platform_search
from asistente.access.web_catalog import WebsiteShortcut


CONFIRMATION_TIMEOUT_SECONDS = 120.0
POSITIVE_CONFIRMATIONS = {"si", "correcto", "confirmo", "hazlo", "adelante", "si hazlo"}
NEGATIVE_CONFIRMATIONS = {"no", "cancelar", "cancela", "dejalo", "no gracias"}


@dataclass(frozen=True, slots=True)
class LocalCommandResult:
    handled: bool
    response: str = ""
    entry: AccessEntry | None = None
    speech_fragments: list[str] | None = None
    client_action: str | None = None


@dataclass(slots=True)
class PendingAccessCommand:
    matches: list[AccessMatch]
    expires_at: float
    operation: str = "open"


@dataclass(slots=True)
class PendingWebsiteCommand:
    website: WebsiteShortcut
    expires_at: float


class AccessToolService:
    def __init__(
        self,
        catalog: AccessCatalog,
        responses: ActionResponseStore | None = None,
        web_tools: WebAccessService | None = None,
        file_access: FileAccessService | None = None,
    ) -> None:
        self.catalog = catalog
        self.responses = responses
        self.web_tools = web_tools
        self.file_access = file_access
        self.pending: PendingAccessCommand | None = None
        self.pending_website: PendingWebsiteCommand | None = None
        self.pending_shutdown_expires_at: float | None = None

    def _message(self, key: str, fallback: str) -> str:
        return self.responses.message(key) if self.responses else fallback

    def open(self, entry_id: str) -> OpenResult:
        return open_entry(self.catalog.get(entry_id))

    def success_message(self) -> str:
        return self._message("success", "¡Hecho!")

    def failure_message(self) -> str:
        return self._message("failed", "No pude completar la acción.")

    def unclear_message(self) -> str:
        return self._message("unclear", "Perdón, ¿puedes repetirlo?")

    def not_found_message(self) -> str:
        return self._message("not_found", "No tengo acceso a esa aplicación.")

    def unsupported_message(self) -> str:
        return self._message("unsupported", "Esa función todavía no está disponible.")

    def not_running_message(self) -> str:
        return self._message("not_running", "No encuentro esa aplicación abierta.")

    def recognizes(self, text: str, assistant_name: str) -> bool:
        """Indica si el texto puede resolverse localmente sin ejecutar la acción."""
        answer = normalize_name(text)
        if answer in POSITIVE_CONFIRMATIONS | NEGATIVE_CONFIRMATIONS:
            return bool(
                self.pending
                or self.pending_website
                or self.pending_shutdown_expires_at is not None
            )
        if (
            is_shutdown_command(text, assistant_name)
            or is_hide_assistant_command(text, assistant_name)
            or is_quit_assistant_command(text, assistant_name)
        ):
            return True
        requested = parse_open_command(text, assistant_name)
        if requested is None:
            requested = parse_probable_open_command(text, assistant_name)
        if requested is not None:
            if self.web_tools is not None and self.web_tools.can_open_request(requested):
                return True
            targets = split_open_targets(requested)
            return bool(targets) and all(
                self.catalog.resolve_exact(target) is not None
                or self.catalog.match(target) is not None
                for target in targets
            )
        for parser in (
            parse_close_command,
            parse_probable_close_command,
            parse_minimize_command,
            parse_probable_minimize_command,
        ):
            target = parser(text, assistant_name)
            if target is not None:
                return bool(split_open_targets(target)) and all(
                    self.catalog.resolve_exact(item) is not None
                    or self.catalog.match(item) is not None
                    for item in split_open_targets(target)
                )
        bare_name = wake_phrase_remainder(text, assistant_name)
        if bare_name is None:
            bare_name = normalize_name(text)
        bare_entry = self.catalog.resolve_exact(bare_name) if bare_name else None
        if bare_entry is not None and bare_entry.kind == "application":
            return True
        return bool(
            bare_name
            and self.web_tools is not None
            and self.web_tools.resolve_bare(bare_name) is not None
        )

    @staticmethod
    def _joined_names(matches: list[AccessMatch]) -> str:
        names = [match.entry.name for match in matches]
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} y {names[-1]}"

    def _confirmation_message(
        self, matches: list[AccessMatch], operation: str = "open"
    ) -> str:
        keys = {
            "open": ("confirm", "¿Quieres abrir {targets}?"),
            "close": ("confirm_close", "¿Quieres cerrar {targets}?"),
            "minimize": ("confirm_minimize", "¿Quieres minimizar {targets}?"),
        }
        key, fallback = keys[operation]
        template = self._message(key, fallback)
        return template.replace("{targets}", self._joined_names(matches))

    def _bare_open_confirmation(self, match: AccessMatch) -> LocalCommandResult:
        self.pending = PendingAccessCommand(
            [match], monotonic() + CONFIRMATION_TIMEOUT_SECONDS
        )
        spoken_name = match.entry.spoken_name or match.entry.name
        template = self._message("confirm_bare_open", "¿Abrir {targets}?")
        return LocalCommandResult(
            True,
            template.replace("{targets}", match.entry.name),
            speech_fragments=["¿Abrir", spoken_name],
        )

    def _bare_website_confirmation(self, website: WebsiteShortcut) -> LocalCommandResult:
        self.pending_website = PendingWebsiteCommand(
            website, monotonic() + CONFIRMATION_TIMEOUT_SECONDS
        )
        template = self._message("confirm_bare_open", "¿Abrir {targets}?")
        return LocalCommandResult(
            True,
            template.replace("{targets}", website.name),
            speech_fragments=["¿Abrir", website.name],
        )

    @staticmethod
    def _confirmation_fragments(
        matches: list[AccessMatch], operation: str = "open"
    ) -> list[str]:
        names = [match.entry.spoken_name or match.entry.name for match in matches]
        prefixes = {
            "open": "¿Quieres abrir",
            "close": "¿Quieres cerrar",
            "minimize": "¿Quieres minimizar",
        }
        fragments = [prefixes[operation]]
        for index, name in enumerate(names):
            if index == len(names) - 1 and index > 0:
                fragments.append("y")
            fragments.append(name)
        return fragments

    def _execute(
        self, matches: list[AccessMatch], operation: str = "open"
    ) -> LocalCommandResult:
        try:
            if operation == "close":
                results: list[CloseResult] = []
                blocked = False
                for match in matches:
                    try:
                        results.append(close_entry(match.entry))
                    except ValueError:
                        blocked = True
                if not any(result.closed for result in results):
                    if blocked and len(matches) == 1:
                        return LocalCommandResult(True, self.failure_message())
                    return LocalCommandResult(True, self.not_running_message())
            elif operation == "minimize":
                minimize_results: list[MinimizeResult] = [
                    minimize_entry(match.entry) for match in matches
                ]
                if not any(result.minimized for result in minimize_results):
                    return LocalCommandResult(True, self.not_running_message())
            else:
                for match in matches:
                    open_entry(match.entry)
        except (ValueError, RuntimeError, OSError):
            return LocalCommandResult(True, self.failure_message())
        for match in matches:
            if match.score < 1.0:
                self.catalog.add_alias(match.entry.id, match.query)
        return LocalCommandResult(
            True, self.success_message(), matches[0].entry if matches else None
        )

    def _handle_pending(self, text: str) -> LocalCommandResult | None:
        answer = normalize_name(text)
        if self.pending_shutdown_expires_at is not None:
            if monotonic() > self.pending_shutdown_expires_at:
                self.pending_shutdown_expires_at = None
            elif answer in POSITIVE_CONFIRMATIONS:
                self.pending_shutdown_expires_at = None
                return LocalCommandResult(
                    True, self.success_message(), client_action="shutdown_pc"
                )
            elif answer in NEGATIVE_CONFIRMATIONS:
                self.pending_shutdown_expires_at = None
                return LocalCommandResult(True, self._message("cancelled", "Entendido."))
            elif len(answer.split()) <= 3:
                return LocalCommandResult(True, self.unclear_message())
            else:
                self.pending_shutdown_expires_at = None
        if self.pending_website is not None:
            if monotonic() > self.pending_website.expires_at:
                self.pending_website = None
            elif answer in POSITIVE_CONFIRMATIONS:
                pending_website = self.pending_website
                self.pending_website = None
                try:
                    if self.web_tools is None:
                        return LocalCommandResult(True, self.failure_message())
                    self.web_tools.open_website(pending_website.website)
                    return LocalCommandResult(True, self.success_message())
                except (ValueError, RuntimeError, OSError):
                    return LocalCommandResult(True, self.failure_message())
            elif answer in NEGATIVE_CONFIRMATIONS:
                self.pending_website = None
                return LocalCommandResult(True, self._message("cancelled", "Entendido."))
            elif len(answer.split()) <= 3:
                return LocalCommandResult(True, self.unclear_message())
            else:
                self.pending_website = None
        if self.pending is None:
            return None
        if monotonic() > self.pending.expires_at:
            self.pending = None
            return None
        if answer in POSITIVE_CONFIRMATIONS:
            pending = self.pending
            self.pending = None
            return self._execute(pending.matches, pending.operation)
        if answer in NEGATIVE_CONFIRMATIONS:
            self.pending = None
            return LocalCommandResult(True, self._message("cancelled", "Entendido."))
        if len(answer.split()) <= 3:
            return LocalCommandResult(True, self.unclear_message())
        self.pending = None
        return None

    def handle(self, text: str, assistant_name: str) -> LocalCommandResult:
        is_confirmation = normalize_name(text) in POSITIVE_CONFIRMATIONS | NEGATIVE_CONFIRMATIONS
        if not is_confirmation and (
            self.pending or self.pending_website or self.pending_shutdown_expires_at is not None
        ) and (
            is_explicit_open_request(text)
            or parse_platform_search(text, assistant_name)
            or self.recognizes(text, assistant_name)
        ):
            self.pending = None
            self.pending_website = None
            self.pending_shutdown_expires_at = None
        if pending_result := self._handle_pending(text):
            return pending_result
        if is_confirmation:
            return LocalCommandResult(True, self.unclear_message())
        if is_shutdown_command(text, assistant_name):
            self.pending_shutdown_expires_at = (
                monotonic() + CONFIRMATION_TIMEOUT_SECONDS
            )
            return LocalCommandResult(
                True,
                self._message("confirm_shutdown", "¿Deseas apagar la PC?"),
                speech_fragments=["¿Deseas apagar", "la PC"],
            )
        if is_hide_assistant_command(text, assistant_name):
            return LocalCommandResult(
                True, self.success_message(), client_action="hide_assistant"
            )
        if is_quit_assistant_command(text, assistant_name):
            return LocalCommandResult(
                True, self.success_message(), client_action="quit_assistant"
            )
        if self.web_tools is not None:
            search = parse_platform_search(text, assistant_name)
            if search:
                try:
                    platform, query = search
                    if platform == "website":
                        site, needs_confirmation = self.web_tools.resolve_navigation(query)
                        if site is not None:
                            if needs_confirmation:
                                return self._bare_website_confirmation(site)
                            self.web_tools.open_website(site)
                        else:
                            self.web_tools.open_search("google", query)
                    else:
                        self.web_tools.open_search(platform, query)
                    return LocalCommandResult(True, self.success_message())
                except (ValueError, RuntimeError, OSError):
                    return LocalCommandResult(True, self.failure_message())
        close_request = parse_close_command(text, assistant_name)
        close_recovered = False
        if close_request is None:
            close_request = parse_probable_close_command(text, assistant_name)
            close_recovered = close_request is not None
        if close_request is not None:
            return self._handle_close(text, close_request, close_recovered)
        minimize_request = parse_minimize_command(text, assistant_name)
        minimize_recovered = False
        if minimize_request is None:
            minimize_request = parse_probable_minimize_command(text, assistant_name)
            minimize_recovered = minimize_request is not None
        if minimize_request is not None:
            return self._handle_minimize(minimize_request, minimize_recovered)
        requested = parse_open_command(text, assistant_name)
        recovered_from_stt = False
        if requested is None:
            requested = parse_probable_open_command(text, assistant_name)
            recovered_from_stt = requested is not None
        if requested is None:
            bare_name = wake_phrase_remainder(text, assistant_name)
            if bare_name is None:
                bare_name = normalize_name(text)
            if bare_name:
                bare_entry = self.catalog.resolve_exact(bare_name)
                if bare_entry is not None and bare_entry.kind == "application":
                    return self._bare_open_confirmation(
                        AccessMatch(bare_entry, bare_name, 1.0)
                    )
                if self.web_tools is not None:
                    website = self.web_tools.resolve_bare(bare_name)
                    if website is not None:
                        return self._bare_website_confirmation(website)
            if is_explicit_open_request(text):
                return LocalCommandResult(
                    True, self.unclear_message()
                )
            if is_probable_local_action(text, assistant_name):
                return LocalCommandResult(True, self.unsupported_message())
            if not is_likely_conversation_after_wake(text, assistant_name):
                return LocalCommandResult(True, self.unclear_message())
            return LocalCommandResult(False)
        targets = split_open_targets(requested)
        if self.web_tools is not None:
            try:
                if self.web_tools.open_request(requested):
                    return LocalCommandResult(True, self.success_message())
            except (ValueError, RuntimeError, OSError):
                return LocalCommandResult(True, self.failure_message())
        exact = self.catalog.resolve_exact(requested)
        if exact is not None:
            matches = [AccessMatch(exact, requested, 1.0)]
        elif len(targets) > 1:
            matches = [self.catalog.match(target) for target in targets]
        else:
            matches = [self.catalog.match(requested)]
        if not matches or any(item is None for item in matches):
            if self.file_access is not None and not recovered_from_stt and is_explicit_open_request(text):
                if file_result := self._open_authorized_file(requested):
                    return file_result
            if not recovered_from_stt and not is_explicit_open_request(text):
                return LocalCommandResult(False)
            return LocalCommandResult(
                True,
                self.not_found_message(),
            )
        resolved_matches = [item for item in matches if item is not None]
        needs_confirmation = recovered_from_stt or has_uncertain_open_cue(text) or any(
            match.score < 0.95 for match in resolved_matches
        )
        if needs_confirmation:
            self.pending = PendingAccessCommand(
                resolved_matches, monotonic() + CONFIRMATION_TIMEOUT_SECONDS
            )
            return LocalCommandResult(
                True,
                self._confirmation_message(resolved_matches),
                speech_fragments=self._confirmation_fragments(resolved_matches),
            )
        return self._execute(resolved_matches)

    def _open_authorized_file(self, requested: str) -> LocalCommandResult | None:
        if self.file_access is None:
            return None
        try:
            matches = self.file_access.find_openable(requested)
            if not matches:
                return None
            if len(matches) > 1:
                choices = "\n".join(f"- {path.name} ({path.parent})" for path in matches[:5])
                return LocalCommandResult(
                    True,
                    "Encontré varios archivos. Repite «Abre» con el nombre completo "
                    "y, si hace falta, añade «en» y el nombre de la carpeta.\n" + choices,
                )
            os.startfile(str(matches[0]))
        except FileAccessError as exc:
            return LocalCommandResult(True, str(exc))
        except (OSError, AttributeError):
            return LocalCommandResult(True, self.failure_message())
        return LocalCommandResult(True, self.success_message())

    def _handle_close(
        self, text: str, requested: str, recovered_from_stt: bool = False
    ) -> LocalCommandResult:
        normalized = normalize_name(requested)
        close_all = normalized in {
            "todo", "todas", "todas las aplicaciones", "todo lo abierto",
        }
        if close_all:
            entries = [
                entry for entry in self.catalog.list()
                if entry.enabled and entry.kind == "application"
            ]
            matches = [AccessMatch(entry, entry.name, 1.0) for entry in entries]
            if not matches:
                return LocalCommandResult(True, self.not_running_message())
        else:
            targets = split_open_targets(requested)
            exact = self.catalog.resolve_exact(requested)
            if exact is not None:
                matches = [AccessMatch(exact, requested, 1.0)]
            elif len(targets) > 1:
                matches = [self.catalog.match(target) for target in targets]
            else:
                matches = [self.catalog.match(requested)]
            if not matches or any(item is None for item in matches):
                return LocalCommandResult(True, self.not_found_message())
            matches = [item for item in matches if item is not None]
            if any(match.entry.kind != "application" for match in matches):
                return LocalCommandResult(True, self.not_found_message())
        needs_confirmation = recovered_from_stt or any(
            match.score < 0.95 for match in matches
        )
        if needs_confirmation:
            self.pending = PendingAccessCommand(
                matches,
                monotonic() + CONFIRMATION_TIMEOUT_SECONDS,
                operation="close",
            )
            return LocalCommandResult(
                True,
                self._confirmation_message(matches, "close"),
                speech_fragments=self._confirmation_fragments(matches, "close"),
            )
        return self._execute(matches, "close")

    def _handle_minimize(
        self, requested: str, recovered_from_stt: bool = False
    ) -> LocalCommandResult:
        normalized = normalize_name(requested)
        minimize_all = normalized in {
            "todo", "todas", "todas las aplicaciones", "todo lo abierto",
        }
        if minimize_all:
            entries = [
                entry for entry in self.catalog.list()
                if entry.enabled and entry.kind == "application"
            ]
            matches = [AccessMatch(entry, entry.name, 1.0) for entry in entries]
            if not matches:
                return LocalCommandResult(True, self.not_running_message())
        else:
            targets = split_open_targets(requested)
            exact = self.catalog.resolve_exact(requested)
            if exact is not None:
                matches = [AccessMatch(exact, requested, 1.0)]
            elif len(targets) > 1:
                matches = [self.catalog.match(target) for target in targets]
            else:
                matches = [self.catalog.match(requested)]
            if not matches or any(item is None for item in matches):
                return LocalCommandResult(True, self.not_found_message())
            matches = [item for item in matches if item is not None]
            if any(match.entry.kind != "application" for match in matches):
                return LocalCommandResult(True, self.not_found_message())
        if recovered_from_stt or any(match.score < 0.95 for match in matches):
            self.pending = PendingAccessCommand(
                matches,
                monotonic() + CONFIRMATION_TIMEOUT_SECONDS,
                operation="minimize",
            )
            return LocalCommandResult(
                True,
                self._confirmation_message(matches, "minimize"),
                speech_fragments=self._confirmation_fragments(matches, "minimize"),
            )
        return self._execute(matches, "minimize")
