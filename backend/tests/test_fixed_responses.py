import asyncio
from pathlib import Path

import pytest

from asistente.core.fixed_responses import FixedResponseMatcher, normalize_text
from asistente.core.orchestrator import Orchestrator
from asistente.config.assistant_profile import AssistantProfileStore


RULES = Path(__file__).resolve().parents[2] / "config" / "defaults" / "fixed_responses.json"
PROFILE = Path(__file__).resolve().parents[2] / "config" / "defaults" / "assistant.json"


def matcher() -> FixedResponseMatcher:
    profile = AssistantProfileStore(PROFILE)
    return FixedResponseMatcher(RULES, profile.variables)


@pytest.mark.parametrize(
    "question",
    [
        "¿Cómo te llamas?",
        "Cuál es tu nombre",
        "Dime tu nombre, por favor",
        "Oye Asistente Modular, ¿quién eres?",
        "¿Me puedes decir cómo te llamas?",
    ],
)
def test_name_variations_return_the_same_response(question: str) -> None:
    match = matcher().match(question)
    assert match is not None
    assert match.response == "Me llamo Asistente Modular."


def test_normalization_removes_accents_and_punctuation() -> None:
    assert normalize_text("¿CÓMO te llamas?") == "como te llamas"


def test_fixed_response_does_not_require_cloud_provider() -> None:
    orchestrator = Orchestrator(
        provider=None,
        personality_path=Path("missing.txt"),
        fixed_responses_path=RULES,
        assistant_profile=AssistantProfileStore(PROFILE),
    )
    reply = asyncio.run(orchestrator.handle_text("¿Cuál es tu nombre?"))
    assert reply.text == "Me llamo Asistente Modular."
    assert reply.total_tokens == 0
