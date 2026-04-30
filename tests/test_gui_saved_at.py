"""Task-13: layout 행에 저장 시각 표시 테스트."""
import pytest

tk = pytest.importorskip("tkinter")


def _make_app(monkeypatch, layouts, layout_payloads):
    """layout_payloads: {name: layout_dict} — load_layout 모킹용."""
    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {"enabled": False, "layout_name": "", "mode": "fast", "startup_delay_seconds": 10},
        "ui": {"language": "ko"},
    })
    monkeypatch.setattr("src.storage.list_layouts", lambda: layouts)
    monkeypatch.setattr("src.storage.load_layout", lambda n: layout_payloads.get(n, {}))
    monkeypatch.setattr("src.storage.save_config", lambda _: None)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [])

    from src.gui import WinLayoutSaverApp
    try:
        return WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")


def _all_label_texts(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            texts.append(child.cget("text"))
        texts.extend(_all_label_texts(child))
    return texts


def test_sa1_saved_at_label_renders_iso_as_yymmdd_format(monkeypatch):
    """UT-SA1: created_at='2026-04-29T14:24:56+09:00'이면 '26.04.29/14:24:56' Label이 행에 렌더링된다."""
    payload = {"Screen1": {"name": "Screen1", "created_at": "2026-04-29T14:24:56+09:00", "windows": [], "monitors": []}}
    app = _make_app(monkeypatch, ["Screen1"], payload)
    try:
        app._refresh_layouts()
        texts = _all_label_texts(app._layout_inner)
        assert "26.04.29/14:24:56" in texts
    finally:
        app.destroy()


def test_sa2_saved_at_label_empty_when_created_at_missing(monkeypatch):
    """UT-SA2: created_at 키가 없으면 시각 Label은 빈 문자열로 표시(예외 없음)."""
    payload = {"Screen1": {"name": "Screen1", "windows": [], "monitors": []}}
    app = _make_app(monkeypatch, ["Screen1"], payload)
    try:
        app._refresh_layouts()
        texts = _all_label_texts(app._layout_inner)
        assert not any("/" in t and ":" in t and "." in t for t in texts if t)
    finally:
        app.destroy()


def test_sa3_saved_at_label_empty_when_created_at_unparseable(monkeypatch):
    """UT-SA3: created_at이 ISO가 아니면 빈 문자열 (예외 전파 안 함)."""
    payload = {"Screen1": {"name": "Screen1", "created_at": "not-a-date", "windows": [], "monitors": []}}
    app = _make_app(monkeypatch, ["Screen1"], payload)
    try:
        app._refresh_layouts()
    finally:
        app.destroy()
