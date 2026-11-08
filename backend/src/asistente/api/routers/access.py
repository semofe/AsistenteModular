"""Access HTTP endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from asistente.access.catalog import AccessCatalog
from asistente.access.web_catalog import WebAccessCatalog
from asistente.access.path_policy import PathPolicyError
from asistente.access.discovery_windows import sync_discovered_apps
from asistente.tools.registry import AccessToolService
from asistente.api.http_schemas import AccessEntryRequest, BrowserConfigRequest, SpokenNameRequest, WebsiteRequest


def create_access_router(
    access_catalog: AccessCatalog | None,
    access_tools: AccessToolService | None,
    web_catalog: WebAccessCatalog | None
) -> APIRouter:
    router = APIRouter()

    @router.post("/access/sync")
    async def sync_apps() -> dict[str, int]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="Catálogo no disponible.")
        added = await asyncio.to_thread(sync_discovered_apps, access_catalog)
        return {"added": added}

    @router.get("/access")
    async def list_access_entries() -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        entries = await asyncio.to_thread(access_catalog.list)
        return {"entries": [entry.to_dict() for entry in entries]}

    @router.post("/access")
    async def add_access_entry(request: AccessEntryRequest) -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        try:
            entry = await asyncio.to_thread(
                access_catalog.add,
                request.name,
                request.kind,
                request.target,
                request.aliases,
                spoken_name=request.spoken_name,
                close_policy=request.close_policy,
            )
        except (ValueError, PathPolicyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.put("/access/{entry_id}/spoken-name")
    async def save_access_spoken_name(
        entry_id: str, request: SpokenNameRequest
    ) -> dict[str, object]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        try:
            entry = await asyncio.to_thread(
                access_catalog.update_spoken_name, entry_id, request.spoken_name
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return entry.to_dict()

    @router.delete("/access/{entry_id}")
    async def delete_access_entry(entry_id: str) -> dict[str, bool]:
        if access_catalog is None:
            raise HTTPException(status_code=503, detail="El catálogo no está disponible.")
        deleted = await asyncio.to_thread(access_catalog.delete, entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Acceso no encontrado.")
        return {"deleted": True}

    @router.post("/access/{entry_id}/open")
    async def open_access_entry(entry_id: str) -> dict[str, object]:
        if access_tools is None:
            raise HTTPException(status_code=503, detail="Las herramientas no están disponibles.")
        try:
            result = await asyncio.to_thread(access_tools.open, entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "opened": result.opened,
            "id": result.entry_id,
            "name": result.name,
            "kind": result.kind,
            "message": access_tools.success_message(),
        }

    @router.get("/browser")
    async def browser_configuration() -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        browser = await asyncio.to_thread(web_catalog.get_browser)
        websites = await asyncio.to_thread(web_catalog.list_websites)
        return {
            "browser": browser.to_dict() if browser else None,
            "websites": [website.to_dict() for website in websites],
        }

    @router.put("/browser")
    async def save_browser_configuration(request: BrowserConfigRequest) -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        try:
            browser = await asyncio.to_thread(
                web_catalog.save_browser, request.name, request.activation_word,
                request.executable, request.aliases,
            )
        except (ValueError, PathPolicyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return browser.to_dict()

    @router.delete("/browser")
    async def clear_browser_configuration() -> dict[str, bool]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        await asyncio.to_thread(web_catalog.clear_browser)
        return {"deleted": True}

    @router.post("/websites")
    async def add_website(request: WebsiteRequest) -> dict[str, object]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        try:
            website = await asyncio.to_thread(
                web_catalog.add_website, request.name, request.url, request.aliases
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return website.to_dict()

    @router.delete("/websites/{website_id}")
    async def delete_website(website_id: str) -> dict[str, bool]:
        if web_catalog is None:
            raise HTTPException(status_code=503, detail="La configuración web no está disponible.")
        deleted = await asyncio.to_thread(web_catalog.delete_website, website_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Acceso web no encontrado.")
        return {"deleted": True}

    return router
