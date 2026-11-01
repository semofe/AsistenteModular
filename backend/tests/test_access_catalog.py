import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from asistente.access.catalog import AccessCatalog, AccessEntry, AccessMatch
from asistente.access.web_catalog import BrowserConfig, WebsiteShortcut
from asistente.config.activation import ActivationSettingsStore
from asistente.access.path_policy import PathPolicyError
from asistente.automation.local_parser import (
    is_hide_assistant_command,
    is_probable_local_action,
    is_quit_assistant_command,
    is_shutdown_command,
    is_likely_conversation_after_wake,
    parse_close_command,
    parse_minimize_command,
    parse_probable_close_command,
    parse_probable_minimize_command,
    parse_open_command,
    parse_probable_open_command,
    split_open_targets,
)
from asistente.storage.database import Database
from asistente.storage.migrations import migrate
from asistente.core.orchestrator import Orchestrator
from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult
from asistente.tools.registry import AccessToolService
from asistente.tools.applications import CloseResult, MinimizeResult, close_entry
from asistente.tools.websites import WebAccessService


def test_catalog_resolves_only_registered_names_and_aliases(tmp_path: Path) -> None:
    target = tmp_path / "manual.txt"
    target.write_text("contenido", encoding="utf-8")
    database = Database(tmp_path / "asistente.sqlite3")
    migrate(database)
    catalog = AccessCatalog(database)

    entry = catalog.add("Manual", "file", str(target), ["documentación"])

    assert catalog.resolve("manual") == entry
    assert catalog.resolve("documentacion") == entry
    assert catalog.resolve("documentacion de la tuya") == entry
    match = catalog.match("el manual de la tuya")
    assert match is not None and match.entry == entry and match.score < 0.95
    assert catalog.resolve("otro archivo") is None


def test_catalog_rejects_missing_targets(tmp_path: Path) -> None:
    database = Database(tmp_path / "asistente.sqlite3")
    migrate(database)
    catalog = AccessCatalog(database)

    with pytest.raises(PathPolicyError):
        catalog.add("Inexistente", "file", str(tmp_path / "missing.txt"))


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("Abre la calculadora", "calculadora"),
        ("Abra el bloque de notas.", "bloque de notas"),
        ("Ábrame el bloc de notas", "bloc de notas"),
        ("Quiero abrir Discord", "discord"),
        ("Necesito abrir Steam", "steam"),
        ("¿Puedes abrirme Spotify?", "spotify"),
        ("Arranca el juego", "juego"),
        ("Oye Asistente Modular, abre mi carpeta de juegos", "carpeta de juegos"),
        ("Por favor ejecuta Steam", "steam"),
        ("A ver el explorador de la tuya", "explorador de la tuya"),
        ("¿Me puedes abrir el explorador de archivos?", "explorador de archivos"),
        ("Borra todos mis archivos", None),
        ("Ejecuta rm -rf", "rm rf"),
    ],
)
def test_local_parser_only_recognizes_open_verbs(command: str, expected: str | None) -> None:
    assert parse_open_command(command, "Asistente Modular") == expected


def test_wake_name_is_dynamic() -> None:
    assert parse_open_command("Oye Luna, abre Steam", "Luna") == "steam"
    assert parse_open_command("Oye Asistente Modular, abre Steam", "Luna") is None


def test_probable_command_recovers_common_stt_errors() -> None:
    assert (
        parse_probable_open_command("Oye asiste modular abre bloque de notas.", "Asistente Modular")
        == "bloque de notas"
    )
    assert parse_probable_open_command("Hablemos de abril de 2025", "Asistente Modular") is None


def test_local_action_detector_preserves_normal_questions() -> None:
    assert is_probable_local_action("Oye Asistente Modular, cierra Spotify", "Asistente Modular") is True
    assert is_probable_local_action("Crea un recordatorio", "Asistente Modular") is True
    assert is_probable_local_action("¿Cómo puedo crear un archivo?", "Asistente Modular") is False
    assert is_probable_local_action("Oye Asistente Modular, ¿qué hora es?", "Asistente Modular") is False


def test_close_and_power_commands_are_parsed_locally() -> None:
    assert parse_close_command("Cierra Steam", "Asistente Modular") == "steam"
    assert parse_close_command("Cierras Steam", "Asistente Modular") == "steam"
    assert parse_close_command("Cierra Steam y Discord", "Asistente Modular") == "steam y discord"
    assert parse_close_command("Cierra todas las aplicaciones", "Asistente Modular") == "todas las aplicaciones"
    assert is_quit_assistant_command("Oye Asistente Modular, apágate", "Asistente Modular") is True
    assert is_shutdown_command("Apaga la PC", "Asistente Modular") is True


@pytest.mark.parametrize(
    "command",
    [
        "Eso es todo", "Eso es todo Asistente Modular", "Esto es todo", "Esto es todo Asistente Modular",
        "Gracias Asistente Modular", "Es todo Asistente Modular",
        "Minimízate", "Minimízate Asistente Modular", "Oye Asistente Modular, eso es todo",
    ],
)
def test_hide_assistant_phrases_are_dynamic(command: str) -> None:
    assert is_hide_assistant_command(command, "Asistente Modular") is True


@pytest.mark.parametrize(
    "command", ["Apágate", "Apágate Asistente Modular", "Ciérrate", "Ciérrate Asistente Modular", "Oye Asistente Modular, apágate"],
)
def test_quit_assistant_accepts_name_after_command(command: str) -> None:
    assert is_quit_assistant_command(command, "Asistente Modular") is True


def test_hide_assistant_is_a_local_client_action() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

    result = AccessToolService(Catalog()).handle("Gracias Asistente Modular", "Asistente Modular")  # type: ignore[arg-type]

    assert result.handled is True
    assert result.response == "¡Hecho!"
    assert result.client_action == "hide_assistant"


def test_minimize_commands_and_stt_variants_are_parsed() -> None:
    assert parse_minimize_command("Minimiza Steam", "Asistente Modular") == "steam"
    assert parse_minimize_command("Minimiza Steam y Discord", "Asistente Modular") == "steam y discord"
    assert parse_probable_minimize_command("Mini misa Steam", "Asistente Modular") == "steam"
    assert parse_probable_minimize_command("Min y misa Steam", "Asistente Modular") == "steam"
    assert parse_probable_minimize_command("Oye asistente modular, minimisa Steam", "Asistente Modular") == "steam"


def test_wake_phrase_distinguishes_conversation_from_gibberish() -> None:
    assert is_likely_conversation_after_wake("Oye Asistente Modular, ¿cómo estás?", "Asistente Modular") is True
    assert is_likely_conversation_after_wake("Oye Asistente Modular, si arrastim", "Asistente Modular") is False


def test_activation_phrase_is_rendered_from_current_assistant_name() -> None:
    store = ActivationSettingsStore(Path("unused-activation.json"))
    with patch.object(store, "get", return_value={
        "enabled": True,
        "wake_phrase": "Oye {assistant_name}",
        "wake_phrases": [
            "Oye {assistant_name}", "Ey {assistant_name}",
            "Oeh {assistant_name}", "{assistant_name}",
        ],
        "inactivity_seconds": 120,
        "show_on_wake": True,
        "hide_on_timeout": True,
    }):
        rendered = store.rendered("Luna")

    assert rendered["wake_phrase"] == "Oye Luna"
    assert rendered["wake_phrases"] == ["Oye Luna", "Ey Luna", "Oeh Luna", "Luna"]
    assert rendered["wake_phrase_template"] == "Oye {assistant_name}"


@pytest.mark.parametrize(
    "command",
    [
        "Sierra Steam",
        "Siera Steam",
        "Ciera Steam",
        "Si era Steam",
        "Si y era Steam",
            "Oye asistente modular, sierra Steam",
    ],
)
def test_probable_close_variants(command: str) -> None:
    assert parse_probable_close_command(command, "Asistente Modular") == "steam"


def test_successful_local_action_returns_hecho() -> None:
    entry = AccessEntry(
        id="calculator",
        name="Calculadora",
        kind="application",
        target=r"C:\Windows\System32\calc.exe",
        aliases=["calculadora"],
        arguments=[],
        working_directory=None,
        enabled=True,
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> AccessEntry:
            return entry

        def resolve(self, _name: str) -> AccessEntry:
            return entry

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        result = service.handle("abre la calculadora", "Asistente Modular")

    mocked_open.assert_called_once_with(entry)
    assert result.handled is True
    assert result.response == "¡Hecho!"


@pytest.mark.parametrize("command", ["Steam", "Oye Asistente Modular, Steam"])
def test_bare_application_name_requests_fragmented_open_confirmation(command: str) -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", ["steam"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, name: str) -> AccessEntry | None:
            return steam if name == "steam" else None

        def add_alias(self, _entry_id: str, _alias: str) -> AccessEntry:
            return steam

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    question = service.handle(command, "Asistente Modular")
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        confirmed = service.handle("sí", "Asistente Modular")

    assert question.response == "¿Abrir Steam?"
    assert question.speech_fragments == ["¿Abrir", "Steam"]
    mocked_open.assert_called_once_with(steam)
    assert confirmed.response == "¡Hecho!"


def test_two_accesses_are_resolved_before_both_are_opened() -> None:
    calculator = AccessEntry(
        "calculator", "Calculadora", "application", "calc.exe",
        ["calculadora"], [], None, True,
    )
    explorer = AccessEntry(
        "explorer", "Explorador de archivos", "application", "explorer.exe",
        ["explorador de archivos"], [], None, True,
    )

    class Catalog:
        entries = {"calculadora": calculator, "explorador de archivos": explorer}

        def resolve_exact(self, name: str) -> AccessEntry | None:
            return self.entries.get(name)

        def match(self, name: str) -> AccessMatch | None:
            entry = self.entries.get(name)
            return AccessMatch(entry, name, 1.0) if entry else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        result = service.handle(
            "abre la calculadora y el explorador de archivos", "Asistente Modular"
        )

    assert split_open_targets("calculadora y el explorador de archivos") == [
        "calculadora", "explorador de archivos"
    ]
    assert mocked_open.call_count == 2
    assert result.response == "¡Hecho!"


def test_unknown_access_uses_fixed_access_message() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    result = AccessToolService(Catalog()).handle("abre Photoshop", "Asistente Modular")  # type: ignore[arg-type]
    assert result.handled is True
    assert result.response == "No tengo acceso a esa aplicación."


def test_multiple_command_opens_nothing_when_one_access_is_missing() -> None:
    calculator = AccessEntry(
        "calculator", "Calculadora", "application", "calc.exe",
        ["calculadora"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, name: str) -> AccessMatch | None:
            return AccessMatch(calculator, name, 1.0) if name == "calculadora" else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        result = service.handle(
            "abre la calculadora y una aplicación desconocida", "Asistente Modular"
        )

    mocked_open.assert_not_called()
    assert result.response == "No tengo acceso a esa aplicación."


def test_model_confusion_is_normalized_to_fixed_repeat_message() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    class ConfusedProvider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            return GenerationResult(text="No entendí lo que dijiste, ¿puedes repetirlo?")

    orchestrator = Orchestrator(
        ConfusedProvider(),
        Path("missing-personality.txt"),
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(orchestrator.handle_text("frase sin sentido xkz"))
    assert reply.text == "Perdón, ¿puedes repetirlo?"


def test_model_access_refusal_is_normalized_to_single_fixed_message() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    class RefusingProvider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            return GenerationResult(
                text=(
                    "No puedo abrir aplicaciones ni archivos directamente en tu equipo. "
                    "¿Te gustaría que te ayude con algo más sobre ellos?"
                )
            )

    orchestrator = Orchestrator(
        RefusingProvider(),
        Path("missing-personality.txt"),
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(orchestrator.handle_text("Háblame sobre una aplicación"))

    assert reply.text == "No tengo acceso a esa aplicación."


def test_uncertain_multiple_command_waits_for_confirmation_and_learns_alias() -> None:
    notes = AccessEntry(
        "notes", "Bloc de notas", "application", "notepad.exe",
        ["bloc de notas"], [], None, True,
    )
    explorer = AccessEntry(
        "explorer", "Explorador de archivos", "application", "explorer.exe",
        ["explorador de archivos"], [], None, True,
    )

    class Catalog:
        learned: list[tuple[str, str]] = []

        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, name: str) -> AccessMatch | None:
            if name == "blog de notans":
                return AccessMatch(notes, name, 0.89)
            if name == "explorador de archivos":
                return AccessMatch(explorer, name, 1.0)
            return None

        def add_alias(self, entry_id: str, alias: str) -> AccessEntry:
            self.learned.append((entry_id, alias))
            return notes if entry_id == notes.id else explorer

    catalog = Catalog()
    service = AccessToolService(catalog)  # type: ignore[arg-type]
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        question = service.handle(
            "A ver el blog de Notans y el explorador de archivos", "Asistente Modular"
        )
        assert mocked_open.call_count == 0
        confirmed = service.handle("sí", "Asistente Modular")

    assert question.response == "¿Quieres abrir Bloc de notas y Explorador de archivos?"
    assert question.speech_fragments == [
        "¿Quieres abrir", "Bloc de notas", "y", "Explorador de archivos"
    ]
    assert mocked_open.call_count == 2
    assert confirmed.response == "¡Hecho!"
    assert catalog.learned == [("notes", "blog de notans")]


def test_formal_open_request_is_handled_locally() -> None:
    notes = AccessEntry(
        "notes", "Bloc de notas", "application", "notepad.exe",
        ["bloc de notas"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, name: str) -> AccessMatch | None:
            if name == "bloque de notas":
                return AccessMatch(notes, name, 0.91)
            return None

        def add_alias(self, _entry_id: str, _alias: str) -> AccessEntry:
            return notes

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch("asistente.tools.registry.open_entry") as mocked_open:
        question = service.handle("Abra el bloque de notas.", "Asistente Modular")
        confirmed = service.handle("sí", "Asistente Modular")

    assert question.response == "¿Quieres abrir Bloc de notas?"
    assert question.speech_fragments == ["¿Quieres abrir", "Bloc de notas"]
    mocked_open.assert_called_once_with(notes)
    assert confirmed.response == "¡Hecho!"


def test_formal_open_request_never_reaches_the_chat_provider() -> None:
    notes = AccessEntry(
        "notes", "Bloc de notas", "application", "notepad.exe",
        ["bloc de notas"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> AccessMatch:
            return AccessMatch(notes, "bloque de notas", 0.91)

    class Provider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            raise AssertionError("El comando local no debe enviarse a Gemini")

    orchestrator = Orchestrator(
        Provider(),
        Path("missing-personality.txt"),
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(orchestrator.handle_text("Abra el bloque de notas."))

    assert reply.text == "¿Quieres abrir Bloc de notas?"
    assert reply.speech_fragments == ["¿Quieres abrir", "Bloc de notas"]


def test_distorted_wake_command_never_reaches_the_chat_provider() -> None:
    notes = AccessEntry(
        "notes", "Bloc de notas", "application", "notepad.exe",
        ["bloc de notas"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, name: str) -> AccessMatch | None:
            if name == "bloque de notas":
                return AccessMatch(notes, name, 0.86)
            return None

    class Provider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            raise AssertionError("La recuperación de STT no debe llamar a Gemini")

    class Profile:
        def get(self) -> dict[str, str]:
            return {"name": "Asistente Modular"}

        def variables(self) -> dict[str, str]:
            return {"assistant_name": "Asistente Modular"}

    orchestrator = Orchestrator(
        Provider(),
        Path("missing-personality.txt"),
        assistant_profile=Profile(),  # type: ignore[arg-type]
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(
        orchestrator.handle_text("Oye, mi abril bloque de notas.")
    )

    assert reply.text == "¿Quieres abrir Bloc de notas?"
    assert reply.total_tokens == 0


def test_distorted_unknown_app_uses_fixed_message_without_tokens() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    result = service.handle("Oye, mi abril programa desconocido", "Asistente Modular")

    assert result.handled is True
    assert result.response == "No tengo acceso a esa aplicación."


def test_unsupported_local_action_never_reaches_the_chat_provider() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    class Provider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            raise AssertionError("Una orden de herramienta no debe llamar a Gemini")

    orchestrator = Orchestrator(
        Provider(),
        Path("missing-personality.txt"),
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(orchestrator.handle_text("Crea un recordatorio"))

    assert reply.text == "Esa función todavía no está disponible."
    assert reply.total_tokens == 0


def test_close_multiple_allowed_apps() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", ["steam"], [], None, True,
    )
    discord = AccessEntry(
        "discord", "Discord", "application", "discord.exe", ["discord"], [], None, True,
    )

    class Catalog:
        entries = {"steam": steam, "discord": discord}

        def resolve_exact(self, name: str) -> AccessEntry | None:
            return self.entries.get(name)

        def match(self, name: str) -> AccessMatch | None:
            entry = self.entries.get(name)
            return AccessMatch(entry, name, 1.0) if entry else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch(
        "asistente.tools.registry.close_entry",
        side_effect=lambda entry: CloseResult(entry.id, entry.name, True),
    ) as mocked_close:
        result = service.handle("Cierra Steam y Discord", "Asistente Modular")

    assert mocked_close.call_count == 2
    assert result.response == "¡Hecho!"


def test_distorted_close_uses_local_fragmented_confirmation() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", ["steam"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, name: str) -> AccessEntry | None:
            return steam if name == "steam" else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    question = service.handle("Sierra Steam", "Asistente Modular")
    with patch(
        "asistente.tools.registry.close_entry",
        return_value=CloseResult("steam", "Steam", True),
    ) as mocked_close:
        confirmed = service.handle("correcto", "Asistente Modular")

    assert question.response == "¿Quieres cerrar Steam?"
    assert question.speech_fragments == ["¿Quieres cerrar", "Steam"]
    assert question.client_action is None
    mocked_close.assert_called_once_with(steam)
    assert confirmed.response == "¡Hecho!"


def test_distorted_minimize_uses_local_fragmented_confirmation() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", ["steam"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, name: str) -> AccessEntry | None:
            return steam if name == "steam" else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    question = service.handle("Mini misa Steam", "Asistente Modular")
    with patch(
        "asistente.tools.registry.minimize_entry",
        return_value=MinimizeResult("steam", "Steam", True),
    ) as mocked_minimize:
        confirmed = service.handle("sí", "Asistente Modular")

    assert question.response == "¿Quieres minimizar Steam?"
    assert question.speech_fragments == ["¿Quieres minimizar", "Steam"]
    mocked_minimize.assert_called_once_with(steam)
    assert confirmed.response == "¡Hecho!"


def test_exact_minimize_executes_locally_without_confirmation() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", ["steam"], [], None, True,
    )

    class Catalog:
        def resolve_exact(self, name: str) -> AccessEntry | None:
            return steam if name == "steam" else None

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch(
        "asistente.tools.registry.minimize_entry",
        return_value=MinimizeResult("steam", "Steam", True),
    ) as mocked_minimize:
        reply = service.handle("Minimiza Steam", "Asistente Modular")

    mocked_minimize.assert_called_once_with(steam)
    assert reply.response == "¡Hecho!"
    assert reply.speech_fragments is None


def test_launcher_close_sends_wm_close_without_taskkill() -> None:
    launcher = AccessEntry(
        "steam", "Steam", "application", "steam.exe", [], [], None, True,
        close_policy="window",
    )
    with (
        patch("asistente.tools.applications.validate_target", return_value=Path("steam.exe")),
        patch("asistente.tools.applications._process_ids", return_value={123}) as process_ids,
        patch("asistente.tools.applications._send_window_command", return_value=True) as send_window,
        patch("asistente.tools.applications.subprocess.run") as taskkill,
    ):
        result = close_entry(launcher)

    process_ids.assert_called_once_with(("steam.exe", "steamwebhelper.exe"))
    send_window.assert_called_once_with({123}, 0x0010)
    taskkill.assert_not_called()
    assert result.closed is True


def test_registered_website_opens_in_configured_browser() -> None:
    youtube = WebsiteShortcut("youtube", "YouTube", "https://youtube.com", ["videos"], True)

    class Catalog:
        def get_browser(self) -> BrowserConfig:
            return BrowserConfig("Firefox", "firefox", r"C:\Firefox\firefox.exe", [])

        def browser_names(self) -> set[str]:
            return {"navegador", "firefox"}

        def resolve_website(self, name: str) -> WebsiteShortcut | None:
            return youtube if name in {"youtube", "videos"} else None

    service = WebAccessService(Catalog())  # type: ignore[arg-type]
    with patch("asistente.tools.websites.subprocess.Popen") as popen:
        handled = service.open_request("YouTube en Firefox")

    assert handled is True
    popen.assert_called_once()
    assert popen.call_args.args[0] == [r"C:\Firefox\firefox.exe", "https://youtube.com"]


def test_registered_website_command_is_handled_before_gemini() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            raise AssertionError("No debe buscar la página como aplicación")

    class WebTools:
        def open_request(self, requested: str) -> bool:
            assert requested == "youtube"
            return True

    service = AccessToolService(
        Catalog(), web_tools=WebTools()  # type: ignore[arg-type]
    )  # type: ignore[arg-type]
    reply = service.handle("Abre YouTube", "Asistente Modular")

    assert reply.handled is True
    assert reply.response == "¡Hecho!"


def test_bare_website_name_requests_local_confirmation() -> None:
    instagram = WebsiteShortcut(
        "instagram", "Instagram", "https://instagram.com", ["insta"], True
    )

    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

    class WebTools:
        def resolve_bare(self, name: str) -> WebsiteShortcut | None:
            return instagram if name in {"instagram", "insta"} else None

        def open_website(self, website: WebsiteShortcut) -> None:
            assert website == instagram

    web_tools = WebTools()
    service = AccessToolService(
        Catalog(), web_tools=web_tools  # type: ignore[arg-type]
    )  # type: ignore[arg-type]
    with patch("asistente.tools.registry.monotonic", side_effect=[100.0, 190.0]):
        question = service.handle("Instagram", "Asistente Modular")
        with patch.object(web_tools, "open_website", wraps=web_tools.open_website) as opened:
            confirmed = service.handle("sí", "Asistente Modular")

    assert question.response == "¿Abrir Instagram?"
    assert question.speech_fragments == ["¿Abrir", "Instagram"]
    opened.assert_called_once_with(instagram)
    assert confirmed.response == "¡Hecho!"


def test_confirmation_without_pending_action_is_handled_locally() -> None:
    class Catalog:
        pass

    service = AccessToolService(Catalog())  # type: ignore[arg-type]

    result = service.handle("correcto.", "Asistente Modular")

    assert result.handled is True
    assert result.response == "Perdón, ¿puedes repetirlo?"


def test_unidentified_text_after_wake_uses_cached_repeat_response_without_tokens() -> None:
    class Catalog:
        def resolve_exact(self, _name: str) -> None:
            return None

        def match(self, _name: str) -> None:
            return None

    class Provider(ChatProvider):
        async def generate(self, _messages: list[ChatMessage]) -> GenerationResult:
            raise AssertionError("El texto no identificado no debe llegar a Gemini")

    class Profile:
        def get(self) -> dict[str, str]:
            return {"name": "Asistente Modular"}

        def variables(self) -> dict[str, str]:
            return {"assistant_name": "Asistente Modular"}

    orchestrator = Orchestrator(
        Provider(),
        Path("missing-personality.txt"),
        assistant_profile=Profile(),  # type: ignore[arg-type]
        access_tools=AccessToolService(Catalog()),  # type: ignore[arg-type]
    )
    reply = asyncio.run(orchestrator.handle_text("Oye Asistente Modular, si arrastim"))

    assert reply.text == "Perdón, ¿puedes repetirlo?"
    assert reply.total_tokens == 0


def test_close_all_only_uses_allowed_applications() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", "steam.exe", [], [], None, True,
    )
    manual = AccessEntry(
        "manual", "Manual", "file", "manual.txt", [], [], None, True,
    )

    class Catalog:
        def list(self) -> list[AccessEntry]:
            return [steam, manual]

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    with patch(
        "asistente.tools.registry.close_entry",
        return_value=CloseResult("steam", "Steam", True),
    ) as mocked_close:
        result = service.handle("Cierra todo", "Asistente Modular")

    mocked_close.assert_called_once_with(steam)
    assert result.response == "¡Hecho!"


def test_close_uses_real_calculator_process_without_process_tree() -> None:
    calculator = AccessEntry(
        "calculator", "Calculadora", "application",
        r"C:\Windows\System32\calc.exe", [], [], None, True,
    )

    with patch("asistente.tools.applications.subprocess.run") as mocked_run:
        mocked_run.return_value.returncode = 0
        result = close_entry(calculator)

    command = mocked_run.call_args.args[0]
    assert command[-2:] == ["/IM", "CalculatorApp.exe"]
    assert "/T" not in command
    assert result.closed is True


def test_close_steam_does_not_try_to_terminate_its_service_tree() -> None:
    steam = AccessEntry(
        "steam", "Steam", "application", r"C:\Games\Steam\steam.exe",
        [], [], None, True,
    )

    with (
        patch(
            "asistente.tools.applications.validate_target",
            return_value=Path(r"C:\Games\Steam\steam.exe"),
        ),
        patch("asistente.tools.applications.subprocess.run") as mocked_run,
    ):
        mocked_run.return_value.returncode = 0
        result = close_entry(steam)

    command = mocked_run.call_args.args[0]
    assert command[-2:] == ["/IM", "steam.exe"]
    assert "/T" not in command
    assert result.closed is True


def test_shutdown_requires_confirmation_and_quit_is_a_client_action() -> None:
    class Catalog:
        pass

    service = AccessToolService(Catalog())  # type: ignore[arg-type]
    question = service.handle("Apaga la PC", "Asistente Modular")
    confirmed = service.handle("sí", "Asistente Modular")
    quit_result = service.handle("Apágate", "Asistente Modular")

    assert question.response == "¿Deseas apagar la PC?"
    assert question.speech_fragments == ["¿Deseas apagar", "la PC"]
    assert question.client_action is None
    assert confirmed.response == "¡Hecho!"
    assert confirmed.client_action == "shutdown_pc"
    assert quit_result.client_action == "quit_assistant"
