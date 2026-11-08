"""Wake phrase and Vosk vocabulary helpers."""
from __future__ import annotations
from asistente.access.catalog import normalize_name


def _vosk_command_grammar(
    assistant_name: str,
    wake_phrases: list[str],
    catalog_phrases: list[str],
    dormant: bool,
) -> list[str]:
    targets = list(dict.fromkeys(
        normalized
        for phrase in catalog_phrases
        if (normalized := normalize_name(phrase))
    ))
    action_prefixes = (
        "abre", "abrir", "inicia", "ejecuta", "lanza",
        "cierra", "cierras", "cerrar", "sierra", "siera", "ciera",
        "si era", "minimiza", "minimizar",
    )
    commands = [*targets]
    commands.extend(
        f"{action} {target}" for target in targets for action in action_prefixes
    )
    commands.extend([
        "cierra todo", "cierra todas las aplicaciones", "apaga la pc",
        "eso es todo", "esto es todo", "minimizate", "apagate", "cierrate",
    ])
    confirmations = [
        "si", "correcto", "confirmo", "hazlo", "adelante", "si hazlo",
        "no", "cancelar", "cancela", "dejalo", "no gracias",
    ]
    wakes = list(dict.fromkeys(
        normalized
        for phrase in [*wake_phrases, assistant_name]
        if (normalized := normalize_name(phrase))
    ))
    wake_commands = [f"{wake} {command}" for wake in wakes for command in commands]
    phrases = (
        [*wakes, *wake_commands]
        if dormant
        else [*commands, *confirmations, *wakes, *wake_commands]
    )
    return [*dict.fromkeys(phrases), "[unk]"]


def _starts_with_wake(text: str, wake_phrases: list[str]) -> bool:
    normalized = normalize_name(text)
    return any(
        normalized == wake or normalized.startswith(f"{wake} ")
        for phrase in wake_phrases
        if (wake := normalize_name(phrase))
    )
