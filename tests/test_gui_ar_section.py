"""Task-13: 자동복구 LabelFrame 구조 테스트."""
import pytest

tk = pytest.importorskip("tkinter")


def _make_app(monkeypatch):
    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {"enabled": False, "layout_name": "", "mode": "fast", "startup_delay_seconds": 10},
        "ui": {"language": "ko"},
    })
    monkeypatch.setattr("src.storage.list_layouts", lambda: ["Screen1"])
    monkeypatch.setattr("src.storage.save_config", lambda _: None)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [])
    from src.gui import WinLayoutSaverApp
    try:
        return WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")


def _is_descendant(widget, ancestor):
    w = widget
    while w is not None:
        if w is ancestor:
            return True
        w = w.master
    return False


def test_ars1_ar_section_is_labelframe(monkeypatch):
    app = _make_app(monkeypatch)
    try:
        assert hasattr(app, "_ar_section"), "_ar_section 속성 없음"
        assert isinstance(app._ar_section, tk.LabelFrame)
        title = str(app._ar_section.cget("text"))
        assert title
    finally:
        app.destroy()


def test_ars2_toggle_button_is_inside_ar_section(monkeypatch):
    app = _make_app(monkeypatch)
    try:
        assert _is_descendant(app._ar_toggle_btn, app._ar_section)
    finally:
        app.destroy()


def test_ars3_options_inside_ar_section(monkeypatch):
    app = _make_app(monkeypatch)
    try:
        for w in (app._ar_combo, app._ar_mode_fast_rb, app._ar_mode_full_rb, app._delay_entry):
            assert _is_descendant(w, app._ar_section), f"{w!r} not in _ar_section"
    finally:
        app.destroy()


def test_ars4_existing_lock_logic_still_works(monkeypatch):
    app = _make_app(monkeypatch)
    try:
        app._apply_ar_toggle_style(True)
        assert str(app._delay_entry.cget("state")) == "disabled"
        assert str(app._ar_combo.cget("state")) == "disabled"
        assert str(app._ar_mode_fast_rb.cget("state")) == "disabled"
        assert str(app._ar_mode_full_rb.cget("state")) == "disabled"

        app._apply_ar_toggle_style(False)
        assert str(app._delay_entry.cget("state")) == "normal"
        assert str(app._ar_combo.cget("state")) == "readonly"
        assert str(app._ar_mode_fast_rb.cget("state")) == "normal"
        assert str(app._ar_mode_full_rb.cget("state")) == "normal"
    finally:
        app.destroy()
