"""Integration tests for multi-window app restore (requires Chrome running)."""
import pytest
from unittest.mock import MagicMock

CHROME_EXE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"


@pytest.fixture
def chrome_windows():
    """Capture current Chrome windows. Skip if fewer than 2 are open."""
    from src.capture import list_current_windows
    wins = [w for w in list_current_windows()
            if w.get("exe_path", "").lower() == CHROME_EXE.lower()]
    if len(wins) < 2:
        pytest.skip("Need at least 2 Chrome windows for this test")
    return wins


@pytest.mark.integration
def test_its_t10_1_two_chrome_windows_matched_correctly(chrome_windows):
    """
    실제 2개 Chrome 창이 각각 올바른 saved 창에 매칭됨.
    saved 창 z_order를 반전시켜도 title_snapshot 기반으로 올바르게 매칭.
    """
    from src.restore import match_windows

    saved = [
        {**chrome_windows[0],
         "z_order": chrome_windows[1]["z_order"],   # z_order 의도적으로 교차
         "placement": chrome_windows[0].get("placement", {})},
        {**chrome_windows[1],
         "z_order": chrome_windows[0]["z_order"],
         "placement": chrome_windows[1].get("placement", {})},
    ]
    sorted_saved = sorted(saved, key=lambda w: w.get("z_order", 0), reverse=True)

    results = match_windows(sorted_saved, chrome_windows)

    for r in results:
        saved_w, running_w = r
        assert running_w is not None, f"no candidate for saved hwnd=0x{saved_w['hwnd']:x}"
        # title_snapshot 일치하는 running 창에 매칭
        assert saved_w["title_snapshot"] == running_w["title_snapshot"]


@pytest.mark.integration
def test_its_t10_2_ensure_apps_count_based_detection(monkeypatch):
    """
    ensure_apps_running count-based: Chrome 2개 저장, 1개만 실행 중이면 1회 launch 시도.
    실제 launch는 하지 않고 launch_app 호출 여부만 확인.
    """
    from src.capture import list_current_windows
    running = [w for w in list_current_windows()
               if w.get("exe_path", "").lower() == CHROME_EXE.lower()]
    if len(running) < 1:
        pytest.skip("Need at least 1 Chrome window")

    saved_windows = [
        {**running[0], "exe_args": "", "cwd": "", "is_uwp": False, "title_pattern": "Chrome$"},
        {**running[0], "exe_args": "", "cwd": "", "is_uwp": False, "title_pattern": "Chrome$"},
    ]

    launched = []

    import src.launcher as _launcher
    monkeypatch.setattr(_launcher, "launch_app",
                        lambda exe, *a, **kw: launched.append(exe) or MagicMock())
    monkeypatch.setattr(_launcher, "_wait_for_window_count", lambda *a, **kw: True)

    from src.launcher import ensure_apps_running
    result = ensure_apps_running(saved_windows, timeout_seconds=5, poll_ms=50)

    # 1개 running, 2개 needed → 1회 launch 시도
    assert result == 1
    assert CHROME_EXE.lower() in [e.lower() for e in launched]
