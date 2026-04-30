import pytest
from src.monitors import compare_monitors, MatchResult, clamp_rect_to_monitor, filter_to_primary


def make_monitor(index=0, x=0, y=0, w=2560, h=1440, primary=True, scale=1.0):
    return {"index": index, "rect": [x, y, w, h], "primary": primary, "scale": scale}


def make_ext(index=1, x=2560, y=0, w=1920, h=1080, primary=False, scale=1.0):
    return make_monitor(index=index, x=x, y=y, w=w, h=h, primary=primary, scale=scale)


class TestCompareMonitors:
    def test_match_identical_configs(self):
        saved = [make_monitor(), make_ext()]
        current = [make_monitor(), make_ext()]
        assert compare_monitors(saved, current) == MatchResult.MATCH

    def test_primary_only_external_differs(self):
        saved = [make_monitor(), make_ext()]
        current = [make_monitor(), make_ext(w=1600)]  # different resolution
        assert compare_monitors(saved, current) == MatchResult.PRIMARY_ONLY

    def test_primary_only_external_removed(self):
        saved = [make_monitor(), make_ext()]
        current = [make_monitor()]  # external removed
        assert compare_monitors(saved, current) == MatchResult.PRIMARY_ONLY

    def test_no_match_primary_differs(self):
        saved = [make_monitor(w=2560, h=1440)]
        current = [make_monitor(w=1920, h=1080)]  # primary resolution changed
        assert compare_monitors(saved, current) == MatchResult.NO_MATCH

    def test_match_single_monitor(self):
        saved = [make_monitor()]
        current = [make_monitor()]
        assert compare_monitors(saved, current) == MatchResult.MATCH


class TestFilterToPrimary:
    def test_returns_only_primary_monitor_windows(self):
        saved_windows = [
            {"monitor_index": 0, "title_snapshot": "win0"},
            {"monitor_index": 1, "title_snapshot": "win1"},
            {"monitor_index": 0, "title_snapshot": "win0b"},
        ]
        saved_monitors = [make_monitor(index=0), make_ext(index=1)]
        result = filter_to_primary(saved_windows, saved_monitors)
        assert len(result) == 2
        assert all(w["monitor_index"] == 0 for w in result)

    def test_all_windows_on_primary_if_single_monitor(self):
        saved_windows = [
            {"monitor_index": 0, "title_snapshot": "a"},
            {"monitor_index": 0, "title_snapshot": "b"},
        ]
        saved_monitors = [make_monitor(index=0)]
        result = filter_to_primary(saved_windows, saved_monitors)
        assert len(result) == 2


class TestClampRect:
    def test_rect_outside_monitor_is_clamped(self):
        monitor = make_monitor(x=0, y=0, w=1920, h=1080)
        rect = [2000, 1200, 800, 600]  # outside monitor
        result = clamp_rect_to_monitor(rect, monitor)
        mx, my, mw, mh = monitor["rect"]
        # x must be within monitor bounds
        assert result[0] >= mx
        assert result[0] + result[2] <= mx + mw
        # y must be within monitor bounds
        assert result[1] >= my
        assert result[1] + result[3] <= my + mh

    def test_rect_inside_monitor_unchanged(self):
        monitor = make_monitor(x=0, y=0, w=1920, h=1080)
        rect = [100, 100, 800, 600]
        result = clamp_rect_to_monitor(rect, monitor)
        assert result == rect

    def test_rect_larger_than_monitor_is_size_clamped(self):
        monitor = make_monitor(x=0, y=0, w=1920, h=1080)
        rect = [0, 0, 2560, 1440]  # window bigger than monitor
        result = clamp_rect_to_monitor(rect, monitor)
        assert result[2] == 1920  # width clamped to monitor width
        assert result[3] == 1080  # height clamped to monitor height
