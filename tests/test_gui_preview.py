"""Task-13: 미리보기 버튼 + Toplevel 창 + 저장 시 스크린샷 캡처 테스트."""
import pytest

tk = pytest.importorskip("tkinter")


def _make_app(monkeypatch, tmp_path, layouts=None, capture_return=True):
    if layouts is None:
        layouts = ["Screen1"]
    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {"enabled": False, "layout_name": "", "mode": "fast", "startup_delay_seconds": 10},
        "ui": {"language": "ko"},
    })
    monkeypatch.setattr("src.storage.list_layouts", lambda: layouts)
    monkeypatch.setattr("src.storage.load_layout", lambda n: {"name": n, "windows": [], "monitors": []})
    monkeypatch.setattr("src.storage.save_config", lambda _: None)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [])

    monkeypatch.setattr("src.storage.screenshot_path",
                        lambda name: tmp_path / f"{name}.png")

    from src.gui import WinLayoutSaverApp
    try:
        return WinLayoutSaverApp()
    except tk.TclError:
        pytest.skip("display unavailable")


def _find_buttons_with_text(widget, text):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Button) and str(child.cget("text")) == text:
            found.append(child)
        found.extend(_find_buttons_with_text(child, text))
    return found


def test_pv1_preview_button_appears_for_each_layout(monkeypatch, tmp_path):
    """UT-PV1: 각 layout 행에 '미리보기' 버튼이 1개씩 렌더링된다."""
    app = _make_app(monkeypatch, tmp_path, layouts=["Screen1", "Screen2"])
    try:
        from src.i18n import t
        btns = _find_buttons_with_text(app._layout_inner, t("preview_btn"))
        assert len(btns) == 2
    finally:
        app.destroy()


def test_pv2_preview_shows_messagebox_when_png_missing(monkeypatch, tmp_path):
    """UT-PV2: PNG 파일이 없으면 messagebox.showinfo 호출, Toplevel은 띄우지 않음."""
    app = _make_app(monkeypatch, tmp_path)
    try:
        called = {}
        def fake_showinfo(title, message, **kw):
            called["title"] = title
            called["message"] = message
        monkeypatch.setattr("tkinter.messagebox.showinfo", fake_showinfo)

        toplevel_count_before = len([w for w in app.winfo_children() if isinstance(w, tk.Toplevel)])
        app._on_preview("Screen1")
        toplevel_count_after = len([w for w in app.winfo_children() if isinstance(w, tk.Toplevel)])

        assert "message" in called
        assert toplevel_count_after == toplevel_count_before
    finally:
        app.destroy()


def test_pv3_preview_opens_toplevel_when_png_exists(monkeypatch, tmp_path):
    """UT-PV3: PNG 파일이 있으면 Toplevel 창을 띄운다."""
    app = _make_app(monkeypatch, tmp_path)
    try:
        png_path = tmp_path / "Screen1.png"
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")
        Image.new("RGB", (10, 10), "white").save(str(png_path), "PNG")

        before = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        app._on_preview("Screen1")
        after = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]

        assert len(after) == len(before) + 1
        for w in after:
            if w not in before:
                w.destroy()
    finally:
        app.destroy()


def test_pv4_on_save_calls_capture_virtual_screen(monkeypatch, tmp_path):
    """UT-PV4: _on_save 워커가 capture_virtual_screen(screenshot_path)을 호출한다."""
    captured = {}

    def fake_capture(path):
        captured["path"] = path
        return True

    monkeypatch.setattr("src.capture.list_current_windows", lambda: [])
    monkeypatch.setattr("src.capture.capture_virtual_screen", fake_capture)
    monkeypatch.setattr("src.storage.save_layout", lambda name, layout: None)
    monkeypatch.setattr("src.storage.next_layout_name", lambda: "Screen99")

    app = _make_app(monkeypatch, tmp_path)
    try:
        class _ImmediateThread:
            def __init__(self, target, daemon=None):
                self._target = target
            def start(self):
                self._target()
        monkeypatch.setattr("src.gui.threading.Thread", _ImmediateThread)

        app._on_save()

        assert "path" in captured
        assert captured["path"] == tmp_path / "Screen99.png"
    finally:
        app.destroy()
