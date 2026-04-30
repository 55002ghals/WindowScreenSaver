import re as _re
import sys
import types
import pytest


@pytest.fixture(autouse=True)
def mock_win32(monkeypatch):
    """Create mock win32 modules so tests run without pywin32 installed."""
    win32gui = types.ModuleType("win32gui")
    win32process = types.ModuleType("win32process")
    win32con = types.ModuleType("win32con")
    win32api = types.ModuleType("win32api")
    pywintypes = types.ModuleType("pywintypes")

    win32con.WS_EX_TOOLWINDOW = 0x80
    win32con.GW_HWNDNEXT = 2
    win32con.SW_SHOWNORMAL = 1
    win32con.SW_SHOWMINIMIZED = 2
    win32con.SW_SHOWMAXIMIZED = 3
    win32con.GWL_EXSTYLE = -20

    win32gui.GetWindowRect = lambda h: (0, 0, 800, 600)  # default: typical normal window

    sys.modules["win32gui"] = win32gui
    sys.modules["win32process"] = win32process
    sys.modules["win32con"] = win32con
    sys.modules["win32api"] = win32api
    sys.modules["pywintypes"] = pywintypes
    yield
    for mod in ["win32gui", "win32process", "win32con", "win32api", "pywintypes"]:
        sys.modules.pop(mod, None)
    sys.modules.pop("src.capture", None)



def test_filters_empty_title(monkeypatch):
    import win32gui, win32con
    win32gui.EnumWindows = lambda cb, extra: cb(1, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: ""  # empty title
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\prog.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert results == []


def test_filters_invisible_windows(monkeypatch):
    import win32gui, win32con
    win32gui.EnumWindows = lambda cb, extra: cb(2, extra)
    win32gui.IsWindowVisible = lambda h: False  # invisible
    win32gui.GetWindowText = lambda h: "Some Window"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\prog.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert results == []


def test_filters_tool_windows(monkeypatch):
    import win32gui, win32con
    hwnd = 3
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Tool Window"
    win32gui.GetWindowLong = lambda h, flag: win32con.WS_EX_TOOLWINDOW  # tool window
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\prog.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert results == []


def test_returns_expected_keys(monkeypatch):
    import win32gui, win32con
    hwnd = 4
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Notepad"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "Notepad"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (100, 100, 900, 700))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\Windows\\notepad.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    w = results[0]
    expected_keys = {
        "exe_path", "exe_args", "cwd", "title_snapshot", "title_pattern",
        "class_name", "placement", "monitor_index", "z_order",
        "is_topmost", "is_uwp", "hwnd"
    }
    assert set(w.keys()) == expected_keys


def test_placement_has_expected_subkeys(monkeypatch):
    import win32gui, win32con
    hwnd = 5
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Chrome"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "Chrome_WidgetWin_1"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (0, 0, 1920, 1080))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\Program Files\\Google\\Chrome\\chrome.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    p = results[0]["placement"]
    assert "state" in p
    assert "normal_rect" in p
    assert "min_pos" in p
    assert "max_pos" in p


def test_uwp_window_is_flagged(monkeypatch):
    import win32gui, win32con
    hwnd = 6
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Calculator"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "ApplicationFrameWindow"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (0, 0, 400, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\Windows\\SystemApps\\ApplicationFrameHost.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    assert results[0]["is_uwp"] is True


def test_non_uwp_window_not_flagged(monkeypatch):
    import win32gui, win32con
    hwnd = 7
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Notepad"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "Notepad"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\Windows\\notepad.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    assert results[0]["is_uwp"] is False


def test_minimized_state(monkeypatch):
    import win32gui, win32con
    hwnd = 8
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Minimized App"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWMINIMIZED, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    assert results[0]["placement"]["state"] == "minimized"


def test_maximized_state(monkeypatch):
    import win32gui, win32con
    hwnd = 9
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Maximized App"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWMAXIMIZED, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    assert results[0]["placement"]["state"] == "maximized"


def test_filters_cloaked_windows(monkeypatch):
    import win32gui, win32con
    hwnd = 10
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Cloaked Window"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "SomeClass"
    win32gui.GetWindowPlacement = lambda h: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: True)  # cloaked

    results = cap.list_current_windows()
    assert results == []


# ---------------------------------------------------------------------------
# _auto_title_pattern
# ---------------------------------------------------------------------------

class TestAutoTitlePattern:
    def test_extracts_app_name_suffix(self):
        from src.capture import _auto_title_pattern
        assert _auto_title_pattern("My Doc - Google Chrome") == "Google\\ Chrome$"

    def test_extracts_obsidian_suffix(self):
        from src.capture import _auto_title_pattern
        assert _auto_title_pattern("Vault - Obsidian") == "Obsidian$"

    def test_no_dash_returns_escaped_full_title(self):
        from src.capture import _auto_title_pattern
        result = _auto_title_pattern("제목 없음")
        assert result == _re.escape("제목 없음") + "$"

    def test_multiple_dashes_uses_last_segment(self):
        from src.capture import _auto_title_pattern
        assert _auto_title_pattern("a - b - MyApp") == "MyApp$"

    def test_pattern_matches_original_title(self):
        from src.capture import _auto_title_pattern
        title = "My Doc - Google Chrome"
        pattern = _auto_title_pattern(title)
        assert _re.search(pattern, title)


# ---------------------------------------------------------------------------
# B1 수정: normal 창은 GetWindowRect, min/max는 rcNormalPosition 사용 (Task-8)
# ---------------------------------------------------------------------------

def test_normal_window_uses_getwindowrect_for_normal_rect(monkeypatch):
    """normal 창(스냅 포함)은 rcNormalPosition 대신 GetWindowRect를 normal_rect로 저장."""
    import win32gui, win32con
    hwnd = 42
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Snapped Window"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "AppClass"
    # rcNormalPosition = 스냅 이전 위치 (실제 화면 위치와 다름)
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (498, 147, 1778, 962))
    # GetWindowRect = 실제 스냅 위치
    win32gui.GetWindowRect = lambda h: (810, 0, 1920, 1020)

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    nr = results[0]["placement"]["normal_rect"]
    # GetWindowRect [810,0,1920,1020] → XYWH [810, 0, 1110, 1020]
    assert nr == [810, 0, 1110, 1020], f"expected GetWindowRect coords, got {nr}"


def test_minimized_window_uses_rcnormalposition(monkeypatch):
    """minimized 창은 GetWindowRect를 쓰지 않고 rcNormalPosition을 그대로 저장."""
    import win32gui, win32con
    hwnd = 43
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Minimized App"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "AppClass"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWMINIMIZED, (-1, -1), (-1, -1), (100, 200, 900, 800))
    win32gui.GetWindowRect = lambda h: (0, 0, 1, 1)  # 최소화된 위치는 무시

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    nr = results[0]["placement"]["normal_rect"]
    # rcNormalPosition [100,200,900,800] → XYWH [100, 200, 800, 600]
    assert nr == [100, 200, 800, 600], f"expected rcNormalPosition coords, got {nr}"


def test_normal_window_getwindowrect_oserror_falls_back_to_rcnormalposition(monkeypatch):
    """GetWindowRect OSError 발생 시 rcNormalPosition을 fallback으로 사용."""
    import win32gui, win32con
    hwnd = 44
    win32gui.EnumWindows = lambda cb, extra: cb(hwnd, extra)
    win32gui.IsWindowVisible = lambda h: True
    win32gui.GetWindowText = lambda h: "Normal App"
    win32gui.GetWindowLong = lambda h, flag: 0
    win32gui.GetClassName = lambda h: "AppClass"
    win32gui.GetWindowPlacement = lambda h: (0, win32con.SW_SHOWNORMAL, (-1, -1), (-1, -1), (50, 60, 850, 660))
    def _raise_oserror(h):
        raise OSError("access denied")
    win32gui.GetWindowRect = _raise_oserror

    import src.capture as cap
    monkeypatch.setattr(cap, "_get_exe_path", lambda h: "C:\\app.exe")
    monkeypatch.setattr(cap, "_is_cloaked", lambda h: False)

    results = cap.list_current_windows()
    assert len(results) == 1
    nr = results[0]["placement"]["normal_rect"]
    # OSError → fallback: rcNormalPosition [50,60,850,660] → XYWH [50, 60, 800, 600]
    assert nr == [50, 60, 800, 600], f"expected rcNormalPosition fallback, got {nr}"


# ─────────────────────────────────────────────────────────────────────────────
# Task-13: capture_virtual_screen (UT-CAP1 ~ UT-CAP2)
# ─────────────────────────────────────────────────────────────────────────────

def test_cap1_capture_virtual_screen_writes_png(tmp_path, monkeypatch):
    """UT-CAP1: capture_virtual_screen(path)는 PIL.ImageGrab.grab을 호출하고 PNG로 저장 후 True 반환."""
    from unittest.mock import MagicMock
    fake_img = MagicMock()
    fake_imagegrab = MagicMock()
    fake_imagegrab.grab.return_value = fake_img

    import sys, types
    fake_pil = types.ModuleType("PIL")
    fake_pil.ImageGrab = fake_imagegrab
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.ImageGrab", fake_imagegrab)

    from src.capture import capture_virtual_screen
    out = tmp_path / "shot.png"
    result = capture_virtual_screen(out)

    assert result is True
    fake_imagegrab.grab.assert_called_once_with(all_screens=True)
    fake_img.save.assert_called_once_with(str(out), "PNG")


def test_cap2_capture_virtual_screen_returns_false_when_pil_missing(tmp_path, monkeypatch):
    """UT-CAP2: PIL import 실패 시 False 반환 (예외 전파 안 함)."""
    import sys
    monkeypatch.setitem(sys.modules, "PIL", None)

    from src.capture import capture_virtual_screen
    result = capture_virtual_screen(tmp_path / "shot.png")
    assert result is False
