"""Per-window context detector. Routes to per-app capture functions."""
import os
import logging

logger = logging.getLogger("app_context")

CHROMIUM_EXES = {"chrome.exe", "msedge.exe", "brave.exe", "whale.exe"}
OFFICE_MAP = {
    "winword.exe":  "office_word",
    "powerpnt.exe": "office_ppt",
    "excel.exe":    "office_excel",
}
DOC_GENERIC_EXES = {
    "acrord32.exe", "acrobat.exe", "notepad.exe", "notepad++.exe",
    "code.exe", "sublime_text.exe", "atom.exe", "wordpad.exe",
}


def detect(exe_path: str) -> str | None:
    """Returns app_context type string, or None if app has no context."""
    base = os.path.basename(exe_path).lower()
    if base in CHROMIUM_EXES:
        return "chromium"
    if base in OFFICE_MAP:
        return OFFICE_MAP[base]
    if base in DOC_GENERIC_EXES:
        return "document_generic"
    return None


def capture_for(exe_path: str, hwnd: int) -> dict | None:
    """Top-level entry. Returns app_context dict or None."""
    typ = detect(exe_path)
    if typ is None:
        return None
    try:
        if typ == "chromium":
            from src.capture_browser import capture_browser_window
            return capture_browser_window(hwnd)
        if typ in ("office_word", "office_ppt", "office_excel"):
            from src.capture_office import capture_office_doc
            return capture_office_doc(hwnd, typ)
        if typ == "document_generic":
            from src.capture_doc_title import capture_doc_title
            return capture_doc_title(hwnd, exe_path)
    except Exception as e:
        logger.warning("app_context capture failed for hwnd=0x%x exe=%s: %s", hwnd, exe_path, e)
    return None
