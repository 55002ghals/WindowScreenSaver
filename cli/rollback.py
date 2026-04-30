"""Headless rollback entry point — called by Windows Task Scheduler."""
import ctypes
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(
        ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    )
except Exception:
    pass

import argparse
import logging
import sys
from pathlib import Path

# Ensure src is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_setup import LOG_FORMAT, DATE_FORMAT
from src import storage, capture, restore as restore_mod

logger = logging.getLogger("rollback")

_SHELL_WAIT_INTERVAL_S = 5
_SHELL_WAIT_MAX_TRIES = 12   # 5s * 12 = 60s


def wait_for_shell_ready(
    list_windows_fn,
    interval_s: float = _SHELL_WAIT_INTERVAL_S,
    max_tries: int = _SHELL_WAIT_MAX_TRIES,
    sleep_fn=None,
) -> int:
    """
    list_windows_fn() 결과가 ≥1개일 때까지 폴링.
    Returns: 마지막 스캔에서 발견한 창 개수 (0이면 셸이 끝까지 비어 있던 것).
    """
    import time as _time
    sleep = sleep_fn or _time.sleep

    for attempt in range(1, max_tries + 1):
        windows = list_windows_fn()
        n = len(windows)
        if n > 0:
            logger.info(
                "rollback: shell ready — %d window(s) at attempt %d/%d",
                n, attempt, max_tries,
            )
            return n
        logger.info(
            "rollback: shell not ready — 0 windows, attempt %d/%d, sleeping %.1fs",
            attempt, max_tries, interval_s,
        )
        if attempt < max_tries:
            sleep(interval_s)

    logger.warning(
        "rollback: shell still empty after %d attempts (%ds total) — proceeding anyway",
        max_tries, int(interval_s * max_tries),
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description="WinLayoutSaver headless rollback")
    parser.add_argument("--layout", default=None, help="Layout name to restore (overrides config)")
    parser.add_argument("--no-launch", action="store_true", help="Skip launching missing apps")
    args = parser.parse_args()

    # Rollback gets its own dated log file
    import os
    from datetime import datetime
    from src.paths import APPDATA
    logs_dir = APPDATA / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rollback_log = logs_dir / f"rollback-{timestamp}.log"

    import logging.handlers
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    fh = logging.handlers.RotatingFileHandler(rollback_log, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    logger.info("rollback: starting (pid=%d)", os.getpid())

    config = storage.load_config()
    rollback_cfg = config.get("auto_rollback", {})

    if not rollback_cfg.get("enabled", False):
        logger.info("rollback: auto_rollback disabled in config — exiting")
        sys.exit(0)

    layout_name = args.layout or rollback_cfg.get("layout_name", "")
    mode = rollback_cfg.get("mode", "fast")
    if mode not in ("fast", "full"):
        logger.warning("rollback: unknown mode '%s', falling back to 'fast'", mode)
        mode = "fast"

    if not layout_name:
        logger.error("rollback: no layout name specified (use --layout or set config)")
        sys.exit(1)

    try:
        layout = storage.load_layout(layout_name)
    except FileNotFoundError:
        logger.error("rollback: layout '%s' not found", layout_name)
        sys.exit(1)

    from src.capture import list_current_windows as _list_current_windows
    wait_for_shell_ready(_list_current_windows)

    from src.monitors import list_current_monitors
    monitors_current = list_current_monitors()

    logger.info("--- phase: restore placement (mode=%s) ---", mode)

    no_launch = args.no_launch or (mode == "fast")
    logger.info("rollback: mode=%s no_launch=%s", mode, no_launch)
    result = restore_mod.restore_layout(
        layout,
        no_launch=no_launch,
        monitors_current=monitors_current,
        post_settle_ms=2000,
        post_launch_settle_ms=0 if no_launch else 5000,
    )

    logger.info(
        "rollback: complete — restored %d/%d, failed %d, elapsed %dms",
        result["restored"], result["total"], result["failed"], result["elapsed_ms"],
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
