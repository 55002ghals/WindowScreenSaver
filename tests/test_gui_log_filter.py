from src.gui_helpers import should_show_log_entry


class TestLogFilter:
    def test_passes_when_both_filters_enabled(self):
        assert should_show_log_entry("INFO", "capture",
            level_on={"INFO"}, module_on={"capture"}) is True

    def test_blocked_by_level_filter(self):
        assert should_show_log_entry("DEBUG", "capture",
            level_on={"INFO"}, module_on={"capture"}) is False

    def test_blocked_by_module_filter(self):
        assert should_show_log_entry("INFO", "monitors",
            level_on={"INFO"}, module_on={"capture"}) is False

    def test_passes_when_module_on_is_none(self):
        assert should_show_log_entry("INFO", "monitors",
            level_on={"INFO"}, module_on=None) is True

    def test_unknown_module_always_passes(self):
        assert should_show_log_entry("INFO", "unknown_mod",
            level_on={"INFO"}, module_on={"capture"}) is True

    def test_monitors_blocked_when_not_in_module_on(self):
        assert should_show_log_entry("INFO", "monitors",
            level_on={"INFO"}, module_on={"capture", "restore"}) is False
