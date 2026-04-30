import logging
import re
import subprocess
import time
from typing import Optional

import psutil

from src.capture import list_current_windows

logger = logging.getLogger("launcher")


def is_running(exe_path: str) -> bool:
    """Check if any process with this exe path is currently running."""
    exe_lower = exe_path.lower()
    for proc in psutil.process_iter(["exe"]):
        try:
            proc_exe = proc.info.get("exe") or ""
            if proc_exe.lower() == exe_lower:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def launch_app(exe_path: str, exe_args: str = "", cwd: str = "", is_uwp: bool = False) -> Optional[subprocess.Popen]:
    """
    Launch an application.
    For UWP apps, uses `explorer.exe shell:AppsFolder\\<AUMID>`.
    Returns the Popen object or None on failure.
    """
    if is_uwp:
        aumid = exe_args.strip()
        cmd = ["explorer.exe", f"shell:AppsFolder\\{aumid}"]
        logger.info("launching UWP app shell:AppsFolder\\%s", aumid)
    else:
        args = exe_args.split() if exe_args else []
        cmd = [exe_path] + args
        logger.info("launching %s args=%s", exe_path, args)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd or None,
            shell=False,
            creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, "DETACHED_PROCESS") else 0,
        )
        return proc
    except OSError as e:
        logger.error("failed to launch %s: %s", exe_path, e)
        return None


def wait_for_window(
    exe_path: str,
    title_pattern: str,
    timeout_seconds: float = 60.0,
    poll_ms: int = 500,
) -> bool:
    """
    Poll until a window from exe_path matching title_pattern appears,
    or timeout_seconds elapses.
    Returns True if window found, False on timeout.
    """
    exe_lower = exe_path.lower()
    pattern_re = re.compile(title_pattern) if title_pattern else None
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        windows = list_current_windows()
        for w in windows:
            if w.get("exe_path", "").lower() != exe_lower:
                continue
            if pattern_re is None or pattern_re.search(w.get("title_snapshot", "")):
                elapsed = timeout_seconds - (deadline - time.monotonic())
                logger.info("matched after %.1fs — exe=%s title='%s'", elapsed, exe_path, w.get("title_snapshot", ""))
                return True
        logger.debug("polling for window exe=%s pattern='%s'", exe_path, title_pattern)
        time.sleep(poll_ms / 1000.0)

    logger.warning("timeout after %.0fs waiting for exe=%s pattern='%s'", timeout_seconds, exe_path, title_pattern)
    return False


def _wait_for_window_count(exe_path: str, min_count: int, timeout_seconds: float, poll_ms: int) -> bool:
    """Poll until at least min_count visible windows of exe_path exist."""
    exe_lower = exe_path.lower()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        count = sum(1 for w in list_current_windows()
                    if w.get("exe_path", "").lower() == exe_lower)
        if count >= min_count:
            return True
        logger.debug("waiting for %d window(s) of %s (current: %d)", min_count, exe_lower, count)
        time.sleep(poll_ms / 1000.0)
    logger.warning("timeout waiting for %d window(s) of %s", min_count, exe_lower)
    return False


def has_visible_window(exe_path: str, title_pattern: str) -> bool:
    """Return True if a visible window exists for exe_path matching title_pattern."""
    exe_lower = exe_path.lower()
    pattern_re = re.compile(title_pattern) if title_pattern else None
    for w in list_current_windows():
        if w.get("exe_path", "").lower() != exe_lower:
            continue
        if pattern_re is None or pattern_re.search(w.get("title_snapshot", "")):
            return True
    return False


def ensure_apps_running(
    saved_windows: list[dict],
    timeout_seconds: float = 60.0,
    poll_ms: int = 500,
) -> int:
    """
    For each exe_path, compare saved window count vs running window count.
    If running count < saved count, launch the app once per missing window.
    Returns total number of launch_app calls made.
    """
    from collections import Counter

    exe_to_saved: dict[str, list[dict]] = {}
    for w in saved_windows:
        exe = w.get("exe_path", "")
        if not exe:
            continue
        exe_to_saved.setdefault(exe.lower(), []).append(w)

    if not exe_to_saved:
        return 0

    running_now = list_current_windows()
    running_counts = Counter(
        w.get("exe_path", "").lower() for w in running_now if w.get("exe_path")
    )

    logger.info(
        "ensure_apps: checking %d exe(s) — running counts: %s",
        len(exe_to_saved), dict(running_counts),
    )

    launched_total = 0
    for exe_lower, saved_list in exe_to_saved.items():
        n_needed = len(saved_list)
        n_running = running_counts.get(exe_lower, 0)
        deficit = n_needed - n_running

        if deficit <= 0:
            logger.debug("ensure_apps: %s — %d/%d, no launch needed", exe_lower, n_running, n_needed)
            continue

        logger.info("ensure_apps: %s — %d running, %d needed, launching %d", exe_lower, n_running, n_needed, deficit)

        rep = saved_list[0]
        for k in range(deficit):
            target_count = n_running + k + 1
            proc = launch_app(
                rep["exe_path"],
                rep.get("exe_args", ""),
                rep.get("cwd", ""),
                rep.get("is_uwp", False),
            )
            if proc is None:
                continue
            launched_total += 1
            found = _wait_for_window_count(rep["exe_path"], target_count, timeout_seconds, poll_ms)
            if not found:
                logger.warning(
                    "ensure_apps: gave up waiting for window #%d of %s",
                    target_count, exe_lower,
                )

    return launched_total
