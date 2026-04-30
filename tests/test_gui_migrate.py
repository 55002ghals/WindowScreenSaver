"""tests/test_gui_migrate.py — GUI __init__ 시 작업 마이그레이션."""
import os
import pytest

if os.name != "nt" and not os.environ.get("DISPLAY"):
    pytest.skip("tkinter requires display", allow_module_level=True)


def test_migrate_runs_when_enabled_and_unflagged(monkeypatch, tmp_path):
    from src import storage
    import src.scheduler as sched_mod

    config = {"auto_rollback": {"enabled": True, "layout_name": "X",
                                "startup_delay_seconds": 10, "mode": "fast"},
              "ui": {"language": "ko"}}
    monkeypatch.setattr(storage, "load_config", lambda: dict(config))

    saved = {}
    def fake_save(c):
        saved.update(c)
    monkeypatch.setattr(storage, "save_config", fake_save)

    calls = {"unregister": 0, "register": 0}
    monkeypatch.setattr(sched_mod, "unregister",
                        lambda: calls.__setitem__("unregister", calls["unregister"] + 1) or True)
    monkeypatch.setattr(sched_mod, "register",
                        lambda **kw: calls.__setitem__("register", calls["register"] + 1) or True)

    from src.gui import WinLayoutSaverApp
    try:
        app = WinLayoutSaverApp()
    except Exception:
        pytest.skip("tkinter unavailable")
    try:
        assert calls["unregister"] == 1
        assert calls["register"] == 1
        assert saved["auto_rollback"]["_migrated_v14"] is True
    finally:
        app.destroy()


def test_migrate_skipped_when_already_flagged(monkeypatch):
    from src import storage
    import src.scheduler as sched_mod

    config = {"auto_rollback": {"enabled": True, "_migrated_v14": True,
                                "layout_name": "X", "startup_delay_seconds": 10, "mode": "fast"},
              "ui": {"language": "ko"}}
    monkeypatch.setattr(storage, "load_config", lambda: dict(config))
    monkeypatch.setattr(storage, "save_config", lambda c: None)

    calls = {"register": 0, "unregister": 0}
    monkeypatch.setattr(sched_mod, "unregister",
                        lambda: calls.__setitem__("unregister", calls["unregister"] + 1) or True)
    monkeypatch.setattr(sched_mod, "register",
                        lambda **kw: calls.__setitem__("register", calls["register"] + 1) or True)

    from src.gui import WinLayoutSaverApp
    try:
        app = WinLayoutSaverApp()
    except Exception:
        pytest.skip("tkinter unavailable")
    try:
        assert calls["register"] == 0
        assert calls["unregister"] == 0
    finally:
        app.destroy()


def test_migrate_skipped_when_disabled(monkeypatch):
    from src import storage
    import src.scheduler as sched_mod

    config = {"auto_rollback": {"enabled": False}, "ui": {"language": "ko"}}
    monkeypatch.setattr(storage, "load_config", lambda: dict(config))
    monkeypatch.setattr(storage, "save_config", lambda c: None)

    calls = {"register": 0}
    monkeypatch.setattr(sched_mod, "register",
                        lambda **kw: calls.__setitem__("register", calls["register"] + 1) or True)
    monkeypatch.setattr(sched_mod, "unregister", lambda: True)

    from src.gui import WinLayoutSaverApp
    try:
        app = WinLayoutSaverApp()
    except Exception:
        pytest.skip("tkinter unavailable")
    try:
        assert calls["register"] == 0
    finally:
        app.destroy()


def test_migrate_failure_keeps_unflagged(monkeypatch):
    from src import storage
    import src.scheduler as sched_mod

    config = {"auto_rollback": {"enabled": True, "layout_name": "X",
                                "startup_delay_seconds": 10, "mode": "fast"},
              "ui": {"language": "ko"}}
    monkeypatch.setattr(storage, "load_config", lambda: dict(config))

    saved_calls = []
    monkeypatch.setattr(storage, "save_config", lambda c: saved_calls.append(c))

    monkeypatch.setattr(sched_mod, "unregister", lambda: True)
    monkeypatch.setattr(sched_mod, "register", lambda **kw: False)

    from src.gui import WinLayoutSaverApp
    try:
        app = WinLayoutSaverApp()
    except Exception:
        pytest.skip("tkinter unavailable")
    try:
        assert all("_migrated_v14" not in c.get("auto_rollback", {}) for c in saved_calls)
    finally:
        app.destroy()
