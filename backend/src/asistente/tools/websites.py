"""Apertura segura de navegador y accesos web registrados."""

from __future__ import annotations

import os
import subprocess
import webbrowser

from asistente.access.catalog import normalize_name
from asistente.access.web_catalog import WebAccessCatalog, WebsiteShortcut
from asistente.automation.local_parser import split_open_targets


class WebAccessService:
    def __init__(self, catalog: WebAccessCatalog) -> None:
        self.catalog = catalog

    def _open(self, url: str | None = None) -> None:
        browser = self.catalog.get_browser()
        if browser is not None:
            command = [browser.executable]
            if url:
                command.append(url)
            subprocess.Popen(command, shell=False, close_fds=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            return
        if url:
            if os.name == "nt":
                os.startfile(url)
            else:
                webbrowser.open_new_tab(url)
        else:
            webbrowser.open_new("about:blank")

    def resolve_bare(self, spoken_name: str) -> WebsiteShortcut | None:
        return self.catalog.resolve_website(spoken_name)

    def can_open_request(self, requested: str) -> bool:
        normalized = normalize_name(requested)
        browser_names = self.catalog.browser_names()
        if normalized in browser_names:
            return True
        for browser_name in sorted(browser_names, key=len, reverse=True):
            suffix = f" en {browser_name}"
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
                break
        targets = split_open_targets(normalized)
        return bool(targets) and all(
            self.catalog.resolve_website(target) is not None for target in targets
        )

    def open_website(self, website: WebsiteShortcut) -> None:
        self._open(website.url)

    def open_request(self, requested: str) -> bool:
        normalized = normalize_name(requested)
        browser_names = self.catalog.browser_names()
        if normalized in browser_names:
            self._open()
            return True

        for browser_name in sorted(browser_names, key=len, reverse=True):
            suffix = f" en {browser_name}"
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
                break
        targets = split_open_targets(normalized)
        sites: list[WebsiteShortcut] = []
        for target in targets:
            site = self.catalog.resolve_website(target)
            if site is None:
                return False
            sites.append(site)
        if not sites:
            return False
        for site in sites:
            self.open_website(site)
        return True

    def open_search(self, platform: str, query: str) -> bool:
        import urllib.parse
        encoded_query = urllib.parse.quote(query.strip())
        if platform == "youtube":
            try:
                import httpx
                import re
                response = httpx.get(f"https://www.youtube.com/results?search_query={encoded_query}", timeout=5.0)
                match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
                if match:
                    video_id = match.group(1)
                    url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
                else:
                    url = f"https://www.youtube.com/results?search_query={encoded_query}"
            except Exception:
                url = f"https://www.youtube.com/results?search_query={encoded_query}"
            self._open(url)
            return True
        elif platform == "spotify":
            url = f"https://open.spotify.com/search/{encoded_query}"
            self._open(url)
            return True
        elif platform == "google":
            url = f"https://www.google.com/search?q={encoded_query}"
            self._open(url)
            return True
        return False



def parse_platform_search(text: str, assistant_name: str = "") -> tuple[str, str] | None:
    import re
    clean = text.strip().rstrip(".!? ")
    if assistant_name:
        clean = re.sub(rf"^(?:(?:oye|ey|oeh)\s+)?{re.escape(assistant_name)}[, ]+", "", clean, flags=re.I)
    clean = re.sub(r"^(?:por favor\s+)?(?:me\s+)?puedes\s+", "", clean, flags=re.I)
    clean = re.sub(r"\s+por favor$", "", clean, flags=re.I)
    explicit = re.fullmatch(r"(?:busca|buscar|búscame|buscame|buscarme|reproduce|reproducir|pon|poner|ponme|ponerme|quiero escuchar|quiero ver)\s+(.+?)\s+en\s+(youtube|spotify|google)", clean, re.I)
    if explicit:
        return explicit.group(2).lower(), explicit.group(1)
    default = re.fullmatch(r"(?:pon|reproduce|ponme|reprodúceme|reproduceme)\s+(.+)", clean, re.I)
    return ("youtube", default.group(1)) if default else None
