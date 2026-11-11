from pathlib import Path

from asistente.config.settings import FileAccessPreferenceStore
from asistente.tools.files import FileAccessService


def test_finds_authorized_file_with_spanish_desktop_location(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    document = desktop / "Calidad de software.pdf"
    document.write_bytes(b"not a real PDF")
    preferences = FileAccessPreferenceStore(tmp_path / "file-access.json")
    preferences.save({"folders": [str(desktop)], "extensions": ["txt"]})
    service = FileAccessService(preferences, tmp_path / "file-index.json")

    assert service.find_openable("calidad de software en escritorio") == [document]


def test_desktop_search_does_not_recurse_into_its_folders(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    direct_document = desktop / "Taller de robotica.pdf"
    direct_document.write_bytes(b"not a real PDF")
    nested = desktop / "AsistenteModular" / "node_modules"
    nested.mkdir(parents=True)
    (nested / "Taller de robotica.pdf").write_bytes(b"not a real PDF")
    preferences = FileAccessPreferenceStore(tmp_path / "file-access.json")
    preferences.save({"folders": [str(desktop)], "extensions": ["txt"]})
    service = FileAccessService(preferences, tmp_path / "file-index.json")

    assert service.find_openable("taller de robotica en escritorio") == [direct_document]
    assert service.find_openable("taller de robotica") == [direct_document]


def test_desktop_index_does_not_include_nested_files(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    direct_document = desktop / "Robotica.docx"
    direct_document.write_bytes(b"not a real document")
    nested_document = desktop / "AsistenteModular" / "node_modules" / "ignore.docx"
    nested_document.parent.mkdir(parents=True)
    nested_document.write_bytes(b"not a real document")
    preferences = FileAccessPreferenceStore(tmp_path / "file-access.json")
    preferences.save({"folders": [str(desktop)], "extensions": ["docx"]})
    service = FileAccessService(preferences, tmp_path / "file-index.json")

    assert service.refresh_index() == [
        {"name": "Robotica.docx", "path": str(direct_document.resolve()), "extension": "docx"}
    ]


def test_resolves_camel_case_filename_when_spoken_without_capitals(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    document = desktop / "TallerRobotica.docx"
    document.write_bytes(b"not a real document")
    preferences = FileAccessPreferenceStore(tmp_path / "file-access.json")
    preferences.save({"folders": [str(desktop)], "extensions": ["docx"]})
    service = FileAccessService(preferences, tmp_path / "file-index.json")
    service.refresh_index()

    assert service.resolve_from_request("resume el archivo tallerrobotica") == str(document.resolve())
