"""Reconoce comandos locales explícitos sin usar el modelo de lenguaje."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _normalized(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _plain(text)).split())


def parse_open_command(text: str, assistant_name: str) -> str | None:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    match = re.fullmatch(
        rf"{wake}(?:por favor\s+)?(?:"
        rf"abre|abra|abrir|abreme|abrame|inicia|iniciar|ejecuta|ejecutar|lanza|ahora|abro|"
        rf"a\s+ver|haber|me\s+abres|puedes\s+abrir(?:me)?|"
        rf"me\s+puedes\s+abrir|podrias\s+abrir(?:me)?|quiero\s+abrir|"
        rf"quiero\s+que\s+abras|necesito\s+abrir|ve\s+abriendo|arranca|arrancar"
        rf")\s+(?:(?:el|la|los|las|mi|mis)\s+)?(.+?)(?:\s+por favor)?",
        normalized,
    )
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def parse_close_command(text: str, assistant_name: str) -> str | None:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    match = re.fullmatch(
        rf"{wake}(?:por favor\s+)?(?:cierra|cierras|cerrar|cierrame)\s+"
        rf"(?:el|la|los|las|mi|mis)?\s*(.+?)(?:\s+por favor)?",
        normalized,
    )
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def parse_probable_close_command(text: str, assistant_name: str) -> str | None:
    """Recupera variantes frecuentes con las que STT transcribe «cierra»."""
    tokens = _normalized(text).split()
    assistant_tokens = _normalized(assistant_name).split()
    position = 0
    wake_detected = False
    if tokens[:1] == ["oye"] and assistant_tokens:
        spoken_name = " ".join(tokens[1:1 + len(assistant_tokens)])
        expected_name = " ".join(assistant_tokens)
        if SequenceMatcher(None, spoken_name, expected_name).ratio() < 0.67:
            return None
        position = 1 + len(assistant_tokens)
        wake_detected = True
    if tokens[position:position + 2] == ["por", "favor"]:
        position += 2

    variants = (
        ("si", "y", "era"),
        ("si", "era"),
        ("ci", "era"),
        ("sierra",),
        ("siera",),
        ("ciera",),
        ("cierras",),
        ("cerra",),
        ("serra",),
        ("cerrar",),
        ("serrar",),
        ("c", "rra"),
        ("serra",),
    )
    consumed = 0
    for variant in variants:
        if tuple(tokens[position:position + len(variant)]) == variant:
            consumed = len(variant)
            break
    if consumed == 0 and wake_detected and position < len(tokens):
        candidate = tokens[position]
        if SequenceMatcher(None, candidate, "cierra").ratio() >= 0.80:
            consumed = 1
    if consumed == 0:
        return None

    target_tokens = tokens[position + consumed:]
    if target_tokens[:1] and target_tokens[0] in {"el", "la", "los", "las", "mi", "mis"}:
        target_tokens = target_tokens[1:]
    if target_tokens[-2:] == ["por", "favor"]:
        target_tokens = target_tokens[:-2]
    target = " ".join(target_tokens).strip()
    return target or None


def parse_minimize_command(text: str, assistant_name: str) -> str | None:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    match = re.fullmatch(
        rf"{wake}(?:por favor\s+)?(?:minimiza|minimizar|minimizame)\s+"
        rf"(?:el|la|los|las|mi|mis)?\s*(.+?)(?:\s+por favor)?",
        normalized,
    )
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def parse_probable_minimize_command(text: str, assistant_name: str) -> str | None:
    tokens = _normalized(text).split()
    assistant_tokens = _normalized(assistant_name).split()
    position = 0
    wake_detected = False
    if tokens[:1] == ["oye"] and assistant_tokens:
        spoken_name = " ".join(tokens[1:1 + len(assistant_tokens)])
        expected_name = " ".join(assistant_tokens)
        if SequenceMatcher(None, spoken_name, expected_name).ratio() < 0.67:
            return None
        position = 1 + len(assistant_tokens)
        wake_detected = True
    if tokens[position:position + 2] == ["por", "favor"]:
        position += 2
    variants = (
        ("min", "y", "misa"), ("mini", "misa"), ("min", "misa"),
        ("minimisa",), ("minimiza",), ("minimisar",),
    )
    consumed = 0
    for variant in variants:
        if tuple(tokens[position:position + len(variant)]) == variant:
            consumed = len(variant)
            break
    if consumed == 0 and wake_detected and position < len(tokens):
        candidate = tokens[position]
        if SequenceMatcher(None, candidate, "minimiza").ratio() >= 0.75:
            consumed = 1
    if consumed == 0:
        return None
    target_tokens = tokens[position + consumed:]
    if target_tokens[:1] and target_tokens[0] in {"el", "la", "los", "las", "mi", "mis"}:
        target_tokens = target_tokens[1:]
    target = " ".join(target_tokens).strip()
    return target or None


def wake_phrase_remainder(text: str, assistant_name: str) -> str | None:
    tokens = _normalized(text).split()
    assistant_tokens = _normalized(assistant_name).split()
    if tokens[:1] != ["oye"] or not assistant_tokens:
        return None
    spoken_name = " ".join(tokens[1:1 + len(assistant_tokens)])
    expected_name = " ".join(assistant_tokens)
    if SequenceMatcher(None, spoken_name, expected_name).ratio() < 0.67:
        return None
    return " ".join(tokens[1 + len(assistant_tokens):]).strip()


def is_likely_conversation_after_wake(text: str, assistant_name: str) -> bool:
    remainder = wake_phrase_remainder(text, assistant_name)
    if remainder is None:
        return True
    tokens = remainder.split()
    if not tokens:
        return False
    conversational_starts = {
        "hola", "buenas", "dime", "explica", "explicame", "cuenta", "cuentame",
        "ayudame", "puedes", "podrias", "quiero", "necesito", "hablemos",
        "que", "como", "cuando", "donde", "porque", "por", "quien", "quienes",
        "cual", "cuales", "cuanto", "cuanta", "cuantos", "cuantas", "es", "son",
        "estoy", "tengo", "me", "mi", "hoy", "ayer", "sabes", "conoces",
        "recomienda", "recomiendame", "explicame", "opinas", "crees",
    }
    return tokens[0] in conversational_starts


def is_quit_assistant_command(text: str, assistant_name: str) -> bool:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    suffix = rf"(?:\s+{re.escape(name)})?" if name else ""
    return bool(re.fullmatch(
        rf"{wake}(?:por favor\s+)?(?:apagate|cierrate){suffix}(?:\s+por favor)?",
        normalized,
    ))


def is_hide_assistant_command(text: str, assistant_name: str) -> bool:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    optional_name = rf"(?:\s+{re.escape(name)})?" if name else ""
    required_name = rf"\s+{re.escape(name)}" if name else r"(?!)"
    patterns = (
        rf"eso\s+es\s+todo{optional_name}",
        rf"esto\s+es\s+todo{optional_name}",
        rf"es\s+todo{optional_name}",
        rf"gracias{required_name}",
        rf"minimizate{optional_name}",
    )
    return any(
        re.fullmatch(rf"{wake}(?:por favor\s+)?{pattern}(?:\s+por favor)?", normalized)
        for pattern in patterns
    )


def is_shutdown_command(text: str, assistant_name: str) -> bool:
    normalized = _normalized(text)
    name = _normalized(assistant_name)
    wake = rf"(?:oye\s+{re.escape(name)}\s+)?" if name else ""
    return bool(
        re.fullmatch(
            rf"{wake}(?:por favor\s+)?(?:apaga|apagar)\s+(?:la|el)?\s*"
            rf"(?:pc|computadora|equipo)(?:\s+por favor)?",
            normalized,
        )
    )


def parse_probable_open_command(text: str, assistant_name: str) -> str | None:
    """Recupera errores breves de STT sin convertir conversación libre en comandos."""
    tokens = _normalized(text).split()
    assistant_tokens = _normalized(assistant_name).split()
    position = 0
    wake_detected = False
    if tokens[:1] == ["oye"] and assistant_tokens:
        spoken_name = " ".join(tokens[1:1 + len(assistant_tokens)])
        expected_name = " ".join(assistant_tokens)
        if SequenceMatcher(None, spoken_name, expected_name).ratio() < 0.67:
            return None
        position = 1 + len(assistant_tokens)
        wake_detected = True
    if tokens[position:position + 2] == ["por", "favor"]:
        position += 2

    patterns = (
        "abre", "abrir", "abreme", "abrame", "inicia", "iniciar",
        "ejecuta", "ejecutar", "lanza", "arranca", "quiero abrir",
        "necesito abrir", "puedes abrir", "podrias abrir",
    )
    best_score = 0.0
    best_length = 0
    for pattern in patterns:
        length = len(pattern.split())
        candidate = " ".join(tokens[position:position + length])
        if not candidate:
            continue
        score = SequenceMatcher(None, candidate, pattern).ratio()
        if score > best_score:
            best_score = score
            best_length = length
    required_score = 0.72 if wake_detected else 0.84
    if best_score < required_score:
        return None

    target_tokens = tokens[position + best_length:]
    if target_tokens[:1] and target_tokens[0] in {"el", "la", "los", "las", "mi", "mis"}:
        target_tokens = target_tokens[1:]
    if target_tokens[-2:] == ["por", "favor"]:
        target_tokens = target_tokens[:-2]
    target = " ".join(target_tokens).strip()
    return target or None


def is_probable_local_action(text: str, assistant_name: str) -> bool:
    """Detecta peticiones de herramientas para impedir que caigan en el chat."""
    tokens = _normalized(text).split()
    assistant_tokens = _normalized(assistant_name).split()
    position = 0
    wake_detected = False
    if tokens[:1] == ["oye"] and assistant_tokens:
        spoken_name = " ".join(tokens[1:1 + len(assistant_tokens)])
        expected_name = " ".join(assistant_tokens)
        if SequenceMatcher(None, spoken_name, expected_name).ratio() < 0.67:
            return False
        position = 1 + len(assistant_tokens)
        wake_detected = True
    if tokens[position:position + 2] == ["por", "favor"]:
        position += 2
    polite_prefixes = (
        ["puedes"], ["podrias"], ["me", "puedes"], ["quiero", "que"],
        ["necesito", "que"],
    )
    for prefix in polite_prefixes:
        if tokens[position:position + len(prefix)] == prefix:
            position += len(prefix)
            break
    if position >= len(tokens):
        return False

    action_verbs = {
        "activa", "activar", "agrega", "agregar", "agenda", "agendar",
        "apaga", "apagar", "busca", "buscar", "cierra", "cerrar",
        "configura", "configurar", "copia", "copiar", "crea", "crear",
        "desactiva", "desactivar", "edita", "editar", "elimina", "eliminar",
        "escribe", "escribir", "guarda", "guardar", "lee", "leer",
        "maximiza", "maximizar", "minimiza", "minimizar", "modifica", "modificar",
        "mueve", "mover", "programa", "programar", "recuerda", "recordar",
        "recuerdame", "reinicia", "reiniciar", "renombra", "renombrar",
        "toma", "tomar",
    }
    candidate = tokens[position]
    if candidate in action_verbs:
        return True
    if not wake_detected:
        return False
    return max(
        SequenceMatcher(None, candidate, verb).ratio() for verb in action_verbs
    ) >= 0.84


def is_explicit_open_request(text: str) -> bool:
    normalized = _normalized(text)
    return bool(
        re.search(
            r"(?:^|\s)(?:abre|abra|abrir|abreme|abrame|inicia|iniciar|ejecuta|ejecutar|lanza|"
            r"me\s+abres|puedes\s+abrir(?:me)?|me\s+puedes\s+abrir|"
            r"podrias\s+abrir(?:me)?|quiero\s+abrir|quiero\s+que\s+abras|"
            r"necesito\s+abrir|ve\s+abriendo|arranca|arrancar)(?:\s|$)",
            normalized,
        )
    )


def has_uncertain_open_cue(text: str) -> bool:
    normalized = _normalized(text)
    return bool(re.search(r"(?:^|\s)(?:a\s+ver|haber)\s+", normalized))


def split_open_targets(target: str) -> list[str]:
    parts = re.split(
        r"\s+(?:y|e)\s+(?:(?:el|la|los|las|mi|mis)\s+)?|\s*,\s*",
        target,
    )
    return [part.strip() for part in parts if part.strip()]
