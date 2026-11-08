"""Configuración del adaptador faster-whisper ejecutado por el trabajador."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FasterWhisperSettings:
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "es"
    beam_size: int = 5
    cpu_threads: int = 6
    download_root: Path | None = None
