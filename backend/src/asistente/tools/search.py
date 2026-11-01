import os
import pathlib
import datetime
import time
import unicodedata

EXTENSION_CATEGORIES = {
    "documentos": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
    "hojas_de_calculo": [".xlsx", ".xls", ".csv"],
    "imagenes": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"],
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".webm"],
    "audio": [".mp3", ".wav", ".flac", ".ogg"]
}

def remove_accents(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')

def get_safe_locations() -> dict[str, pathlib.Path]:
    home = pathlib.Path.home()
    return {
        "desktop": home / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "pictures": home / "Pictures",
        "videos": home / "Videos",
        "music": home / "Music",
    }

def search_files_local(query: str | None = None, extension: str | None = None, location: str | None = None, max_results: int = 15) -> list[dict]:
    deadline = time.monotonic() + 8
    safe_locations = get_safe_locations()
    base_paths = []
    
    if location and location.lower() in safe_locations:
        base_paths.append(safe_locations[location.lower()])
    elif location:
        # If user specified a location but it's not a known safe location, we might fallback or return empty
        # For safety, let's search in documents and downloads if unknown, but better yet: return empty or try to map
        # If it's something like "descargas", we can handle aliases
        alias_map = {
            "descargas": "downloads", "documentos": "documents", "escritorio": "desktop",
            "imagenes": "pictures", "imágenes": "pictures", "fotos": "pictures",
            "videos": "videos", "musica": "music", "música": "music"
        }
        loc_lower = location.lower()
        if loc_lower in alias_map:
            base_paths.append(safe_locations[alias_map[loc_lower]])
        else:
            base_paths = list(safe_locations.values())
    else:
        # Default: search everywhere safe
        base_paths = list(safe_locations.values())
        
    query_lower = remove_accents(query.lower()) if query else None
    
    target_exts = []
    if extension:
        ext_lower = extension.lower()
        if ext_lower in EXTENSION_CATEGORIES:
            target_exts = EXTENSION_CATEGORIES[ext_lower]
        else:
            if not ext_lower.startswith("."):
                ext_lower = f".{ext_lower}"
            target_exts = [ext_lower]

    results = []
    
    for base_path in base_paths:
        if not base_path.exists():
            continue
            
        try:
            for root, dirs, files in os.walk(base_path):
                if time.monotonic() > deadline:
                    return results
                if ".git" in dirs: dirs.remove(".git")
                if "node_modules" in dirs: dirs.remove("node_modules")
                if ".venv" in dirs: dirs.remove(".venv")
                if "venv" in dirs: dirs.remove("venv")
                if "AppData" in dirs: dirs.remove("AppData")
                
                for file in files:
                    if target_exts:
                        _, ext = os.path.splitext(file)
                        if ext.lower() not in target_exts:
                            continue
                            
                    if query_lower and query_lower not in remove_accents(file.lower()):
                        continue
                        
                    file_path = pathlib.Path(root) / file
                    try:
                        stat = file_path.stat()
                        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        results.append({
                            "name": file,
                            "path": str(file_path),
                            "extension": file_path.suffix,
                            "size": stat.st_size,
                            "modified": mod_time
                        })
                    except OSError:
                        pass
                        
                    if len(results) >= max_results:
                        return results
        except OSError:
            pass

    return results
