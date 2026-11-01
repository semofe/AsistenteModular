"""Accesos seguros iniciales disponibles en Windows."""

from __future__ import annotations

import os
from pathlib import Path


def builtin_windows_apps() -> list[dict[str, object]]:
    system_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        ("Calculadora", system_root / "System32" / "calc.exe", ["calculadora", "calc"]),
        ("Bloc de notas", system_root / "System32" / "notepad.exe", ["bloc de notas", "notepad"]),
        ("Explorador de archivos", system_root / "explorer.exe", ["explorador", "archivos"]),
    ]
    return [
        {"name": name, "kind": "application", "target": str(target), "aliases": aliases}
        for name, target, aliases in candidates if target.is_file()
    ]


def discover_start_menu_apps() -> list[dict[str, object]]:
    program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    app_data = Path(os.environ.get("APPDATA", r"C:\Users\Default\AppData\Roaming"))
    
    paths_to_scan = [
        program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    ]
    
    discovered = []
    seen_names = set()
    
    for base_path in paths_to_scan:
        if not base_path.is_dir():
            continue
        for lnk_file in base_path.rglob("*.lnk"):
            # Exclude uninstallers or help files
            name_lower = lnk_file.stem.lower()
            if any(x in name_lower for x in ["uninstall", "desinstalar", "help", "ayuda", "setup", "instalar"]):
                continue
                
            name = lnk_file.stem
            if name_lower in seen_names:
                continue
                
            seen_names.add(name_lower)
            aliases = [name.lower()]
            
            # Simple alias generation
            if " " in name:
                parts = name.lower().split()
                if len(parts) <= 3:
                    aliases.extend(parts)
            
            discovered.append({
                "name": name,
                "kind": "application",
                "target": str(lnk_file),
                "aliases": list(set(aliases))
            })
            
    return discovered


def sync_discovered_apps(catalog) -> int:
    """Add missing shortcuts without deleting or changing user entries."""
    added = 0
    for app in discover_start_menu_apps():
        if catalog.resolve(app["name"]) is None:
            try:
                catalog.add(**app)
                added += 1
            except ValueError:
                continue
    return added
