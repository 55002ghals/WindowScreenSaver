"""Build launch argument list for restoring document apps (Office, generic)."""


def build_doc_launch_args(exe_path: str, app_ctx: dict) -> list[str]:
    """Return [exe_path, document_path] or just [exe_path] if path is empty."""
    path = app_ctx.get("document_path", "")
    if not path:
        return [exe_path]
    return [exe_path, path]
