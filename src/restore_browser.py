"""Build launch argument list for restoring a Chromium browser window."""


def build_browser_launch_args(exe_path: str, app_ctx: dict) -> list[str]:
    """Return [exe_path, --new-window, url1, url2, ...] skipping blank URLs."""
    tabs = app_ctx.get("browser_tabs", [])
    nonblank = [u for u in tabs if u]
    if not nonblank:
        return [exe_path]
    return [exe_path, "--new-window"] + nonblank
