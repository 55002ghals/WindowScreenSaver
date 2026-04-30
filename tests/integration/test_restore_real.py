"""Integration tests — real Windows API, no mocks.
Run with: pytest -m integration tests/integration/
These tests require a desktop environment with pywin32 installed.
"""
import logging
import subprocess
import time

import pytest

from src.capture import list_current_windows
from src.restore import restore_layout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_notepad(w: dict) -> bool:
    """True for any Notepad window (Win32 or UWP)."""
    return "notepad.exe" in w.get("exe_path", "").lower()


def _wait_for_exe_window(exe_name: str, timeout: float = 15.0,
                         exclude_hwnds: set = None) -> dict | None:
    """Poll until a window from exe_name appears; return window dict or None.

    Pass exclude_hwnds to skip pre-existing windows (e.g. unkillable UWP Notepad).
    """
    deadline = time.monotonic() + timeout
    exe_lower = exe_name.lower()
    _exclude = exclude_hwnds or set()
    while time.monotonic() < deadline:
        for w in list_current_windows():
            if (exe_lower in w.get("exe_path", "").lower()
                    and w["hwnd"] not in _exclude):
                return w
        time.sleep(0.5)
    return None


def _kill_all(exe_name: str) -> None:
    subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True)
    time.sleep(1.5)


def _rects_close(r1: list, r2: list, tol: int = 20) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(r1, r2))


def chrome_installed() -> bool:
    import os
    return os.path.exists(
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )


# ---------------------------------------------------------------------------
# ITC1: Notepad 창 저장 → 위치 이동 → 복구 → 위치 검증
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc1_notepad_restore_position():
    """Save notepad position, move it, restore and verify position matches."""
    import win32gui

    EXPLICIT_POS = (200, 100, 700, 500)
    MOVED_POS    = (500, 350, 700, 500)

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe")
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        # UWP Notepad startup state restoration finishes within ~3 s.
        # Wait 4 s so it cannot fight back against our explicit SetWindowPos.
        time.sleep(4.0)

        win32gui.SetWindowPos(hwnd, None, EXPLICIT_POS[0], EXPLICIT_POS[1],
                              EXPLICIT_POS[2], EXPLICIT_POS[3], 0x0010 | 0x0004)

        # Wait for UWP fight-back after our move to settle.
        time.sleep(1.5)

        wins = list_current_windows()
        w = next((x for x in wins if x["hwnd"] == hwnd), None)
        assert w is not None, "Notepad window disappeared during settle wait"

        original_rect = w["placement"]["normal_rect"]  # [x, y, w, h]
        layout = {"name": "itc1", "windows": [w], "monitors": []}

        # Move window to a clearly different position
        win32gui.SetWindowPos(hwnd, None, MOVED_POS[0], MOVED_POS[1],
                              MOVED_POS[2], MOVED_POS[3], 0x0010 | 0x0004)

        # Restrict to only our hwnd so pre-existing UWP Notepad windows are not matched.
        running = [x for x in list_current_windows() if x["hwnd"] == hwnd]
        result = restore_layout(layout, running_windows=running)
        assert result["restored"] == 1

        # Verify position
        placement = win32gui.GetWindowPlacement(hwnd)
        rc = placement[4]  # LTRB
        actual = [rc[0], rc[1], rc[2] - rc[0], rc[3] - rc[1]]
        assert _rects_close(actual, original_rect), f"Expected ~{original_rect}, got {actual}"
    finally:
        proc.terminate()
        _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC2: Notepad 2개 창 저장 → 복구 → 각각 위치 검증
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc2_two_notepad_windows_restore():
    """Two notepad windows: save, move both, restore, verify each."""
    import win32gui

    # Explicit positions — guaranteed non-overlapping (700 px gap on x-axis).
    EXPLICIT_POS1 = (200, 100, 600, 400)
    EXPLICIT_POS2 = (900, 400, 600, 400)
    MOVED_POS1    = (700, 500, 600, 400)
    MOVED_POS2    = (100, 300, 600, 400)

    _kill_all("notepad.exe")
    pre_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    proc1 = subprocess.Popen(["notepad.exe"])
    w1 = _wait_for_exe_window("notepad.exe", exclude_hwnds=pre_hwnds)
    assert w1 is not None
    hwnd1 = w1["hwnd"]

    proc2 = subprocess.Popen(["notepad.exe"])
    # Wait for second NEW window (not pre-existing, different hwnd from hwnd1).
    deadline = time.monotonic() + 15.0
    w2 = None
    while time.monotonic() < deadline:
        for w in list_current_windows():
            if (_is_notepad(w)
                    and w["hwnd"] != hwnd1
                    and w["hwnd"] not in pre_hwnds):
                w2 = w
                break
        if w2:
            break
        time.sleep(0.5)

    try:
        assert w2 is not None, "Second Notepad window did not appear"
        hwnd2 = w2["hwnd"]

        # UWP Notepad startup state restoration finishes within ~3 s.
        # Wait 4 s so it cannot fight back against our explicit SetWindowPos.
        time.sleep(4.0)

        # Force each window to a known, non-overlapping position.
        win32gui.SetWindowPos(hwnd1, None, EXPLICIT_POS1[0], EXPLICIT_POS1[1],
                              EXPLICIT_POS1[2], EXPLICIT_POS1[3], 0x0010 | 0x0004)
        win32gui.SetWindowPos(hwnd2, None, EXPLICIT_POS2[0], EXPLICIT_POS2[1],
                              EXPLICIT_POS2[2], EXPLICIT_POS2[3], 0x0010 | 0x0004)

        # Wait for UWP fight-back after our move to settle.
        time.sleep(1.5)

        wins = list_current_windows()
        w1 = next((x for x in wins if x["hwnd"] == hwnd1), None)
        w2 = next((x for x in wins if x["hwnd"] == hwnd2), None)
        assert w1 is not None and w2 is not None, "Notepad window disappeared during settle wait"

        layout = {"name": "itc2", "windows": [w1, w2], "monitors": []}
        orig1 = w1["placement"]["normal_rect"]
        orig2 = w2["placement"]["normal_rect"]

        # Move both windows to non-overlapping positions (different from saved).
        win32gui.SetWindowPos(hwnd1, None, MOVED_POS1[0], MOVED_POS1[1],
                              MOVED_POS1[2], MOVED_POS1[3], 0x0010 | 0x0004)
        win32gui.SetWindowPos(hwnd2, None, MOVED_POS2[0], MOVED_POS2[1],
                              MOVED_POS2[2], MOVED_POS2[3], 0x0010 | 0x0004)

        # Filter running_windows to only our two hwnds — pre-existing UWP Notepad windows
        # have identical exe/title scores and would be matched first, leaving hwnd1/hwnd2 unrestored.
        running = [w for w in list_current_windows() if w["hwnd"] in {hwnd1, hwnd2}]
        result = restore_layout(layout, running_windows=running)
        assert result["restored"] == 2

        # Both windows have identical titles so matching is ambiguous.
        # Verify that each hwnd ended up at one of the two original positions
        # (the restore may swap which window gets which saved slot).
        expected_positions = [orig1, orig2]
        for hwnd in [hwnd1, hwnd2]:
            placement = win32gui.GetWindowPlacement(hwnd)
            rc = placement[4]
            actual = [rc[0], rc[1], rc[2] - rc[0], rc[3] - rc[1]]
            matched = any(_rects_close(actual, exp) for exp in expected_positions)
            assert matched, f"hwnd=0x{hwnd:x}: actual {actual} doesn't match either of {expected_positions}"
    finally:
        proc1.terminate()
        proc2.terminate()
        _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC3: Chrome 완전 종료 후 복구 → Chrome 창 존재 확인
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not chrome_installed(), reason="Chrome not installed")
def test_itc3_chrome_killed_and_restored(caplog):
    """Kill Chrome entirely, restore layout, verify Chrome window appears."""
    CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    _kill_all("chrome.exe")
    proc = subprocess.Popen([CHROME_EXE, "--new-window"])
    w = _wait_for_exe_window("chrome.exe", timeout=15)
    assert w is not None, "Chrome window did not appear after launch"

    layout = {"name": "itc3", "windows": [w], "monitors": []}

    # Kill Chrome completely
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(2)

    with caplog.at_level(logging.WARNING, logger="restore"):
        result = restore_layout(layout)

    time.sleep(5)
    windows_after = list_current_windows()
    chrome_windows = [x for x in windows_after if "chrome.exe" in x.get("exe_path", "").lower()]
    assert len(chrome_windows) >= 1, "Chrome window not found after restore"

    chrome_win = chrome_windows[0]
    actual_rect = chrome_win["placement"]["normal_rect"]
    saved_rect  = w["placement"]["normal_rect"]
    # Chrome ignores SetWindowPos for size after a force-kill because it restores its own
    # profile-saved window size on startup.  Only the origin (x, y) is reliably honored.
    assert abs(actual_rect[0] - saved_rect[0]) <= 30 and abs(actual_rect[1] - saved_rect[1]) <= 30, \
        f"ITC3: origin mismatch — saved={saved_rect}, actual={actual_rect}"

    no_candidate_warns = [r for r in caplog.records if "no candidate" in r.message]
    assert no_candidate_warns == [], f"Unexpected 'no candidate' warnings: {no_candidate_warns}"

    _kill_all("chrome.exe")


# ---------------------------------------------------------------------------
# ITC4: Chrome 창만 닫기 (프로세스 유지) → 복구 → Chrome 창 존재 확인
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not chrome_installed(), reason="Chrome not installed")
def test_itc4_chrome_background_only_then_restored(caplog):
    """Core bug scenario: Chrome process alive but no window → restore creates window."""
    import win32gui
    import win32con

    CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    WM_CLOSE = 0x0010

    _kill_all("chrome.exe")
    proc = subprocess.Popen([CHROME_EXE, "--new-window"])
    w = _wait_for_exe_window("chrome.exe", timeout=15)
    assert w is not None, "Chrome window did not appear after launch"

    layout = {"name": "itc4", "windows": [w], "monitors": []}
    hwnd = w["hwnd"]

    # Close just the window (leave background process running)
    win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)
    time.sleep(2)

    # Verify: process still alive, window gone
    import psutil
    chrome_procs = [p for p in psutil.process_iter(["name"])
                    if (p.info.get("name") or "").lower() == "chrome.exe"]
    assert len(chrome_procs) > 0, "Chrome process should still be running"

    visible = [x for x in list_current_windows() if "chrome.exe" in x.get("exe_path", "").lower()]
    # If Chrome auto-recreated a window, skip the "no visible window" check
    if visible:
        pytest.skip("Chrome auto-recreated window; background-only state not achievable in this env")

    with caplog.at_level(logging.WARNING, logger="restore"):
        result = restore_layout(layout)

    time.sleep(5)
    windows_after = list_current_windows()
    chrome_windows = [x for x in windows_after if "chrome.exe" in x.get("exe_path", "").lower()]
    assert len(chrome_windows) >= 1, "Chrome window not found after restore"

    chrome_win = chrome_windows[0]
    actual_rect = chrome_win["placement"]["normal_rect"]
    saved_rect  = w["placement"]["normal_rect"]
    # Chrome은 프로세스 재오픈 시 자신의 profile 저장 크기를 복원함.
    # x,y 원점만 검증 (ITC3와 동일한 이유).
    assert abs(actual_rect[0] - saved_rect[0]) <= 30 and abs(actual_rect[1] - saved_rect[1]) <= 30, \
        f"ITC4: origin mismatch — saved={saved_rect}, actual={actual_rect}"

    no_candidate_warns = [r for r in caplog.records if "no candidate" in r.message]
    assert no_candidate_warns == [], f"Unexpected 'no candidate' warnings: {no_candidate_warns}"

    _kill_all("chrome.exe")


# ---------------------------------------------------------------------------
# ITC5: Notepad 종료 후 복구 → 저장 위치로 복구 (위치 정확도 검증)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc5_notepad_killed_and_restored_position():
    """Kill Notepad, restore layout, verify it comes back at the saved position."""
    import win32gui

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe")
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        target = [200, 150, 700, 500]
        win32gui.SetWindowPos(hwnd, None, target[0], target[1], target[2], target[3],
                              0x0010 | 0x0004)
        time.sleep(0.3)

        wins = list_current_windows()
        notepad_win = next((x for x in wins if _is_notepad(x)
                            and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        captured_rect = notepad_win["placement"]["normal_rect"]

        layout = {"name": "itc5", "windows": [notepad_win], "monitors": []}
    finally:
        proc.terminate()
        _kill_all("notepad.exe")

    # Snapshot surviving Notepad hwnds (UWP may not be fully killable).
    pre_restore_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    result = restore_layout(layout, stabilize_ms=500)
    assert result["restored"] == 1

    wins_after = list_current_windows()
    # Prefer the newly launched window; fall back to any Notepad.
    new_wins = [x for x in wins_after if _is_notepad(x) and x["hwnd"] not in pre_restore_hwnds]
    notepad_wins = new_wins if new_wins else [x for x in wins_after if _is_notepad(x)]
    assert len(notepad_wins) >= 1, "Notepad window not found after restore"

    actual_rect = notepad_wins[0]["placement"]["normal_rect"]
    assert _rects_close(actual_rect, captured_rect, tol=20), \
        f"ITC5: position mismatch — saved={captured_rect}, actual={actual_rect}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC6: Notepad 최대화 상태 종료 후 복구 → 최대화 상태 재현
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc6_notepad_maximized_killed_and_restored():
    """Kill maximized Notepad, restore and verify it comes back maximized."""
    import win32gui
    import win32con

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe")
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.3)

        wins = list_current_windows()
        notepad_win = next((x for x in wins if _is_notepad(x)
                            and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        assert notepad_win["placement"]["state"] == "maximized", "Window should be maximized"

        layout = {"name": "itc6", "windows": [notepad_win], "monitors": []}
    finally:
        proc.terminate()
        _kill_all("notepad.exe")

    # Snapshot surviving Notepad hwnds (UWP may not be fully killable).
    pre_restore_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    result = restore_layout(layout, stabilize_ms=500)
    assert result["restored"] == 1

    wins_after = list_current_windows()
    # Prefer the newly launched window; fall back to any Notepad.
    new_wins = [x for x in wins_after if _is_notepad(x) and x["hwnd"] not in pre_restore_hwnds]
    notepad_wins = new_wins if new_wins else [x for x in wins_after if _is_notepad(x)]
    assert len(notepad_wins) >= 1, "Notepad window not found after restore"

    restored_hwnd = notepad_wins[0]["hwnd"]
    placement = win32gui.GetWindowPlacement(restored_hwnd)
    assert placement[1] == win32con.SW_SHOWMAXIMIZED, \
        f"ITC6: expected maximized (showCmd={win32con.SW_SHOWMAXIMIZED}), got {placement[1]}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC7: Notepad 2창 종료 후 복구 → 각 창이 저장된 위치 중 하나와 일치
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc7_two_notepad_windows_killed_and_restored():
    """Kill two Notepad windows, restore, verify each appears at one of the saved positions."""
    import win32gui

    _kill_all("notepad.exe")  # ensure clean state before starting
    proc1 = subprocess.Popen(["notepad.exe"])
    w1 = _wait_for_exe_window("notepad.exe")
    assert w1 is not None

    proc2 = subprocess.Popen(["notepad.exe"])
    deadline = time.monotonic() + 15.0
    w2 = None
    while time.monotonic() < deadline:
        for w in list_current_windows():
            if _is_notepad(w) and w["hwnd"] != w1["hwnd"]:
                w2 = w
                break
        if w2:
            break
        time.sleep(0.5)

    try:
        assert w2 is not None, "Second Notepad window did not appear"

        pos1 = [100, 100, 600, 400]
        pos2 = [750, 300, 600, 400]
        win32gui.SetWindowPos(w1["hwnd"], None, pos1[0], pos1[1], pos1[2], pos1[3], 0x0010 | 0x0004)
        win32gui.SetWindowPos(w2["hwnd"], None, pos2[0], pos2[1], pos2[2], pos2[3], 0x0010 | 0x0004)
        time.sleep(0.3)

        wins = list_current_windows()
        # Filter to only the two windows we opened to avoid counting pre-existing Notepad windows
        notepad_wins = [x for x in wins
                        if _is_notepad(x)
                        and x["hwnd"] in {w1["hwnd"], w2["hwnd"]}]
        assert len(notepad_wins) == 2, f"Expected exactly 2 tracked Notepad windows, got {len(notepad_wins)}"
        layout = {"name": "itc7", "windows": notepad_wins, "monitors": []}
        expected_positions = [pos1, pos2]
    finally:
        proc1.terminate()
        proc2.terminate()
        _kill_all("notepad.exe")

    result = restore_layout(layout, stabilize_ms=500)
    assert result["restored"] == 2

    # Verify the two saved positions are occupied — regardless of how many Notepad windows
    # exist in the environment (UWP Notepad may not be fully killable by taskkill).
    wins_after = list_current_windows()
    notepad_wins_after = [x for x in wins_after if _is_notepad(x)]

    for exp_pos in expected_positions:
        matched_windows = [w for w in notepad_wins_after
                           if _rects_close(w["placement"]["normal_rect"], exp_pos, tol=20)]
        assert matched_windows, f"ITC7: no window found at expected position {exp_pos}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC8: Notepad 화면 모서리(x=5,y=5) 위치 종료 후 복구
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc8_notepad_corner_position_restored():
    """Kill Notepad at near-corner position (5,5), restore and verify same position."""
    import win32gui

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe")
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        target = [5, 5, 500, 400]
        win32gui.SetWindowPos(hwnd, None, target[0], target[1], target[2], target[3],
                              0x0010 | 0x0004)
        # Wait 2 s for UWP Notepad fight-back to settle so captured_rect reflects
        # the stable position (not a mid-fight-back intermediate coordinate).
        time.sleep(2.0)

        wins = list_current_windows()
        notepad_win = next((x for x in wins if _is_notepad(x)
                            and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        # captured_rect is GetWindowRect-based (actual screen position after fight-back).
        captured_rect = notepad_win["placement"]["normal_rect"]

        layout = {"name": "itc8", "windows": [notepad_win], "monitors": []}
    finally:
        proc.terminate()
        _kill_all("notepad.exe")

    # Snapshot surviving Notepad hwnds (UWP may not be fully killable).
    pre_restore_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    result = restore_layout(layout, stabilize_ms=500)
    assert result["restored"] == 1

    wins_after = list_current_windows()
    # Prefer the newly launched window; fall back to any Notepad.
    new_wins = [x for x in wins_after if _is_notepad(x) and x["hwnd"] not in pre_restore_hwnds]
    notepad_wins = new_wins if new_wins else [x for x in wins_after if _is_notepad(x)]
    assert len(notepad_wins) >= 1, "Notepad window not found after restore"

    actual_rect = notepad_wins[0]["placement"]["normal_rect"]
    # Compare against captured_rect (actual stored position) rather than target,
    # because UWP Notepad may have fought back to a different position.
    assert _rects_close(actual_rect, captured_rect, tol=20), \
        f"ITC8: position mismatch — captured={captured_rect}, actual={actual_rect}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC11: 멀티모니터 — 보조 모니터 창 복원 (멀티모니터 환경에서만 실행)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc11_secondary_monitor_position_restored():
    """보조 모니터에 Notepad를 배치하고 저장 후, 종료-복원 시 보조 모니터 위치에 복원."""
    import win32gui
    from src.monitors import list_current_monitors

    monitors = list_current_monitors()
    if len(monitors) < 2:
        pytest.skip("멀티모니터 환경 필요")

    # 주 모니터가 아닌 첫 번째 모니터를 보조 모니터로 사용
    secondary = next((m for m in monitors if not m.get("primary")), None)
    assert secondary is not None, "보조 모니터를 찾을 수 없음"

    sec_rect = secondary["rect"]  # [x, y, w, h]
    # 보조 모니터 중앙 근처에 배치 (모니터 내부에 충분히 들어오도록)
    target_x = sec_rect[0] + 100
    target_y = sec_rect[1] + 100
    target_w = min(600, sec_rect[2] - 200)
    target_h = min(400, sec_rect[3] - 200)
    target = [target_x, target_y, target_w, target_h]

    _kill_all("notepad.exe")
    pre_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe", exclude_hwnds=pre_hwnds)
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        # 보조 모니터에 배치
        win32gui.SetWindowPos(hwnd, None, target[0], target[1], target[2], target[3],
                              0x0010 | 0x0004)
        # UWP fight-back 안정화 대기
        time.sleep(2.0)

        wins = list_current_windows()
        notepad_win = next((x for x in wins if _is_notepad(x) and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        captured_rect = notepad_win["placement"]["normal_rect"]

        layout = {"name": "itc11", "windows": [notepad_win], "monitors": list_current_monitors()}
    finally:
        proc.terminate()
        _kill_all("notepad.exe")

    pre_restore_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    # post_settle_ms=4500 ensures re-apply fires after UWP startup restore (~3 s).
    result = restore_layout(layout, stabilize_ms=500, post_settle_ms=4500)
    assert result["restored"] == 1

    wins_after = list_current_windows()
    new_wins = [x for x in wins_after if _is_notepad(x) and x["hwnd"] not in pre_restore_hwnds]
    notepad_wins = new_wins if new_wins else [x for x in wins_after if _is_notepad(x)]
    assert len(notepad_wins) >= 1, "Notepad window not found after restore"

    actual_rect = notepad_wins[0]["placement"]["normal_rect"]
    assert _rects_close(actual_rect, captured_rect, tol=30), \
        f"ITC11: 보조 모니터 위치 불일치 — captured={captured_rect}, actual={actual_rect}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC9: 동일 레이아웃 연속 2회 복구 — 멱등성(idempotency) 검증
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc9_restore_idempotent_two_runs():
    """Restore the same layout twice; both runs should place Notepad at the saved position."""
    import win32gui

    # Kill Win32 Notepad instances left from prior tests; UWP Notepad may survive.
    _kill_all("notepad.exe")
    pre_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    proc = subprocess.Popen(["notepad.exe"])
    try:
        # Wait for the newly launched Win32 Notepad (hwnd not in the pre-existing set).
        w = None
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            for win in list_current_windows():
                if (_is_notepad(win)
                        and win["hwnd"] not in pre_hwnds):
                    w = win
                    break
            if w:
                break
            time.sleep(0.5)
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        target = [200, 200, 700, 500]
        win32gui.SetWindowPos(hwnd, None, target[0], target[1], target[2], target[3],
                              0x0010 | 0x0004)
        time.sleep(0.3)

        wins = list_current_windows()
        notepad_win = next((x for x in wins if _is_notepad(x)
                            and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        captured_rect = notepad_win["placement"]["normal_rect"]

        layout = {"name": "itc9", "windows": [notepad_win], "monitors": []}
    finally:
        proc.terminate()
        _kill_all("notepad.exe")

    saved_exe = notepad_win["exe_path"].lower()

    # 1차 복구 — UWP startup state restoration finishes within ~3s; post_settle_ms=4500
    # ensures our re-apply fires AFTER UWP's fight-back window.
    pre_restore1_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}
    result1 = restore_layout(layout, stabilize_ms=500, post_settle_ms=4500)
    assert result1["restored"] == 1

    wins1 = list_current_windows()
    # Prefer newly launched windows over pre-existing UWP survivors (e.g. from prior tests).
    new_np1 = [x for x in wins1 if _is_notepad(x) and x["hwnd"] not in pre_restore1_hwnds]
    np1 = new_np1 if new_np1 else [x for x in wins1 if x.get("exe_path", "").lower() == saved_exe]
    assert len(np1) >= 1
    actual1 = np1[0]["placement"]["normal_rect"]
    assert _rects_close(actual1, captured_rect, tol=20), \
        f"ITC9 run1: position mismatch — saved={captured_rect}, actual={actual1}"

    _kill_all("notepad.exe")

    # 2차 복구 — same post_settle_ms reasoning as first run
    pre_restore2_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}
    result2 = restore_layout(layout, stabilize_ms=500, post_settle_ms=4500)
    assert result2["restored"] == 1

    wins2 = list_current_windows()
    new_np2 = [x for x in wins2 if _is_notepad(x) and x["hwnd"] not in pre_restore2_hwnds]
    np2 = new_np2 if new_np2 else [x for x in wins2 if x.get("exe_path", "").lower() == saved_exe]
    assert len(np2) >= 1
    actual2 = np2[0]["placement"]["normal_rect"]
    assert _rects_close(actual2, captured_rect, tol=20), \
        f"ITC9 run2: position mismatch — saved={captured_rect}, actual={actual2}"

    _kill_all("notepad.exe")


# ---------------------------------------------------------------------------
# ITC10: post_settle 재적용 검증
# Chrome/Electron이 WM_WINDOWPOSCHANGED로 창을 비동기 복원하는 상황을 시뮬레이션:
# restore_layout 실행 중 배치 직후 외부 스레드가 창을 강제 이동시키고,
# post_settle 재적용이 올바른 위치로 되돌리는지 5초 후 확인.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc10_post_settle_corrects_async_window_move():
    """restore_layout 배치 직후 외부에서 창을 이동시켜도 post_settle 재적용이 올바른 위치를 유지."""
    import threading
    import win32gui

    _kill_all("notepad.exe")
    pre_hwnds = {w["hwnd"] for w in list_current_windows() if _is_notepad(w)}

    proc = subprocess.Popen(["notepad.exe"])
    try:
        w = _wait_for_exe_window("notepad.exe", exclude_hwnds=pre_hwnds)
        assert w is not None, "Notepad window did not appear"
        hwnd = w["hwnd"]

        target = [300, 200, 700, 500]
        win32gui.SetWindowPos(hwnd, None, target[0], target[1], target[2], target[3],
                              0x0010 | 0x0004)
        time.sleep(0.3)

        wins = list_current_windows()
        notepad_win = next((x for x in wins
                            if _is_notepad(x)
                            and x["hwnd"] == hwnd), None)
        assert notepad_win is not None
        layout = {"name": "itc10", "windows": [notepad_win], "monitors": []}

        # 배치 직후(~1.7 s) 외부 스레드가 창을 나쁜 위치로 이동 (Chrome/Electron 비동기 복원 시뮬레이션)
        bad_pos = [target[0] + 400, target[1] + 300, target[2], target[3]]

        def _async_disrupt():
            time.sleep(1.7)
            try:
                win32gui.SetWindowPos(hwnd, None, bad_pos[0], bad_pos[1],
                                      bad_pos[2], bad_pos[3], 0x0010 | 0x0004)
            except Exception:
                pass

        threading.Thread(target=_async_disrupt, daemon=True).start()

        # Pass running_windows with only hwnd so match_windows cannot pick a
        # pre-existing Notepad window over our tracked window.
        running_for_restore = [x for x in list_current_windows() if x["hwnd"] == hwnd]
        result = restore_layout(layout, running_windows=running_for_restore,
                                post_settle_ms=3000)
        assert result["restored"] == 1

        # restore_layout 반환 후 5초 대기 — 추가 비동기 이동이 없는지 확인
        time.sleep(5)

        wins_after = list_current_windows()
        # Use the tracked hwnd to avoid picking up pre-existing UWP Notepad windows.
        notepad_wins = [x for x in wins_after if x["hwnd"] == hwnd]
        assert len(notepad_wins) >= 1, "Tracked Notepad window not found after restore"

        actual_rect = notepad_wins[0]["placement"]["normal_rect"]
        assert _rects_close(actual_rect, target, tol=20), (
            f"ITC10: post_settle 재적용 후에도 위치 불일치 — "
            f"target={target}, actual={actual_rect}, bad_pos={bad_pos}"
        )
    finally:
        proc.terminate()
        _kill_all("notepad.exe")
