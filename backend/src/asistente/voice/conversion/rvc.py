"""Configuración de conversión RVC."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RVCSettings:
    enabled: bool
    python_path: Path
    project_path: Path
    model_path: Path
    index_path: Path
    pitch: int = 8
    index_rate: float = 0.75
