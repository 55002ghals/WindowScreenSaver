"""Task-12: GUI 모드 선택 및 활성화 잠금 테스트."""
import pytest

tk = pytest.importorskip("tkinter")


def _make_app(monkeypatch, mode="fast", enabled=False, layouts=None):
    """테스트용 WinLayoutSaverApp 생성 헬퍼."""
    if layouts is None:
        layouts = ["Screen1"]
    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {
            "enabled": enabled,
            "layout_name": layouts[0] if layouts else "",
            "mode": mode,
            "startup_delay_seconds": 10,
        },
        "ui": {"language": "ko"},
    })
    monkeypatch.setattr("src.storage.list_layouts", lambda: layouts)
    monkeypatch.setattr("src.storage.save_config", lambda _: None)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [])

    from src.gui import WinLayoutSaverApp
    try:
        return WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")


# ------------------------------------------------------------------------------
# 모드 Radio 버튼 존재 및 기본값 (UT-GUI1 ~ UT-GUI2)
# ------------------------------------------------------------------------------

def test_gui1_mode_radio_defaults_to_fast(monkeypatch):
    """UT-GUI1: 설정에 mode='fast'이면 fast Radio가 선택된 상태로 초기화된다."""
    app = _make_app(monkeypatch, mode="fast")
    try:
        assert hasattr(app, "_ar_mode_var"), "_ar_mode_var 속성 없음"
        assert app._ar_mode_var.get() == "fast"
    finally:
        app.destroy()


def test_gui2_mode_radio_restores_full_from_config(monkeypatch):
    """UT-GUI2: 설정에 mode='full'이면 full Radio가 선택된 상태로 초기화된다."""
    app = _make_app(monkeypatch, mode="full")
    try:
        assert app._ar_mode_var.get() == "full"
    finally:
        app.destroy()


# ------------------------------------------------------------------------------
# 설명 Label 갱신 (UT-GUI3)
# ------------------------------------------------------------------------------

def test_gui3_mode_desc_updates_on_mode_change(monkeypatch):
    """UT-GUI3: _on_mode_change() 호출 시 _mode_desc_var가 선택 모드에 맞게 바뀐다."""
    app = _make_app(monkeypatch, mode="fast")
    try:
        app._ar_mode_var.set("fast")
        app._on_mode_change()
        fast_desc = app._mode_desc_var.get()
        assert fast_desc

        app._ar_mode_var.set("full")
        app._on_mode_change()
        full_desc = app._mode_desc_var.get()
        assert full_desc
        assert full_desc != fast_desc
    finally:
        app.destroy()


# ------------------------------------------------------------------------------
# 활성화 시 컨트롤 잠금 (UT-GUI4 ~ UT-GUI6)
# ------------------------------------------------------------------------------

def test_gui4_delay_entry_locked_when_enabled(monkeypatch):
    """UT-GUI4: _apply_ar_toggle_style(True) 시 _delay_entry state='disabled'."""
    app = _make_app(monkeypatch, enabled=False)
    try:
        app._apply_ar_toggle_style(True)
        assert app._delay_entry.cget("state") == "disabled"

        app._apply_ar_toggle_style(False)
        assert app._delay_entry.cget("state") == "normal"
    finally:
        app.destroy()


def test_gui5_mode_radios_locked_when_enabled(monkeypatch):
    """UT-GUI5: _apply_ar_toggle_style(True) 시 두 Radio 버튼 state='disabled'."""
    app = _make_app(monkeypatch, enabled=False)
    try:
        app._apply_ar_toggle_style(True)
        assert app._ar_mode_fast_rb.cget("state") == "disabled"
        assert app._ar_mode_full_rb.cget("state") == "disabled"

        app._apply_ar_toggle_style(False)
        assert app._ar_mode_fast_rb.cget("state") == "normal"
        assert app._ar_mode_full_rb.cget("state") == "normal"
    finally:
        app.destroy()


def test_gui6_layout_combo_locked_when_enabled(monkeypatch):
    """UT-GUI6: _apply_ar_toggle_style(True) 시 _ar_combo state='disabled'."""
    app = _make_app(monkeypatch, enabled=False)
    try:
        app._apply_ar_toggle_style(True)
        assert str(app._ar_combo.cget("state")) == "disabled"

        app._apply_ar_toggle_style(False)
        assert str(app._ar_combo.cget("state")) == "readonly"
    finally:
        app.destroy()


# ------------------------------------------------------------------------------
# _on_ar_toggle에서 mode 저장 (UT-GUI7)
# ------------------------------------------------------------------------------

def test_gui7_on_ar_toggle_saves_mode_to_config(monkeypatch):
    """UT-GUI7: 활성화 토글 시 현재 선택된 mode가 config에 저장된다."""
    saved = {}
    monkeypatch.setattr("src.scheduler.register", lambda **kw: True)
    monkeypatch.setattr("src.scheduler.unregister", lambda: True)

    app = _make_app(monkeypatch, mode="fast", enabled=False)
    # Re-apply after _make_app (which installs a no-op save_config internally)
    monkeypatch.setattr("src.storage.save_config", lambda cfg: saved.update(cfg))
    try:
        app._ar_mode_var.set("full")
        app._on_ar_toggle()

        assert saved.get("auto_rollback", {}).get("mode") == "full"
    finally:
        app.destroy()
