"""Configuración común de síntesis de voz."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TTSSettings:
    model_path: Path
    config_path: Path
    voice_path: Path
    language: str = "e"
    speed: float = 1.0
