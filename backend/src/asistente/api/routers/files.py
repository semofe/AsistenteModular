"""Files HTTP endpoints."""
from __future__ import annotations
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException
from asistente.config.settings import FileAccessPreferenceStore
from asistente.tools.files import FileAccessService
from asistente.api.http_schemas import FileAccessPreferencesRequest
from asistente.api.http_schemas import READABLE_FILE_EXTENSIONS


def create_files_router(
    file_access_preferences: FileAccessPreferenceStore | None,
    file_access: FileAccessService | None
) -> APIRouter:
    router = APIRouter()

    @router.get("/files/preferences")
    async def file_access_configuration() -> dict[str, object]:
        if file_access_preferences is None:
            raise HTTPException(status_code=503, detail="La configuración de archivos no está disponible.")
        return file_access_preferences.get()

    @router.put("/files/preferences")
    async def save_file_access_configuration(
        request: FileAccessPreferencesRequest,
    ) -> dict[str, object]:
        if file_access_preferences is None:
            raise HTTPException(status_code=503, detail="La configuración de archivos no está disponible.")
        try:
            folders: list[str] = []
            for folder in request.folders:
                path = Path(folder).expanduser().resolve(strict=True)
                if not path.is_dir():
                    raise ValueError(f"La ruta no es una carpeta: {folder}")
                folders.append(str(path))
            unsupported = {
                extension.strip().lower().lstrip(".")
                for extension in request.extensions
                if extension.strip().lower().lstrip(".") not in READABLE_FILE_EXTENSIONS
            }
            if unsupported:
                raise ValueError(
                    "Tipos disponibles actualmente: "
                    + ", ".join(sorted(READABLE_FILE_EXTENSIONS))
                    + "."
                )
            saved = file_access_preferences.save({
                "folders": folders,
                "extensions": request.extensions,
            })
            if file_access is not None:
                await asyncio.to_thread(file_access.refresh_index)
            return saved
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/files/index")
    async def file_index() -> dict[str, object]:
        if file_access is None:
            raise HTTPException(status_code=503, detail="El índice de archivos no está disponible.")
        return {"files": file_access.index()}

    @router.post("/files/index/refresh")
    async def refresh_file_index() -> dict[str, object]:
        if file_access is None:
            raise HTTPException(status_code=503, detail="El índice de archivos no está disponible.")
        files = await asyncio.to_thread(file_access.refresh_index)
        return {"files": files}

    return router
