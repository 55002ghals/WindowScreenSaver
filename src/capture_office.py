"""Capture file paths from Office apps via COM (win32com.client.GetActiveObject)."""
import logging
import os
import re

logger = logging.getLogger("capture_office")

PROGID_MAP = {
    "office_word":  "Word.Application",
    "office_ppt":   "PowerPoint.Application",
    "office_excel": "Excel.Application",
}
COLLECTION_MAP = {
    "office_word":  ("Documents", "FullName"),
    "office_ppt":   ("Presentations", "FullName"),
    "office_excel": ("Workbooks", "FullName"),
}
TITLE_APP_MAP = {
    "office_word":  r"^(.+?)\s+-\s+(?:Microsoft\s+)?Word\b",
    "office_ppt":   r"^(.+?)\s+-\s+(?:Microsoft\s+)?PowerPoint\b",
    "office_excel": r"^(.+?)\s+-\s+(?:Microsoft\s+)?Excel\b",
}


def _hwnd_to_pid(hwnd: int) -> int:
    import win32process
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


def _resolve_lnk(lnk_path: str) -> str | None:
    """Resolve a .lnk shortcut to its target path."""
    try:
        import pythoncom
        import win32com.shell.shell as shell

        pythoncom.CoInitialize()
        try:
            link = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink,
            )
            persist = link.QueryInterface(pythoncom.IID_IPersistFile)
            persist.Load(lnk_path)
            target, _ = link.GetPath(shell.SLGP_UNCPRIORITY)
            return target if target else None
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        logger.debug("_resolve_lnk failed for %s: %s", lnk_path, e)
        return None


def _fallback_title_parse(hwnd: int, typ: str) -> dict | None:
    """창 제목에서 'filename.ext - AppName' 추출. 절대경로 아니면 Recent Items 검색."""
    import win32gui
    title = win32gui.GetWindowText(hwnd)
    pat = TITLE_APP_MAP.get(typ, "")
    if not pat:
        return None
    m = re.match(pat, title)
    if not m:
        return None
    fname = m.group(1).strip()
    if os.path.isabs(fname) and os.path.exists(fname):
        return {"type": typ, "document_path": fname}
    recent = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Recent")
    if os.path.isdir(recent):
        fname_lower = os.path.splitext(fname.lower())[0]
        for entry in os.listdir(recent):
            if entry.lower().startswith(fname_lower) and entry.lower().endswith(".lnk"):
                target = _resolve_lnk(os.path.join(recent, entry))
                if target and os.path.exists(target):
                    return {"type": typ, "document_path": target}
    return None


def capture_office_doc(hwnd: int, typ: str) -> dict | None:
    """Use COM GetActiveObject to enumerate Documents/Presentations/Workbooks,
    find the one whose process matches our hwnd, return its FullName."""
    import win32com.client
    progid = PROGID_MAP.get(typ)
    collection_attr, _ = COLLECTION_MAP.get(typ, (None, None))
    if not progid or not collection_attr:
        return None

    try:
        app = win32com.client.GetActiveObject(progid)
    except Exception as e:
        logger.debug("GetActiveObject(%s) failed: %s — falling back to title", progid, e)
        return _fallback_title_parse(hwnd, typ)

    try:
        for doc in getattr(app, collection_attr):
            full = doc.FullName
            if full and os.path.exists(full):
                return {"type": typ, "document_path": full}
    except Exception as e:
        logger.warning("COM enumerate failed for typ=%s: %s", typ, e)

    return _fallback_title_parse(hwnd, typ)
