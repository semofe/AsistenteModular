"""Valida destinos antes de incorporarlos a la lista permitida."""

from __future__ import annotations

from pathlib import Path


class PathPolicyError(ValueError):
    pass


APPLICATION_EXTENSIONS = {".exe", ".lnk"}


def validate_target(kind: str, target: str) -> Path:
    if kind not in {"application", "file", "folder"}:
        raise PathPolicyError("Tipo de acceso desconocido.")
    if not target.strip():
        raise PathPolicyError("Debes elegir una ruta.")
    path = Path(target).expanduser()
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise PathPolicyError("La ruta indicada no existe.") from exc
    if kind == "folder" and not path.is_dir():
        raise PathPolicyError("La ruta no corresponde a una carpeta.")
    if kind in {"file", "application"} and not path.is_file():
        raise PathPolicyError("La ruta no corresponde a un archivo.")
    if kind == "application" and path.suffix.casefold() not in APPLICATION_EXTENSIONS:
        raise PathPolicyError("Solo se permiten aplicaciones .exe o accesos directos .lnk.")
    return path
