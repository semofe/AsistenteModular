"""Rutas persistentes de la aplicación en Windows."""

from __future__ import annotations

import os
from pathlib import Path


def data_directory() -> Path:
    if configured := os.environ.get("ASISTENTE_DATA_DIR"):
        return Path(configured).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Asistente Modular"
    return Path.home() / "AppData" / "Local" / "Asistente Modular"


def ensure_data_directories(root: Path | None = None) -> dict[str, Path]:
    base = root or data_directory()
    paths = {
        "root": base,
        "config": base / "config",
        "data": base / "data",
        "cache": base / "cache",
        "memories": base / "memories",
        "logs": base / "logs",
        "models": base / "models",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
