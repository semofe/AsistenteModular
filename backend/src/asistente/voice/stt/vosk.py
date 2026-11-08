"""Configuración del reconocedor local Vosk para comandos y activación."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VoskSettings:
    model_path: Path
    sample_rate: int = 16000
    minimum_confidence: float = 0.55

