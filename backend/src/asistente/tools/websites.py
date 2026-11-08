"""Apertura segura de navegador y accesos web registrados."""

from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx

from asistente.access.catalog import normalize_name
from asistente.access.web_catalog import WebAccessCatalog, WebsiteShortcut
from asistente.automation.local_parser import split_open_targets


_DEFAULT_WEBSITES = (
    WebsiteShortcut("linkedin", "LinkedIn", "https://www.linkedin.com/", ["linked in"], True),
    WebsiteShortcut("instagram", "Instagram", "https://www.instagram.com/", [], True),
    WebsiteShortcut(
        "mercado-libre", "Mercado Libre", "https://www.mercadolibre.com.pe/",
        ["mercadolibre", "mercado libre peru"], True,
    ),
    WebsiteShortcut("youtube", "YouTube", "https://www.youtube.com/", ["you tube"], True),
    WebsiteShortcut("spotify", "Spotify", "https://open.spotify.com/", [], True),
)
_WEB_ADDRESS = re.compile(
    r"(?:https?://)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}"
    r"(?:[/?#][^\s\\]*)?", re.I
)


def _search_website(query: str) -> str | None:
    brand = normalize_name(query).replace(" ", "")
    if not re.fullmatch(r"[a-z0-9]{3,63}", brand):
        return None
    try:
        response = httpx.get(
            "https://www.bing.com/search",
            params={"q": query, "format": "rss"},
            timeout=3.0,
        )
        response.raise_for_status()
        results = ElementTree.fromstring(response.content)
    except (httpx.HTTPError, ElementTree.ParseError):
        return None

    domain_pattern = re.compile(
        rf"(?:www\.|[a-z]{{2,3}}\.)?({brand}\.(?:(?:com|org|net|co)\.[a-z]{{2}}|[a-z]{{2,63}}))"
    )
    matches: dict[str, str] = {}
    for link in results.findall("./channel/item/link")[:12]:
        try:
            result = urlsplit(link.text or "")
        except ValueError:
            continue
        host = result.hostname or ""
        if result.scheme != "https" or result.netloc.lower() != host:
            continue
        if match := domain_pattern.fullmatch(host):
            matches.setdefault(match.group(1), f"https://{host}/")
    return next(iter(matches.values())) if len(matches) == 1 else None


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

    def resolve_navigation(self, query: str) -> tuple[WebsiteShortcut | None, bool]:
        if self.catalog is not None and (site := self.catalog.resolve_website(query)):
            return site, False
        if _WEB_ADDRESS.fullmatch(query):
            url = query if query.lower().startswith(("http://", "https://")) else f"https://{query}"
            return WebsiteShortcut("address", query, url, [], True), False

        name = normalize_name(query)
        scores = []
        for site in _DEFAULT_WEBSITES:
            names = [normalize_name(alias) for alias in [site.name, *site.aliases]]
            if name in names:
                return site, False
            if len(name) >= 5:
                score = max(SequenceMatcher(None, name, alias).ratio() for alias in names)
                scores.append((score, site))
        scores.sort(key=lambda match: match[0], reverse=True)
        if scores and scores[0][0] >= 0.82 and scores[0][0] - scores[1][0] >= 0.1:
            return scores[0][1], True
        if url := _search_website(query):
            return WebsiteShortcut("search", query, url, [], True), False
        return None, False

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
    clean = text.strip().rstrip(".!? ")
    if assistant_name:
        clean = re.sub(rf"^(?:(?:oye|ey|oeh)\s+)?{re.escape(assistant_name)}[, ]+", "", clean, flags=re.I)
    clean = re.sub(r"^(?:por favor\s+)?(?:me\s+)?puedes\s+", "", clean, flags=re.I)
    clean = re.sub(r"\s+por favor$", "", clean, flags=re.I)
    enter = re.fullmatch(r"entra\s+(.+)", clean, re.I)
    if enter:
        query = re.sub(r"^(?:a|en)(?:\s+|$)", "", enter.group(1), flags=re.I)
        return ("website", query) if query else None
    explicit = re.fullmatch(r"(?:busca|buscar|búscame|buscame|buscarme|reproduce|reproducir|pon|poner|ponme|ponerme|quiero escuchar|quiero ver)\s+(.+?)\s+en\s+(youtube|spotify|google)", clean, re.I)
    if explicit:
        return explicit.group(2).lower(), explicit.group(1)
    default = re.fullmatch(r"(?:pon|reproduce|ponme|reprodúceme|reproduceme)\s+(.+)", clean, re.I)
    return ("youtube", default.group(1)) if default else None
