"""Tests for src/launcher.py — mocks psutil and subprocess."""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc_info(exe: str):
    """Return a mock psutil Process with info dict."""
    p = MagicMock()
    p.info = {"exe": exe}
    return p


def _saved_window(
    exe_path="C:\\app.exe",
    exe_args="",
    cwd="",
    is_uwp=False,
    title_pattern="",
):
    return {
        "exe_path": exe_path,
        "exe_args": exe_args,
        "cwd": cwd,
        "is_uwp": is_uwp,
        "title_pattern": title_pattern,
    }


def _running_window(exe_path="C:\\app.exe", title="App Window"):
    return {
        "exe_path": exe_path,
        "title_snapshot": title,
    }


# ---------------------------------------------------------------------------
# is_running tests
# ---------------------------------------------------------------------------

def test_is_running_true(monkeypatch):
    """Process with matching exe_path is running."""
    import psutil
    mock_proc = _make_proc_info("C:\\app.exe")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [mock_proc])

    from src.launcher import is_running
    assert is_running("C:\\app.exe") is True


def test_is_running_false(monkeypatch):
    """No process with that exe_path."""
    import psutil
    mock_proc = _make_proc_info("C:\\other.exe")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [mock_proc])

    from src.launcher import is_running
    assert is_running("C:\\app.exe") is False


def test_is_running_case_insensitive(monkeypatch):
    """exe path match is case-insensitive."""
    import psutil
    mock_proc = _make_proc_info("C:\\App.EXE")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [mock_proc])

    from src.launcher import is_running
    assert is_running("c:\\app.exe") is True


# ---------------------------------------------------------------------------
# launch_app tests
# ---------------------------------------------------------------------------

def test_launch_app_calls_popen(monkeypatch):
    """When app not running, Popen is called with correct args."""
    mock_popen = MagicMock()
    mock_popen.return_value = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    from src.launcher import launch_app
    result = launch_app("C:\\app.exe", exe_args="--flag val")

    mock_popen.assert_called_once()
    cmd_arg = mock_popen.call_args[0][0]
    assert cmd_arg[0] == "C:\\app.exe"
    assert "--flag" in cmd_arg
    assert "val" in cmd_arg
    assert result is not None


def test_launch_app_not_called_when_running(monkeypatch):
    """When app already running, Popen is not called (caller is responsible)."""
    import psutil
    mock_proc = _make_proc_info("C:\\app.exe")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [mock_proc])

    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    from src.launcher import is_running
    # is_running returns True; caller should not call launch_app
    assert is_running("C:\\app.exe") is True
    mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# wait_for_window tests
# ---------------------------------------------------------------------------

def test_wait_for_window_found(monkeypatch):
    """list_current_windows returns matching window on 2nd poll."""
    call_count = {"n": 0}

    def fake_list():
        call_count["n"] += 1
        if call_count["n"] < 2:
            return []
        return [_running_window("C:\\app.exe", "App Window")]

    monkeypatch.setattr("src.launcher.list_current_windows", fake_list)
    monkeypatch.setattr("time.sleep", lambda _: None)

    from src.launcher import wait_for_window
    result = wait_for_window("C:\\app.exe", title_pattern="App.*", timeout_seconds=10, poll_ms=50)
    assert result is True


def test_wait_for_window_timeout(monkeypatch):
    """Returns empty list every time; verify timeout after N retries."""
    call_count = {"n": 0}

    def fake_list():
        call_count["n"] += 1
        return []

    # Use a very short timeout and patch time.monotonic to advance quickly
    tick = {"t": 0.0}

    def fake_monotonic():
        val = tick["t"]
        tick["t"] += 0.6  # advance 600ms each call (past poll_ms=500)
        return val

    monkeypatch.setattr("src.launcher.list_current_windows", fake_list)
    monkeypatch.setattr("time.sleep", lambda _: None)
    monkeypatch.setattr("time.monotonic", fake_monotonic)

    from src.launcher import wait_for_window
    result = wait_for_window("C:\\app.exe", title_pattern="", timeout_seconds=1.0, poll_ms=500)
    assert result is False
    # Must have polled at least once
    assert call_count["n"] >= 1


# ---------------------------------------------------------------------------
# ensure_apps_running tests
# ---------------------------------------------------------------------------

def test_ensure_apps_running_skips_empty_exe_path(monkeypatch):
    """exe_path=""인 창은 실행 불가이므로 launch_app을 호출하지 않는다."""
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: [])

    launched = []
    monkeypatch.setattr("src.launcher.launch_app",
                        lambda exe, *args, **kw: launched.append(exe) or MagicMock())
    monkeypatch.setattr("src.launcher.wait_for_window", lambda *a, **kw: True)

    from src.launcher import ensure_apps_running
    ensure_apps_running([{"exe_path": "", "exe_args": "", "cwd": "",
                          "is_uwp": False, "title_pattern": ""}])
    assert launched == []   # exe_path="" → 실행 시도 안 함


# ---------------------------------------------------------------------------
# has_visible_window tests (TC1–TC3)
# ---------------------------------------------------------------------------

def test_has_visible_window_no_windows(monkeypatch):
    """TC1: Chrome background process only, no visible window → False."""
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: [])

    from src.launcher import has_visible_window
    assert has_visible_window("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "Chrome$") is False


def test_has_visible_window_chrome_window_exists(monkeypatch):
    """TC2: Chrome window visible → True."""
    windows = [{"exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "title_snapshot": "새 탭 - Chrome"}]
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)

    from src.launcher import has_visible_window
    assert has_visible_window("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "Chrome$") is True


def test_has_visible_window_exe_mismatch(monkeypatch):
    """TC3: Notepad running but querying for Chrome → False."""
    windows = [{"exe_path": "C:\\Windows\\notepad.exe", "title_snapshot": "Untitled - Notepad"}]
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)

    from src.launcher import has_visible_window
    assert has_visible_window("C:\\chrome.exe", "Chrome$") is False


# ---------------------------------------------------------------------------
# ensure_apps_running: has_visible_window-based tests (TC4–TC5)
# ---------------------------------------------------------------------------

def test_ensure_apps_running_no_window_launches(monkeypatch):
    """TC4: No visible window for saved app → launch_app is called."""
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: [])

    launched = []

    def fake_launch_app(exe_path, exe_args="", cwd="", is_uwp=False):
        launched.append(exe_path)
        return MagicMock()

    monkeypatch.setattr("src.launcher.launch_app", fake_launch_app)
    monkeypatch.setattr("src.launcher._wait_for_window_count", lambda *a, **kw: True)

    from src.launcher import ensure_apps_running
    ensure_apps_running([_saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$")],
                        timeout_seconds=5, poll_ms=50)
    assert launched == ["C:\\chrome.exe"]


def test_ensure_apps_running_window_exists_no_launch(monkeypatch):
    """TC5: Chrome window already visible → launch_app is NOT called."""
    windows = [{"exe_path": "C:\\chrome.exe", "title_snapshot": "New Tab - Chrome"}]
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)

    launched = []

    def fake_launch_app(exe_path, exe_args="", cwd="", is_uwp=False):
        launched.append(exe_path)
        return MagicMock()

    monkeypatch.setattr("src.launcher.launch_app", fake_launch_app)

    from src.launcher import ensure_apps_running
    ensure_apps_running([_saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$")],
                        timeout_seconds=5, poll_ms=50)
    assert launched == []


def test_restore_layout_launches_missing_app_then_rematch(monkeypatch):
    """복원 시 꺼진 앱을 자동 실행하고 재스캔 후 재매칭한다."""
    import types, sys

    # Stub out win32 modules for restore.py
    win32gui = types.ModuleType("win32gui")
    win32con = types.ModuleType("win32con")
    win32con.SW_SHOWNORMAL = 1
    win32con.SW_SHOWMINIMIZED = 2
    win32con.SW_SHOWMAXIMIZED = 3
    win32gui.SetWindowPlacement = lambda *a: None
    win32gui.SetWindowPos = lambda *a: None
    win32gui.GetWindowPlacement = lambda *a: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))
    win32gui.GetWindowRect = lambda *a: (0, 0, 800, 600)
    sys.modules["win32gui"] = win32gui
    sys.modules["win32con"] = win32con

    # 첫 번째 스캔: Chrome 없음 / 두 번째 스캔: Chrome 있음
    scan_count = {"n": 0}

    def fake_list_current():
        scan_count["n"] += 1
        if scan_count["n"] == 1:
            return []
        return [{
            "hwnd": 0xABCD,
            "exe_path": "C:\\chrome.exe",
            "title_snapshot": "NAVER - Chrome",
            "title_pattern": "Chrome$",
            "class_name": "Chrome_WidgetWin_1",
            "is_hidden": False,
        }]

    launched = []

    def fake_ensure(saved_windows, **kwargs):
        for w in saved_windows:
            if w.get("exe_path"):
                launched.append(w["exe_path"])

    monkeypatch.setattr("src.capture.list_current_windows", fake_list_current)
    monkeypatch.setattr("src.launcher.ensure_apps_running", fake_ensure)

    sys.modules.pop("src.restore", None)

    from src.restore import restore_layout

    layout = {
        "name": "test",
        "windows": [{
            "exe_path": "C:\\chrome.exe",
            "title_snapshot": "NAVER - Chrome",
            "title_pattern": "Chrome$",
            "class_name": "Chrome_WidgetWin_1",
            "placement": {"state": "normal", "normal_rect": [0, 0, 800, 600],
                          "min_pos": [-1, -1], "max_pos": [-1, -1]},
            "z_order": 0,
        }],
        "monitors": [],
    }

    result = restore_layout(layout)

    assert "C:\\chrome.exe" in launched   # 자동 실행 시도
    assert scan_count["n"] == 2           # 두 번 스캔 (launch 전/후)
    assert result["restored"] == 1

    # Cleanup
    for mod in ["win32gui", "win32con", "src.restore"]:
        sys.modules.pop(mod, None)


def test_restore_layout_with_prescan_skips_ensure_bug(monkeypatch):
    """GUI 경로(running_windows 미리 전달) 재현 — 버그 확인 후 올바른 경로 검증."""
    import types, sys

    win32gui = types.ModuleType("win32gui")
    win32con = types.ModuleType("win32con")
    win32con.SW_SHOWNORMAL = 1
    win32con.SW_SHOWMINIMIZED = 2
    win32con.SW_SHOWMAXIMIZED = 3
    win32gui.SetWindowPlacement = lambda *a: None
    win32gui.SetWindowPos = lambda *a: None
    win32gui.GetWindowPlacement = lambda *a: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))
    win32gui.GetWindowRect = lambda *a: (0, 0, 800, 600)
    sys.modules["win32gui"] = win32gui
    sys.modules["win32con"] = win32con

    scan_count = {"n": 0}

    def fake_list_current():
        scan_count["n"] += 1
        if scan_count["n"] >= 2:
            return [{
                "hwnd": 0xABCD,
                "exe_path": "C:\\chrome.exe",
                "title_snapshot": "NAVER - Chrome",
                "title_pattern": "Chrome$",
                "class_name": "Chrome_WidgetWin_1",
                "is_hidden": False,
            }]
        return []

    launched = []

    def fake_ensure(saved_windows, **kwargs):
        for w in saved_windows:
            if w.get("exe_path"):
                launched.append(w["exe_path"])

    monkeypatch.setattr("src.capture.list_current_windows", fake_list_current)
    monkeypatch.setattr("src.launcher.ensure_apps_running", fake_ensure)

    sys.modules.pop("src.restore", None)

    from src.restore import restore_layout

    layout = {
        "name": "test",
        "windows": [{
            "exe_path": "C:\\chrome.exe",
            "title_snapshot": "NAVER - Chrome",
            "title_pattern": "Chrome$",
            "class_name": "Chrome_WidgetWin_1",
            "placement": {"state": "normal", "normal_rect": [0, 0, 800, 600],
                          "min_pos": [-1, -1], "max_pos": [-1, -1]},
            "z_order": 0,
        }],
        "monitors": [],
    }

    # GUI 수정 후 경로: running_windows 미전달 → ensure_apps_running 내부 호출
    result = restore_layout(layout)

    assert "C:\\chrome.exe" in launched, "ensure_apps_running이 호출되지 않았음"
    assert result["restored"] == 1

    for mod in ["win32gui", "win32con", "src.restore"]:
        sys.modules.pop(mod, None)


# ---------------------------------------------------------------------------
# ensure_apps_running 반환값 테스트 (UT-L1, UT-L2)
# ---------------------------------------------------------------------------

def test_ensure_apps_running_returns_zero_when_all_running(monkeypatch):
    """모든 앱이 이미 실행 중 → 0 반환."""
    windows = [{"exe_path": "C:\\app.exe", "title_snapshot": "App Window"}]
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)

    from src.launcher import ensure_apps_running
    result = ensure_apps_running([_saved_window(exe_path="C:\\app.exe", title_pattern="App")])
    assert result == 0


def test_ensure_apps_running_returns_count_of_launched(monkeypatch):
    """2개 앱 모두 없음 → 2회 론칭, 반환값 2."""
    monkeypatch.setattr("src.launcher.list_current_windows", lambda: [])

    launched = []

    def fake_launch(exe, *a, **kw):
        launched.append(exe)
        return MagicMock()

    monkeypatch.setattr("src.launcher.launch_app", fake_launch)
    monkeypatch.setattr("src.launcher._wait_for_window_count", lambda *a, **kw: True)

    from src.launcher import ensure_apps_running
    result = ensure_apps_running([
        _saved_window(exe_path="C:\\a.exe", title_pattern=""),
        _saved_window(exe_path="C:\\b.exe", title_pattern=""),
    ])
    assert result == 2
    assert len(launched) == 2


def test_uwp_uses_explorer_shell(monkeypatch):
    """Saved window with is_uwp=True and AUMID in exe_args uses explorer.exe shell:AppsFolder."""
    mock_popen = MagicMock()
    mock_popen.return_value = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    aumid = "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"

    from src.launcher import launch_app
    launch_app("C:\\Windows\\ApplicationFrameHost.exe", exe_args=aumid, is_uwp=True)

    mock_popen.assert_called_once()
    cmd_arg = mock_popen.call_args[0][0]
    assert cmd_arg[0] == "explorer.exe"
    assert f"shell:AppsFolder\\{aumid}" in cmd_arg


# ---------------------------------------------------------------------------
# TestEnsureAppsRunningMultiWindow (UT-T10-L1 ~ UT-T10-L3)
# ---------------------------------------------------------------------------

class TestEnsureAppsRunningMultiWindow:
    def test_two_saved_one_running_launches_once(self, monkeypatch):
        """
        Chrome 2개 저장, 1개만 실행 중 → deficit=1 → launch 1회.
        (title_pattern='Chrome$' 동일해도 count 기반이므로 정확히 탐지)
        """
        windows = [{"exe_path": "C:\\chrome.exe", "title_snapshot": "CertiNavigator - Chrome"}]
        monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)
        monkeypatch.setattr("src.launcher._wait_for_window_count", lambda *a, **kw: True)

        launched = []
        monkeypatch.setattr("src.launcher.launch_app",
                            lambda exe, *a, **kw: launched.append(exe) or MagicMock())

        from src.launcher import ensure_apps_running
        result = ensure_apps_running([
            _saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$"),
            _saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$"),
        ], timeout_seconds=5, poll_ms=50)

        assert launched == ["C:\\chrome.exe"]   # 1회 launch
        assert result == 1

    def test_two_saved_two_running_no_launch(self, monkeypatch):
        """Chrome 2개 저장, 2개 실행 중 → deficit=0 → launch 없음."""
        windows = [
            {"exe_path": "C:\\chrome.exe", "title_snapshot": "CertiNavigator - Chrome"},
            {"exe_path": "C:\\chrome.exe", "title_snapshot": "새 탭 - Chrome"},
        ]
        monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)

        launched = []
        monkeypatch.setattr("src.launcher.launch_app",
                            lambda exe, *a, **kw: launched.append(exe) or MagicMock())

        from src.launcher import ensure_apps_running
        result = ensure_apps_running([
            _saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$"),
            _saved_window(exe_path="C:\\chrome.exe", title_pattern="Chrome$"),
        ], timeout_seconds=5, poll_ms=50)

        assert launched == []
        assert result == 0

    def test_wait_for_window_count_true_when_met(self, monkeypatch):
        """exe_path 창 수가 min_count 이상이면 True."""
        windows = [{"exe_path": "C:\\chrome.exe"}, {"exe_path": "C:\\chrome.exe"}]
        monkeypatch.setattr("src.launcher.list_current_windows", lambda: windows)
        monkeypatch.setattr("time.sleep", lambda _: None)

        from src.launcher import _wait_for_window_count
        assert _wait_for_window_count("C:\\chrome.exe", 2, timeout_seconds=5, poll_ms=50) is True

    def test_wait_for_window_count_false_on_timeout(self, monkeypatch):
        """창 수 부족 상태에서 타임아웃 → False."""
        monkeypatch.setattr("src.launcher.list_current_windows", lambda: [])
        monkeypatch.setattr("time.sleep", lambda _: None)

        tick = {"t": 0.0}
        def fake_monotonic():
            val = tick["t"]
            tick["t"] += 0.6
            return val
        monkeypatch.setattr("time.monotonic", fake_monotonic)

        from src.launcher import _wait_for_window_count
        assert _wait_for_window_count("C:\\chrome.exe", 1, timeout_seconds=1.0, poll_ms=500) is False
