from asistente.api.routes import _starts_with_wake, _vosk_command_grammar


def test_active_vosk_grammar_contains_commands_confirmations_and_wake_forms() -> None:
    grammar = _vosk_command_grammar(
        "Asistente Modular", ["Oye Asistente Modular", "Ey Asistente Modular", "Asistente Modular"], ["Instagram", "Steam"], False
    )

    assert "instagram" in grammar
    assert "abre instagram" in grammar
    assert "sierra instagram" in grammar
    assert "oye asistente abre instagram" in grammar
    assert "correcto" in grammar
    assert grammar[-1] == "[unk]"


def test_dormant_vosk_grammar_requires_a_wake_phrase() -> None:
    grammar = _vosk_command_grammar(
        "Asistente Modular", ["Oye Asistente Modular", "Ey Asistente Modular", "Asistente Modular"], ["Instagram"], True
    )

    assert "oye asistente abre instagram" in grammar
    assert "abre instagram" not in grammar
    assert _starts_with_wake("Oye Asistente Modular abre Instagram", ["Oye Asistente Modular", "Ey Asistente Modular"])
    assert not _starts_with_wake("Abre Instagram", ["Oye Asistente Modular", "Ey Asistente Modular"])
