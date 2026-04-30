import pytest
import os
from pathlib import Path


@pytest.fixture
def tmp_appdata(tmp_path, monkeypatch):
    """Redirect APPDATA to a temp directory for tests."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import src.paths as paths_mod
    import src.storage as storage_mod

    monkeypatch.setattr(paths_mod, "APPDATA", tmp_path / "WinLayoutSaver")
    monkeypatch.setattr(paths_mod, "LAYOUTS_DIR", tmp_path / "WinLayoutSaver" / "layouts")
    monkeypatch.setattr(paths_mod, "CONFIG_PATH", tmp_path / "WinLayoutSaver" / "config.json")
    monkeypatch.setattr(paths_mod, "LOGS_DIR", tmp_path / "WinLayoutSaver" / "logs")
    # Also patch storage module references
    monkeypatch.setattr(storage_mod, "APPDATA", tmp_path / "WinLayoutSaver")
    monkeypatch.setattr(storage_mod, "LAYOUTS_DIR", tmp_path / "WinLayoutSaver" / "layouts")
    monkeypatch.setattr(storage_mod, "CONFIG_PATH", tmp_path / "WinLayoutSaver" / "config.json")
    return tmp_path
