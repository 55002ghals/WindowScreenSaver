"""Tests for restore.py matching and placement logic."""
import sys
import types
import pytest


@pytest.fixture(autouse=True)
def mock_win32(monkeypatch):
    """Create mock win32 modules so tests run without pywin32 installed."""
    win32gui = types.ModuleType("win32gui")
    win32con = types.ModuleType("win32con")

    win32con.SW_SHOWNORMAL = 1
    win32con.SW_SHOWMINIMIZED = 2
    win32con.SW_SHOWMAXIMIZED = 3

    win32gui.SetWindowPos = lambda *a: None
    win32gui.GetWindowPlacement = lambda *a: None  # kept for minimized/maximized state tests
    win32gui.GetWindowRect = lambda *a: (0, 0, 100, 100)  # default: wrong position → verify fails

    sys.modules["win32gui"] = win32gui
    sys.modules["win32con"] = win32con
    yield
    for mod in ["win32gui", "win32con"]:
        sys.modules.pop(mod, None)
    sys.modules.pop("src.restore", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _saved(exe_path="C:\\app.exe", title_pattern="", class_name="AppClass",
           title_snapshot="App Window"):
    return {
        "exe_path": exe_path,
        "title_pattern": title_pattern,
        "class_name": class_name,
        "title_snapshot": title_snapshot,
        "placement": {"state": "normal", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]},
        "z_order": 0,
    }


def _running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="App Window", class_name="AppClass"):
    return {
        "hwnd": hwnd,
        "exe_path": exe_path,
        "title_snapshot": title_snapshot,
        "class_name": class_name,
    }


# ---------------------------------------------------------------------------
# score_window tests
# ---------------------------------------------------------------------------

def test_match_by_exe_only():
    from src.restore import score_window
    saved = _saved(exe_path="C:\\app.exe", title_pattern="", class_name="OtherClass")
    running = _running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="Different Window", class_name="AppClass")
    # exe matches (+10), no title pattern, title_snapshot differs, class doesn't match
    assert score_window(saved, running, set()) == 10


def test_match_by_exe_and_title():
    from src.restore import score_window
    # saved snapshot differs from running → only pattern bonus fires (not snapshot bonus)
    saved = _saved(exe_path="C:\\app.exe", title_pattern="App.*", class_name="OtherClass",
                   title_snapshot="Old Title")
    running = _running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="App Window", class_name="AppClass")
    # exe (+10) + pattern (+5) = 15
    assert score_window(saved, running, set()) == 15


def test_match_by_exe_title_class():
    from src.restore import score_window
    # saved snapshot differs from running → pattern + class only
    saved = _saved(exe_path="C:\\app.exe", title_pattern="App.*", class_name="AppClass",
                   title_snapshot="Old Title")
    running = _running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="App Window", class_name="AppClass")
    # exe (+10) + pattern (+5) + class (+3) = 18
    assert score_window(saved, running, set()) == 18


def test_no_match_score_zero():
    from src.restore import score_window
    saved = _saved(exe_path="C:\\notepad.exe", title_pattern="Notepad", class_name="Notepad")
    running = _running(hwnd=1, exe_path="C:\\chrome.exe", title_snapshot="Google Chrome", class_name="Chrome_WidgetWin_1")
    # nothing matches, score = 0
    assert score_window(saved, running, set()) == 0


def test_duplicate_prevention():
    from src.restore import score_window
    saved = _saved(exe_path="C:\\app.exe")
    running = _running(hwnd=42, exe_path="C:\\app.exe")
    already_assigned = {42}
    assert score_window(saved, running, already_assigned) == -100


def test_match_ambiguous_prefers_highest_score():
    from src.restore import match_windows
    saved = [_saved(exe_path="C:\\app.exe", title_pattern="App.*", class_name="AppClass")]
    # running1 matches exe+title+class (score=18), running2 matches exe only (score=10)
    running1 = _running(hwnd=10, exe_path="C:\\app.exe", title_snapshot="App Window", class_name="AppClass")
    running2 = _running(hwnd=20, exe_path="C:\\app.exe", title_snapshot="Other Title", class_name="OtherClass")
    results = match_windows(saved, [running1, running2])
    assert len(results) == 1
    matched_hwnd = results[0][1]["hwnd"]
    assert matched_hwnd == 10  # higher score wins


def test_empty_title_pattern_skips_title_scoring():
    from src.restore import score_window
    saved = _saved(exe_path="C:\\app.exe", title_pattern="", class_name="OtherClass",
                   title_snapshot="App Window")
    running = _running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="Anything Goes Here")
    # title_pattern is "" and title_snapshot differs, so no title score; exe only = 10
    assert score_window(saved, running, set()) == 10


# ---------------------------------------------------------------------------
# match_windows tests
# ---------------------------------------------------------------------------

def test_match_returns_none_when_no_candidate():
    from src.restore import match_windows
    # exe, class, title_snapshot all differ — nothing matches, score stays 0
    saved = [_saved(exe_path="C:\\missing.exe", class_name="MissingClass",
                    title_snapshot="Missing App")]
    running = [_running(hwnd=1, exe_path="C:\\other.exe", class_name="OtherClass",
                        title_snapshot="Other App")]
    results = match_windows(saved, running)
    assert len(results) == 1
    assert results[0][1] is None


def test_duplicate_prevention_second_gets_no_match():
    from src.restore import match_windows
    # Two saved windows want the same running window — only one should be matched
    saved1 = _saved(exe_path="C:\\app.exe", title_pattern="App.*", class_name="AppClass")
    saved2 = _saved(exe_path="C:\\app.exe", title_pattern="App.*", class_name="AppClass")
    running = [_running(hwnd=1, exe_path="C:\\app.exe", title_snapshot="App Window", class_name="AppClass")]
    results = match_windows([saved1, saved2], running)
    matched = [r for r in results if r[1] is not None]
    unmatched = [r for r in results if r[1] is None]
    assert len(matched) == 1      # exactly one saved gets matched
    assert len(unmatched) == 1    # the other gets nothing (duplicate prevention)


# ---------------------------------------------------------------------------
# restore_placement tests
# ---------------------------------------------------------------------------

def test_restore_placement_normal(monkeypatch):
    import win32gui, win32con
    calls = {}

    def mock_set_placement(hwnd, placement_tuple):
        calls["hwnd"] = hwnd
        calls["placement"] = placement_tuple

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = mock_set_placement
    # 검증은 GetWindowRect 사용: nr에 맞는 LTRB 반환
    win32gui.GetWindowRect = lambda hwnd: (10, 20, 810, 620)

    from src.restore import restore_placement
    placement = {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]}
    result = restore_placement(100, placement)

    assert result is True
    assert calls["hwnd"] == 100
    assert calls["placement"][1] == win32con.SW_SHOWNORMAL
    assert calls["placement"][4] == (10, 20, 810, 620)  # XYWH converted back to LTRB


def test_restore_placement_maximized(monkeypatch):
    import win32gui, win32con
    calls = {}

    def mock_set_placement(hwnd, placement_tuple):
        calls["placement"] = placement_tuple

    win32gui.SetWindowPlacement = mock_set_placement

    from src.restore import restore_placement
    placement = {"state": "maximized", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]}
    result = restore_placement(200, placement)

    assert result is True
    assert calls["placement"][1] == win32con.SW_SHOWMAXIMIZED


def test_restore_placement_minimized(monkeypatch):
    import win32gui, win32con
    calls = {}

    def mock_set_placement(hwnd, placement_tuple):
        calls["placement"] = placement_tuple

    win32gui.SetWindowPlacement = mock_set_placement

    from src.restore import restore_placement
    placement = {"state": "minimized", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]}
    result = restore_placement(300, placement)

    assert result is True
    assert calls["placement"][1] == win32con.SW_SHOWMINIMIZED


def test_restore_placement_returns_false_on_exception(monkeypatch):
    import win32gui

    def mock_set_placement(hwnd, placement_tuple):
        raise OSError("access denied")

    win32gui.SetWindowPlacement = mock_set_placement

    from src.restore import restore_placement
    placement = {"state": "normal", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]}
    result = restore_placement(999, placement)
    assert result is False


# ---------------------------------------------------------------------------
# score_window: title_snapshot exact match bonus
# ---------------------------------------------------------------------------

def test_exact_title_snapshot_match_scores_5_when_no_pattern():
    from src.restore import score_window
    saved  = _saved(exe_path="C:\\app.exe", title_snapshot="My Window", title_pattern="")
    running = _running(exe_path="C:\\app.exe", title_snapshot="My Window", class_name="OtherClass")
    assert score_window(saved, running, set()) == 15  # exe(10) + snapshot_exact(5)


def test_no_bonus_when_title_snapshot_differs():
    from src.restore import score_window
    saved  = _saved(exe_path="C:\\app.exe", title_snapshot="Window A", title_pattern="")
    running = _running(exe_path="C:\\app.exe", title_snapshot="Window B", class_name="OtherClass")
    assert score_window(saved, running, set()) == 10  # exe(10) only


def test_pattern_and_snapshot_bonuses_stack():
    """pattern 매칭 AND snapshot 완전 일치 시 두 보너스가 모두 적용돼야 한다."""
    from src.restore import score_window
    saved  = _saved(exe_path="C:\\app.exe", title_snapshot="Window A", title_pattern="Window")
    running = _running(exe_path="C:\\app.exe", title_snapshot="Window A", class_name="OtherClass")
    assert score_window(saved, running, set()) == 20  # exe(10) + pattern(5) + snapshot(5)


def test_two_same_exe_windows_match_by_title():
    from src.restore import match_windows
    saved_a = _saved(exe_path="C:\\app.exe", title_snapshot="Doc A")
    saved_b = _saved(exe_path="C:\\app.exe", title_snapshot="Doc B")
    running_a = _running(exe_path="C:\\app.exe", title_snapshot="Doc A", hwnd=1)
    running_b = _running(exe_path="C:\\app.exe", title_snapshot="Doc B", hwnd=2)
    results = match_windows([saved_a, saved_b], [running_a, running_b])
    matched_hwnds = {r["hwnd"] for _, r in results if r}
    assert matched_hwnds == {1, 2}
    assert results[0][1]["hwnd"] == 1
    assert results[1][1]["hwnd"] == 2


def test_chrome_windows_disambiguated_when_running_order_reversed():
    """같은 title_pattern을 가진 Chrome 창 2개가 running 순서 무관하게 정확히 매칭돼야 한다."""
    from src.restore import match_windows
    saved_gmail = _saved(exe_path="C:\\chrome.exe",
                         title_snapshot="Gmail - Google Chrome",
                         title_pattern="Google\\ Chrome$")
    saved_yt = _saved(exe_path="C:\\chrome.exe",
                      title_snapshot="YouTube - Google Chrome",
                      title_pattern="Google\\ Chrome$")
    # running 순서가 저장 순서와 반대
    running_yt   = _running(exe_path="C:\\chrome.exe",
                            title_snapshot="YouTube - Google Chrome", hwnd=2)
    running_gmail = _running(exe_path="C:\\chrome.exe",
                             title_snapshot="Gmail - Google Chrome", hwnd=1)

    results = match_windows([saved_gmail, saved_yt], [running_yt, running_gmail])
    assert results[0][1]["hwnd"] == 1  # saved_gmail → running_gmail
    assert results[1][1]["hwnd"] == 2  # saved_yt   → running_yt


# ---------------------------------------------------------------------------
# restore_placement: SetWindowPos follow-up call
# ---------------------------------------------------------------------------

def test_restore_placement_normal_also_calls_set_window_pos(monkeypatch):
    from unittest.mock import MagicMock
    import win32gui, win32con
    nr = [100, 200, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock(return_value=True)
    # 검증: GetWindowRect가 nr에 맞는 LTRB 반환
    win32gui.GetWindowRect = MagicMock(return_value=(100, 200, 900, 800))

    from src.restore import restore_placement
    placement = {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]}
    result = restore_placement(0x1234, placement)

    assert result is True
    win32gui.SetWindowPos.assert_called_once()
    args = win32gui.SetWindowPos.call_args[0]
    assert args[2] == 100  # x
    assert args[3] == 200  # y
    assert args[4] == 800  # w
    assert args[5] == 600  # h


def test_restore_placement_maximized_skips_set_window_pos(monkeypatch):
    from unittest.mock import MagicMock
    import win32gui
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()

    from src.restore import restore_placement
    placement = {"state": "maximized", "normal_rect": [0, 0, 800, 600],
                 "min_pos": [-1, -1], "max_pos": [-1, -1]}
    restore_placement(0x1234, placement)
    win32gui.SetWindowPos.assert_not_called()


# ---------------------------------------------------------------------------
# _rects_close (UT-3a ~ UT-3f)
# ---------------------------------------------------------------------------

def test_ut3a_exact_match():
    from src.restore import _rects_close
    assert _rects_close([100, 200, 800, 600], [100, 200, 800, 600], tol=0) is True


def test_ut3b_at_tolerance_boundary():
    from src.restore import _rects_close
    assert _rects_close([100, 200, 800, 600], [110, 210, 810, 610], tol=10) is True


def test_ut3c_one_element_exceeds_tol():
    from src.restore import _rects_close
    assert _rects_close([100, 200, 800, 600], [111, 200, 800, 600], tol=10) is False


def test_ut3d_negative_coords():
    from src.restore import _rects_close
    assert _rects_close([-1920, 0, 800, 600], [-1915, 5, 795, 595], tol=10) is True
    assert _rects_close([-1920, 0, 800, 600], [-1905, 0, 800, 600], tol=10) is False


def test_ut3e_list_shorter_than_4():
    from src.restore import _rects_close
    assert _rects_close([100, 200, 800], [100, 200, 800, 600], tol=10) is False


def test_ut3f_4k_coords():
    from src.restore import _rects_close
    assert _rects_close([3840, 2160, 3840, 2160], [3842, 2162, 3838, 2158], tol=5) is True


# ---------------------------------------------------------------------------
# restore_placement retries (UT-1, UT-2, UT-5, UT-6, UT-7, UT-8, UT-9, UT-10, UT-11)
# ---------------------------------------------------------------------------

def test_ut1_second_attempt_succeeds():
    """1차 검증 실패, 2차 성공 → True, SetWindowPlacement 2회 호출."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]
    # GetWindowRect: 1차=틀린 위치, 2차=맞는 위치
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(side_effect=[
        (0, 0, 100, 100),          # 1st attempt: wrong → fail
        (10, 20, 810, 620),        # 2nd attempt: correct → succeed
    ])

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is True
    assert win32gui.SetWindowPlacement.call_count == 2


def test_ut2_all_retries_exhausted():
    """retries=3 모두 실패 → False, SetWindowPlacement 3회 호출."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(0, 0, 100, 100))  # always wrong

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is False
    assert win32gui.SetWindowPlacement.call_count == 3


def test_ut5_retries_1_fails_immediately():
    """retries=1: 단 한 번 시도 후 실패 → False, 1회만 호출."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(0, 0, 100, 100))  # always wrong

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=1, retry_delay_ms=0,
    )

    assert result is False
    assert win32gui.SetWindowPlacement.call_count == 1


def test_ut6_first_attempt_succeeds_no_retry():
    """첫 시도에서 즉시 성공 → True, SetWindowPlacement 1회만 호출."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))  # correct

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is True
    assert win32gui.SetWindowPlacement.call_count == 1


def test_ut7_get_window_rect_oserror_no_crash():
    """GetWindowRect OSError → 예외 미전파, False 반환."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(side_effect=OSError("access denied"))

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is False


def test_ut8_get_window_rect_always_wrong_retries_exhausted():
    """GetWindowRect가 항상 틀린 위치 반환 → retries 후 False, SetWindowPlacement retries회 호출."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [10, 20, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(0, 0, 100, 100))  # always wrong

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is False
    assert win32gui.SetWindowPlacement.call_count == 3


def test_ut9_maximized_no_verification_calls():
    """state=maximized → GetWindowRect/GetWindowPlacement 미호출, True 반환."""
    from unittest.mock import MagicMock
    import win32gui

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowPlacement = MagicMock()
    win32gui.GetWindowRect = MagicMock()

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "maximized", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]},
    )

    assert result is True
    win32gui.GetWindowPlacement.assert_not_called()
    win32gui.GetWindowRect.assert_not_called()


def test_ut10_minimized_no_verification_calls():
    """state=minimized → GetWindowRect/GetWindowPlacement 미호출, True 반환."""
    from unittest.mock import MagicMock
    import win32gui

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowPlacement = MagicMock()
    win32gui.GetWindowRect = MagicMock()

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "minimized", "normal_rect": [0, 0, 800, 600], "min_pos": [-1, -1], "max_pos": [-1, -1]},
    )

    assert result is True
    win32gui.GetWindowPlacement.assert_not_called()
    win32gui.GetWindowRect.assert_not_called()


def test_ut11_negative_coord_normal_rect():
    """음수 x 좌표(멀티모니터 왼쪽 배치) → 정상 처리, True."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [-1920, 100, 800, 600]

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    # GetWindowRect: nr에 맞는 LTRB 반환 (-1920,100,-1120,700)
    win32gui.GetWindowRect = MagicMock(return_value=(-1920, 100, -1120, 700))

    from src.restore import restore_placement
    result = restore_placement(
        100,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
        retries=3, retry_delay_ms=0,
    )

    assert result is True
    args = win32gui.SetWindowPos.call_args[0]
    assert args[2] == -1920  # x


# ---------------------------------------------------------------------------
# restore_layout stabilize_ms (UT-4, UT-13, UT-14, UT-15)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_layout_deps(monkeypatch):
    """restore_layout 호출에 필요한 sys.modules 의존성을 최소한으로 모킹."""
    import types
    from unittest.mock import MagicMock
    from enum import Enum

    class MatchResult(Enum):
        FULL_MATCH = "full_match"
        PRIMARY_ONLY = "primary_only"
        NO_MATCH = "no_match"

    monitors_mod = types.ModuleType("src.monitors")
    monitors_mod.MatchResult = MatchResult
    monitors_mod.compare_monitors = lambda *a, **kw: MatchResult.FULL_MATCH
    monitors_mod.filter_to_primary = lambda windows, *a: windows
    monitors_mod.clamp_rect_to_monitor = lambda r, m: r

    launcher_mod = types.ModuleType("src.launcher")
    launcher_mod.ensure_apps_running = MagicMock()

    capture_mod = types.ModuleType("src.capture")
    capture_mod.list_current_windows = MagicMock(return_value=[])

    monkeypatch.setitem(sys.modules, "src.monitors", monitors_mod)
    monkeypatch.setitem(sys.modules, "src.launcher", launcher_mod)
    monkeypatch.setitem(sys.modules, "src.capture", capture_mod)


def test_ut4_stabilize_ms_zero_no_sleep(mock_layout_deps):
    """stabilize_ms=0 → time.sleep 미호출."""
    from unittest.mock import patch

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []}, stabilize_ms=0)

    mock_sleep.assert_not_called()


def test_ut13_stabilize_ms_500_sleeps_half_second(mock_layout_deps):
    """stabilize_ms=500 → time.sleep(0.5) 호출."""
    from unittest.mock import patch

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []}, stabilize_ms=500)

    mock_sleep.assert_called_once_with(0.5)


def test_ut14_running_windows_passed_no_sleep(mock_layout_deps):
    """running_windows를 외부에서 전달하면 stabilize_ms 무시, sleep 미호출."""
    from unittest.mock import patch

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []},
                       running_windows=[], stabilize_ms=1500)

    mock_sleep.assert_not_called()


def test_ut15_stabilize_ms_default_sleeps_1500ms(mock_layout_deps):
    """stabilize_ms 생략(기본값 1500) → time.sleep(1.5) 호출."""
    from unittest.mock import patch

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []})

    mock_sleep.assert_called_once_with(1.5)


# ---------------------------------------------------------------------------
# restore_layout post_settle_ms (UT-16, UT-17, UT-18)
# Chrome/Electron 앱이 WM_WINDOWPOSCHANGED로 창을 비동기 복원하는 문제 대응.
# ---------------------------------------------------------------------------

def _post_settle_env(monkeypatch, sys_modules):
    """post_settle 테스트용 src.monitors 모킹."""
    import types
    from enum import Enum

    class FakeMatchResult(Enum):
        MATCH = "MATCH"
        PRIMARY_ONLY = "PRIMARY_ONLY"
        NO_MATCH = "NO_MATCH"

    monitors_mod = types.ModuleType("src.monitors")
    monitors_mod.MatchResult = FakeMatchResult
    monitors_mod.compare_monitors = lambda *a, **kw: FakeMatchResult.MATCH
    monitors_mod.filter_to_primary = lambda w, *a: w
    monitors_mod.clamp_rect_to_monitor = lambda r, m: r
    monkeypatch.setitem(sys_modules, "src.monitors", monitors_mod)
    sys_modules.pop("src.restore", None)


def _make_normal_layout(nr):
    return {
        "name": "t",
        "windows": [{
            "exe_path": "C:\\app.exe",
            "title_snapshot": "App",
            "title_pattern": "",
            "class_name": "C",
            "placement": {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
            "z_order": 0,
        }],
        "monitors": [],
    }


def _make_running(nr=None):
    return [{"hwnd": 1, "exe_path": "C:\\app.exe", "title_snapshot": "App", "class_name": "C"}]


def test_ut16_post_settle_ms_zero_no_reapply(monkeypatch):
    """post_settle_ms=0 → sleep 미호출, SetWindowPlacement 1회만(재적용 없음)."""
    import sys
    from unittest.mock import MagicMock, patch
    import win32gui, win32con

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))

    _post_settle_env(monkeypatch, sys.modules)

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout(_make_normal_layout(nr), running_windows=_make_running(), post_settle_ms=0)

    mock_sleep.assert_not_called()
    assert win32gui.SetWindowPlacement.call_count == 1


def test_ut17_post_settle_ms_positive_sleeps_and_reapplies(monkeypatch):
    """post_settle_ms > 0, 배치 성공 → sleep(post_settle/1000) 호출, SetWindowPlacement 2회."""
    import sys
    from unittest.mock import MagicMock, patch
    import win32gui, win32con

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))

    _post_settle_env(monkeypatch, sys.modules)

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        result = restore_layout(_make_normal_layout(nr), running_windows=_make_running(), post_settle_ms=200)

    mock_sleep.assert_called_once_with(0.2)
    assert win32gui.SetWindowPlacement.call_count == 2  # 초기 배치 + 재적용
    assert result["restored"] == 1


def test_ut18_post_settle_runs_even_when_first_pass_failed(monkeypatch):
    """초기 배치 실패(False)여도 매칭된 창이 있으면 post_settle sleep 및 재시도 실행.
    Chrome처럼 시작 시 즉시 배치를 거부하지만 안정화 후 수락하는 케이스 지원."""
    import sys
    from unittest.mock import patch, MagicMock

    _post_settle_env(monkeypatch, sys.modules)

    nr = [10, 20, 800, 600]

    placement_calls = []
    def fake_placement(hwnd, placement):
        placement_calls.append(hwnd)
        return False  # 항상 실패

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        with patch("src.restore.restore_placement", side_effect=fake_placement):
            result = restore_layout(_make_normal_layout(nr), running_windows=_make_running(), post_settle_ms=500)

    # 매칭된 창이 있으므로 sleep 호출됨
    mock_sleep.assert_called_once_with(0.5)
    # 초기 + 재시도 = 2회 호출
    assert len(placement_calls) == 2
    assert result["failed"] == 1
    assert result["restored"] == 0


def test_ut18b_post_settle_skipped_when_no_matched_windows(monkeypatch):
    """매칭된 창이 아예 없으면(all running=None) post_settle sleep 미호출."""
    import sys
    from unittest.mock import patch

    _post_settle_env(monkeypatch, sys.modules)

    layout = {
        "name": "t",
        "windows": [{"exe_path": "C:\\missing.exe", "title_snapshot": "X", "title_pattern": "",
                     "class_name": "C", "placement": {"state": "normal", "normal_rect": [0, 0, 800, 600],
                     "min_pos": [-1, -1], "max_pos": [-1, -1]}, "z_order": 0}],
        "monitors": [],
    }
    # exe/class/title 모두 다름 → score=0 → 매칭 없음(running=None)
    running = [{"hwnd": 1, "exe_path": "C:\\other.exe", "title_snapshot": "Other", "class_name": "OtherClass"}]

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        result = restore_layout(layout, running_windows=running, post_settle_ms=500)

    mock_sleep.assert_not_called()
    assert result["failed"] == 1


# ---------------------------------------------------------------------------
# restore_layout post_launch_settle_ms (UT-R1, UT-R2, UT-R3)
# ---------------------------------------------------------------------------

def test_ut19_post_launch_settle_ms_zero_no_second_reapply(monkeypatch):
    """post_launch_settle_ms=0(기본값) → launched_count>0이어도 2차 sleep/재적용 없음."""
    import sys
    from unittest.mock import MagicMock, patch
    import win32gui, win32con

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))

    _post_settle_env(monkeypatch, sys.modules)

    import types
    launcher_mod = types.ModuleType("src.launcher")
    launcher_mod.ensure_apps_running = MagicMock(return_value=1)
    monkeypatch.setitem(sys.modules, "src.launcher", launcher_mod)
    capture_mod = types.ModuleType("src.capture")
    capture_mod.list_current_windows = MagicMock(return_value=_make_running())
    monkeypatch.setitem(sys.modules, "src.capture", capture_mod)

    with patch("time.sleep") as mock_sleep:
        from src.restore import restore_layout
        restore_layout(
            _make_normal_layout(nr),
            stabilize_ms=0,
            post_settle_ms=0,
            post_launch_settle_ms=0,
        )

    mock_sleep.assert_not_called()
    assert win32gui.SetWindowPlacement.call_count == 1


def test_ut20_post_launch_settle_ms_fires_when_apps_launched(monkeypatch):
    """post_launch_settle_ms=3000, launched_count=1 → sleep(3.0) 추가, SetWindowPlacement 3회."""
    import sys
    from unittest.mock import MagicMock, patch
    import win32gui, win32con

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))

    _post_settle_env(monkeypatch, sys.modules)

    import types
    launcher_mod = types.ModuleType("src.launcher")
    launcher_mod.ensure_apps_running = MagicMock(return_value=1)
    monkeypatch.setitem(sys.modules, "src.launcher", launcher_mod)
    capture_mod = types.ModuleType("src.capture")
    capture_mod.list_current_windows = MagicMock(return_value=_make_running())
    monkeypatch.setitem(sys.modules, "src.capture", capture_mod)

    sleep_calls = []
    with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        from src.restore import restore_layout
        restore_layout(
            _make_normal_layout(nr),
            post_settle_ms=2000,
            post_launch_settle_ms=3000,
        )

    assert 2.0 in sleep_calls
    assert 3.0 in sleep_calls
    assert win32gui.SetWindowPlacement.call_count == 3


def test_ut21_post_launch_settle_skipped_when_no_apps_launched(monkeypatch):
    """post_launch_settle_ms=3000이지만 launched_count=0 → 2차 재적용 없음."""
    import sys
    from unittest.mock import MagicMock, patch
    import win32gui, win32con

    nr = [10, 20, 800, 600]
    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = MagicMock()
    win32gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))

    _post_settle_env(monkeypatch, sys.modules)

    import types
    launcher_mod = types.ModuleType("src.launcher")
    launcher_mod.ensure_apps_running = MagicMock(return_value=0)
    monkeypatch.setitem(sys.modules, "src.launcher", launcher_mod)
    capture_mod = types.ModuleType("src.capture")
    capture_mod.list_current_windows = MagicMock(return_value=_make_running())
    monkeypatch.setitem(sys.modules, "src.capture", capture_mod)

    sleep_calls = []
    with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        from src.restore import restore_layout
        restore_layout(
            _make_normal_layout(nr),
            post_settle_ms=2000,
            post_launch_settle_ms=3000,
        )

    assert 3.0 not in sleep_calls
    assert win32gui.SetWindowPlacement.call_count == 2


# ---------------------------------------------------------------------------
# UT-A4: SWP_NOSENDCHANGING 플래그 검증 (Task-8 M2)
# ---------------------------------------------------------------------------

def test_ut_a4_restore_placement_includes_swp_nosendchanging(monkeypatch):
    """SetWindowPos 호출 시 SWP_NOSENDCHANGING(0x0400) 플래그가 포함되는지 검증."""
    from unittest.mock import MagicMock
    import win32gui

    nr = [100, 100, 800, 600]
    swp_calls = []

    def capture_flags(hwnd, ins, x, y, cx, cy, flags):
        swp_calls.append(flags)

    win32gui.SetWindowPlacement = MagicMock()
    win32gui.SetWindowPos = capture_flags
    win32gui.GetWindowRect = MagicMock(return_value=(100, 100, 900, 700))

    from src.restore import restore_placement
    result = restore_placement(
        1,
        {"state": "normal", "normal_rect": nr, "min_pos": [-1, -1], "max_pos": [-1, -1]},
    )

    assert result is True
    assert swp_calls, "SetWindowPos가 호출되지 않음"
    assert swp_calls[0] & 0x0400, "SWP_NOSENDCHANGING(0x0400) 플래그 없음"


# ---------------------------------------------------------------------------
# TestMultiWindowMatching (UT-T10-M1-1 ~ UT-T10-M1-3)
# ---------------------------------------------------------------------------

class TestMultiWindowMatching:
    def test_same_app_two_saved_one_running_matches_higher_score(self):
        """
        Chrome 2개 저장, 1개 running → title_snapshot이 일치하는 saved 창에 매칭.
        title_snapshot 불일치 saved 창은 no candidate.
        """
        saved = [
            _saved(exe_path="C:\\chrome.exe", title_snapshot="CertiNavigator - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
            _saved(exe_path="C:\\chrome.exe", title_snapshot="새 탭 - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
        ]
        running = [
            _running(hwnd=0x1, exe_path="C:\\chrome.exe",
                     title_snapshot="CertiNavigator - Chrome", class_name="Chrome_WidgetWin_1"),
        ]
        from src.restore import match_windows
        results = match_windows(saved, running)
        assert results[0][1] is not None
        assert results[0][0]["title_snapshot"] == "CertiNavigator - Chrome"
        assert results[0][1]["hwnd"] == 0x1
        assert results[1][1] is None   # 새 탭 → no candidate

    def test_same_app_two_saved_two_running_correct_cross_assignment(self):
        """
        Chrome 2개 저장, 2개 running → title_snapshot 기반으로 각자 올바른 창에 매칭.
        (running 순서와 관계없이)
        """
        saved = [
            _saved(exe_path="C:\\chrome.exe", title_snapshot="CertiNavigator - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
            _saved(exe_path="C:\\chrome.exe", title_snapshot="새 탭 - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
        ]
        running = [
            _running(hwnd=0x1, exe_path="C:\\chrome.exe",
                     title_snapshot="새 탭 - Chrome", class_name="Chrome_WidgetWin_1"),
            _running(hwnd=0x2, exe_path="C:\\chrome.exe",
                     title_snapshot="CertiNavigator - Chrome", class_name="Chrome_WidgetWin_1"),
        ]
        from src.restore import match_windows
        results = match_windows(saved, running)
        matched = {r[0]["title_snapshot"]: r[1]["hwnd"] for r in results if r[1]}
        assert matched["CertiNavigator - Chrome"] == 0x2
        assert matched["새 탭 - Chrome"] == 0x1

    def test_optimal_matching_independent_of_z_order(self):
        """
        z_order=7인 '새 탭' saved 창이 먼저 처리되더라도 score가 낮아서
        running Chrome-X를 선점하지 않음 (이전 그리디 버그 회귀 방지).
        """
        saved = [
            _saved(exe_path="C:\\chrome.exe", title_snapshot="CertiNavigator - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
            _saved(exe_path="C:\\chrome.exe", title_snapshot="새 탭 - Chrome",
                   title_pattern="Chrome$", class_name="Chrome_WidgetWin_1"),
        ]
        saved[0]["z_order"] = 3
        saved[1]["z_order"] = 7
        sorted_saved = sorted(saved, key=lambda w: w.get("z_order", 0), reverse=True)

        running = [
            _running(hwnd=0x1, exe_path="C:\\chrome.exe",
                     title_snapshot="CertiNavigator - Chrome", class_name="Chrome_WidgetWin_1"),
        ]
        from src.restore import match_windows
        results = match_windows(sorted_saved, running)
        matched_titles = {r[0]["title_snapshot"]: r[1] for r in results}
        assert matched_titles["CertiNavigator - Chrome"] is not None
        assert matched_titles["CertiNavigator - Chrome"]["hwnd"] == 0x1
        assert matched_titles["새 탭 - Chrome"] is None


# ---------------------------------------------------------------------------
# no_launch 파라미터 (UT-NL1 ~ UT-NL3)
# ---------------------------------------------------------------------------

def test_nl1_no_launch_true_skips_ensure_apps_running(mock_layout_deps):
    """UT-NL1: no_launch=True → ensure_apps_running 미호출."""
    import sys
    from unittest.mock import patch
    ensure_mock = sys.modules["src.launcher"].ensure_apps_running

    with patch("time.sleep"):
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []}, no_launch=True)

    ensure_mock.assert_not_called()


def test_nl2_no_launch_false_calls_ensure_apps_running(mock_layout_deps):
    """UT-NL2: no_launch=False(기본) → ensure_apps_running 1회 호출."""
    import sys
    from unittest.mock import patch
    ensure_mock = sys.modules["src.launcher"].ensure_apps_running

    with patch("time.sleep"):
        from src.restore import restore_layout
        restore_layout({"name": "t", "windows": [], "monitors": []}, no_launch=False)

    ensure_mock.assert_called_once()


def test_nl3_no_launch_true_rescans_windows_twice(mock_layout_deps):
    """UT-NL3: no_launch=True여도 running_windows=None이면 list_current_windows 2회 스캔."""
    import sys
    scan_mock = sys.modules["src.capture"].list_current_windows

    from src.restore import restore_layout
    restore_layout({"name": "t", "windows": [], "monitors": []}, no_launch=True)

    assert scan_mock.call_count == 2
