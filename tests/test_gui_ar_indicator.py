import os
import pytest

# tk가 없는 CI 환경에서는 skip
tk = pytest.importorskip("tkinter")


def test_apply_ar_toggle_style_enabled_changes_text_and_bg():
    from src.gui import WinLayoutSaverApp
    # Tk root 없이 메서드 호출이 어려우므로 실제 인스턴스 생성
    try:
        app = WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")
    try:
        app._apply_ar_toggle_style(True)
        text = app._ar_toggle_btn.cget("text")
        bg = str(app._ar_toggle_btn.cget("bg")).lower()
        assert text == "활성화됨" or text == "Enabled"
        assert bg in ("#2e7d32", "#2E7D32".lower())

        app._apply_ar_toggle_style(False)
        text2 = app._ar_toggle_btn.cget("text")
        assert text2 in ("활성화", "Enable")
    finally:
        app.destroy()
