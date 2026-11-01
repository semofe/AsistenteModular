"""Apertura de destinos autorizados sin intérprete de comandos."""

from __future__ import annotations

import os
import subprocess
import csv
import ctypes
import io
from dataclasses import dataclass
from pathlib import Path

from asistente.access.catalog import AccessEntry
from asistente.access.path_policy import validate_target


@dataclass(frozen=True, slots=True)
class OpenResult:
    entry_id: str
    name: str
    kind: str
    opened: bool


@dataclass(frozen=True, slots=True)
class CloseResult:
    entry_id: str
    name: str
    closed: bool


@dataclass(frozen=True, slots=True)
class MinimizeResult:
    entry_id: str
    name: str
    minimized: bool


PROTECTED_EXECUTABLES = {
    "csrss.exe", "dwm.exe", "explorer.exe", "lsass.exe", "services.exe",
    "smss.exe", "svchost.exe", "system", "wininit.exe", "winlogon.exe",
}

PROCESS_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "calc.exe": ("CalculatorApp.exe",),
}

WINDOW_PROCESS_ALIASES: dict[str, tuple[str, ...]] = {
    "steam.exe": ("steam.exe", "steamwebhelper.exe"),
    "epicgameslauncher.exe": ("EpicGamesLauncher.exe", "EpicWebHelper.exe"),
    "galaxyclient.exe": ("GalaxyClient.exe", "GalaxyClient Helper.exe"),
    "ubisoftconnect.exe": ("UbisoftConnect.exe",),
    "upc.exe": ("upc.exe",),
    "eadesktop.exe": ("EADesktop.exe",),
}


def _shortcut_executable(shortcut: Path) -> Path:
    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    if not powershell.is_file():
        raise RuntimeError("No se pudo resolver el acceso directo de la aplicación.")
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ASISTENTE_SHORTCUT);"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8;"
        "Write-Output $s.TargetPath"
    )
    completed = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "ASISTENTE_SHORTCUT": str(shortcut)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    target = Path(completed.stdout.strip())
    if completed.returncode != 0 or target.suffix.casefold() != ".exe":
        raise RuntimeError("El acceso directo no apunta a una aplicación ejecutable.")
    return target


def close_entry(entry: AccessEntry) -> CloseResult:
    if not entry.enabled or entry.kind != "application":
        raise ValueError("Este acceso no corresponde a una aplicación habilitada.")
    target = validate_target(entry.kind, entry.target)
    if os.name != "nt":
        raise RuntimeError("El cierre de aplicaciones está disponible únicamente en Windows.")
    executable = target if target.suffix.casefold() == ".exe" else _shortcut_executable(target)
    image_name = executable.name.casefold()
    if image_name in PROTECTED_EXECUTABLES:
        raise ValueError("Esa aplicación forma parte del sistema y no se puede cerrar.")
    if entry.close_policy == "window":
        process_names = WINDOW_PROCESS_ALIASES.get(image_name, (executable.name,))
        process_ids = _process_ids(process_names)
        return CloseResult(entry.id, entry.name, _send_window_command(process_ids, 0x0010))
    taskkill = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/taskkill.exe"
    process_names = PROCESS_NAME_ALIASES.get(image_name, (executable.name,))
    closed = False
    for process_name in process_names:
        completed = subprocess.run(
            [str(taskkill), "/IM", process_name],
            capture_output=True,
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        closed = completed.returncode == 0 or closed
    return CloseResult(entry.id, entry.name, closed)


def _process_ids(process_names: tuple[str, ...]) -> set[int]:
    expected_names = {name.casefold() for name in process_names}
    tasklist = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/tasklist.exe"
    completed = subprocess.run(
        [str(tasklist), "/FO", "CSV", "/NH"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if completed.returncode != 0:
        raise RuntimeError("Windows no pudo consultar las aplicaciones abiertas.")
    return {
        int(row[1]) for row in csv.reader(io.StringIO(completed.stdout))
        if len(row) >= 2 and row[0].casefold() in expected_names and row[1].isdigit()
    }


def _send_window_command(process_ids: set[int], message: int) -> bool:
    if not process_ids:
        return False
    user32 = ctypes.windll.user32
    affected = 0
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def send_to_window(window: int, _parameter: int) -> bool:
        nonlocal affected
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if process_id.value in process_ids and user32.IsWindowVisible(window):
            user32.PostMessageW(window, message, 0, 0)
            affected += 1
        return True

    user32.EnumWindows(send_to_window, 0)
    return affected > 0


def minimize_entry(entry: AccessEntry) -> MinimizeResult:
    if not entry.enabled or entry.kind != "application":
        raise ValueError("Este acceso no corresponde a una aplicación habilitada.")
    target = validate_target(entry.kind, entry.target)
    if os.name != "nt":
        raise RuntimeError("Minimizar aplicaciones está disponible únicamente en Windows.")
    executable = target if target.suffix.casefold() == ".exe" else _shortcut_executable(target)
    image_name = executable.name.casefold()
    if image_name in PROTECTED_EXECUTABLES:
        raise ValueError("Esa aplicación forma parte del sistema y no se puede minimizar.")
    process_ids = _process_ids(PROCESS_NAME_ALIASES.get(image_name, (executable.name,)))
    if not process_ids:
        return MinimizeResult(entry.id, entry.name, False)

    user32 = ctypes.windll.user32
    minimized = 0
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def minimize_window(window: int, _parameter: int) -> bool:
        nonlocal minimized
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if process_id.value in process_ids and user32.IsWindowVisible(window):
            user32.ShowWindowAsync(window, 6)
            minimized += 1
        return True

    user32.EnumWindows(minimize_window, 0)
    return MinimizeResult(entry.id, entry.name, minimized > 0)


def open_entry(entry: AccessEntry) -> OpenResult:
    if not entry.enabled:
        raise ValueError("Este acceso está desactivado.")
    target = validate_target(entry.kind, entry.target)
    if os.name != "nt":
        raise RuntimeError("La apertura de accesos está disponible únicamente en Windows.")
    if entry.kind == "application" and target.suffix.casefold() == ".exe":
        subprocess.Popen(
            [str(target), *entry.arguments],
            cwd=entry.working_directory or str(target.parent),
            shell=False,
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        os.startfile(str(target))
    return OpenResult(entry.id, entry.name, entry.kind, True)
