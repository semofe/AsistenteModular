import asyncio
from pathlib import Path

from asistente.core.orchestrator import Orchestrator
from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult


class FakeProvider(ChatProvider):
    def __init__(self) -> None:
        self.received: list[ChatMessage] = []

    async def generate(self, messages: list[ChatMessage]) -> GenerationResult:
        self.received = messages
        return GenerationResult(
            text="Respuesta de prueba",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
        )


def test_orchestrator_preserves_a_bounded_history(tmp_path: Path) -> None:
    personality = tmp_path / "personality.txt"
    personality.write_text("Eres Asistente Modular.", encoding="utf-8")
    provider = FakeProvider()
    orchestrator = Orchestrator(provider, personality, max_history_messages=2)

    first = asyncio.run(orchestrator.handle_text("Hola"))
    second = asyncio.run(orchestrator.handle_text("¿Cómo estás?"))

    assert first.text == "Respuesta de prueba"
    assert first.total_tokens == 14
    assert second.session_tokens == 28
    assert provider.received[0].content == "Eres Asistente Modular."
    assert [message.content for message in orchestrator.history] == [
        "¿Cómo estás?",
        "Respuesta de prueba",
    ]
