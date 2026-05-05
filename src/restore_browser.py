"""Build launch argument list for restoring a Chromium browser window."""
import logging

logger = logging.getLogger("restore_browser")


def build_browser_launch_args(exe_path: str, app_ctx: dict) -> list[str]:
    """Return [exe_path, --new-window, url1, url2, ...] skipping blank URLs."""
    tabs = app_ctx.get("browser_tabs", [])
    nonblank = [u for u in tabs if u]
    if not nonblank:
        logger.info("build_browser_launch_args: no urls → launching without --new-window")
        return [exe_path]
    cmd = [exe_path, "--new-window"] + nonblank
    logger.info("build_browser_launch_args: %d url(s), cmd[0..3]=%s ...", len(nonblank), cmd[:3])
    return cmd
