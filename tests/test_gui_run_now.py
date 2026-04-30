"""tests/test_gui_run_now.py — '지금 실행' 버튼 단위 테스트."""
import os
import pytest
import tkinter as tk

if os.name != "nt" and not os.environ.get("DISPLAY"):
    pytest.skip("tkinter requires display", allow_module_level=True)


def _walk(widget):
    yield widget
    for c in widget.winfo_children():
        yield from _walk(c)


def test_run_now_button_exists(monkeypatch):
    from src.i18n import t
    from src.gui import WinLayoutSaverApp
    app = WinLayoutSaverApp()
    try:
        labels = [w.cget("text") for w in _walk(app)
                  if isinstance(w, tk.Button)]
        assert t("run_now_btn") in labels
    finally:
        app.destroy()


def test_run_now_calls_scheduler(monkeypatch):
    import src.scheduler as sched_mod
    import src.gui as gui_mod
    from src.gui import WinLayoutSaverApp

    monkeypatch.setattr(sched_mod, "run_now", lambda: (True, "OK"))
    shown = {"info": 0, "error": 0}
    monkeypatch.setattr(gui_mod.messagebox, "showinfo",
                        lambda *a, **kw: shown.__setitem__("info", shown["info"] + 1))
    monkeypatch.setattr(gui_mod.messagebox, "showerror",
                        lambda *a, **kw: shown.__setitem__("error", shown["error"] + 1))

    app = WinLayoutSaverApp()
    try:
        app._on_run_now()
        assert shown["info"] == 1
        assert shown["error"] == 0
    finally:
        app.destroy()


def test_run_now_failure_shows_error(monkeypatch):
    import src.scheduler as sched_mod
    import src.gui as gui_mod
    from src.gui import WinLayoutSaverApp

    monkeypatch.setattr(sched_mod, "run_now", lambda: (False, "작업 없음"))
    shown = {"info": 0, "error": 0, "error_msg": ""}
    monkeypatch.setattr(gui_mod.messagebox, "showinfo",
                        lambda *a, **kw: shown.__setitem__("info", shown["info"] + 1))
    def _err(_t, msg, **kw):
        shown["error"] += 1
        shown["error_msg"] = msg
    monkeypatch.setattr(gui_mod.messagebox, "showerror", _err)

    app = WinLayoutSaverApp()
    try:
        app._on_run_now()
        assert shown["error"] == 1
        assert "작업 없음" in shown["error_msg"]
    finally:
        app.destroy()
