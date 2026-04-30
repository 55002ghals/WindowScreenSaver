"""Task-13: PRIMARY_ONLY 라벨이 'Not matched'로 표시되는지."""
import pytest


def test_ml1_primary_only_returns_not_matched_text(monkeypatch):
    """UT-ML1: compare_monitors가 PRIMARY_ONLY를 반환하면 indicator 텍스트가 'Not matched' 포함."""
    pytest.importorskip("tkinter")
    import tkinter as tk

    from src.monitors import MatchResult

    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {"enabled": False, "layout_name": "", "mode": "fast", "startup_delay_seconds": 10},
        "ui": {"language": "ko"},
    })
    monkeypatch.setattr("src.storage.list_layouts", lambda: ["Screen1"])
    monkeypatch.setattr("src.storage.load_layout",
                        lambda n: {"monitors": [{"index": 0, "primary": True, "rect": [0, 0, 100, 100]}]})
    monkeypatch.setattr("src.storage.save_config", lambda _: None)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [{"index": 0, "primary": True, "rect": [0, 0, 100, 100]}])
    monkeypatch.setattr("src.gui.compare_monitors", lambda saved, current: MatchResult.PRIMARY_ONLY)

    from src.gui import WinLayoutSaverApp
    try:
        app = WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")
    try:
        app._current_monitors = [{"index": 0, "primary": True, "rect": [0, 0, 100, 100]}]
        text, color = app._get_match_indicator("Screen1")
        assert "Not matched" in text
        assert color == "orange"
    finally:
        app.destroy()
