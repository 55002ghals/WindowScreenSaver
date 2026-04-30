"""Task-11: fast 모드가 launcher 경로를 우회하고 5초 안에 끝나는지 검증."""
import sys
import time
import types


def _stub_win32(monkeypatch):
    g = types.ModuleType("win32gui")
    c = types.ModuleType("win32con")
    c.SW_SHOWNORMAL = 1; c.SW_SHOWMINIMIZED = 2; c.SW_SHOWMAXIMIZED = 3
    g.SetWindowPlacement = lambda *a: None
    g.SetWindowPos = lambda *a: None
    g.GetWindowPlacement = lambda *a: (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600))
    g.GetWindowRect = lambda *a: (0, 0, 800, 600)
    g.EnumWindows = lambda callback, extra: None
    monkeypatch.setitem(sys.modules, "win32gui", g)
    monkeypatch.setitem(sys.modules, "win32con", c)


def test_rollback_fast_finishes_within_5_seconds(monkeypatch, tmp_path):
    _stub_win32(monkeypatch)

    layout = {
        "name": "L1",
        "windows": [{
            "exe_path": "C:\\app.exe",
            "title_snapshot": "App - foo",
            "title_pattern": "foo$",
            "class_name": "C1",
            "placement": {"state": "normal", "normal_rect": [0, 0, 800, 600],
                          "min_pos": [-1, -1], "max_pos": [-1, -1]},
            "z_order": 0,
        }],
        "monitors": [],
    }
    monkeypatch.setattr("src.storage.load_config", lambda: {
        "auto_rollback": {"layout_name": "L1", "mode": "fast", "enabled": True},
    })
    monkeypatch.setattr("src.storage.load_layout", lambda name: layout)
    monkeypatch.setattr("src.monitors.list_current_monitors", lambda: [])
    monkeypatch.setattr("src.capture.list_current_windows", lambda: [{
        "hwnd": 0xABCD, "exe_path": "C:\\app.exe",
        "title_snapshot": "App - foo", "class_name": "C1", "is_hidden": False,
    }])

    # ensure가 절대 호출되어선 안 되므로 호출되면 5초 sleep으로 실패 유도
    def fail_ensure(*a, **kw):
        time.sleep(10)
        return 0
    monkeypatch.setattr("src.launcher.ensure_apps_running", fail_ensure)
    monkeypatch.setattr("src.paths.APPDATA", tmp_path)

    sys.modules.pop("cli.rollback", None)
    from cli import rollback
    monkeypatch.setattr(sys, "argv", ["rollback.py"])

    t0 = time.monotonic()
    try:
        rollback.main()
    except SystemExit:
        pass
    elapsed = time.monotonic() - t0

    # post_settle_ms=2000 + 자체 호출 + 약간 여유 = 5초 이내
    assert elapsed < 5.0, f"fast rollback took {elapsed:.2f}s (>= 5s)"
