KNOWN_MODULES = frozenset({
    "monitors", "capture", "restore", "launcher",
    "scheduler", "gui", "rollback", "storage",
})


def should_show_log_entry(
    level: str,
    logger_name: str,
    level_on: set,
    module_on: "set | None",
) -> bool:
    """Log entry 표시 여부 결정 (레벨 AND 모듈 필터)."""
    if level not in level_on:
        return False
    if module_on is None:
        return True
    if logger_name not in KNOWN_MODULES:
        return True
    return logger_name in module_on
