"""Capture file paths from generic document apps via window title + cmdline parsing."""
import json
import logging
import os
import re
import urllib.parse
from pathlib import Path

import psutil

logger = logging.getLogger("capture_doc_title")

# (exe_basename, title regex) → group(1) = 파일명/경로
# For code.exe: group(1)=file/symbol, group(2)=workspace folder name
TITLE_PATTERNS = [
    ("acrord32.exe", r"^(.+\.pdf)\s+-\s+Adobe Acrobat"),
    ("acrobat.exe",  r"^(.+\.pdf)\s+-\s+Adobe Acrobat"),
    ("notepad.exe",  r"^(.+?)\s+-\s+메모장"),
    ("notepad.exe",  r"^(.+?)\s+-\s+Notepad"),
    ("code.exe",     r"^(?:●\s+|✳\s+)?(.+?)\s+-\s+(.+?)\s+-\s+.*Visual Studio Code"),
    ("code.exe",     r"^(?:●\s+)?(.+?)\s+-\s+.*Visual Studio Code"),
    ("wordpad.exe",  r"^(.+?)\s+-\s+WordPad"),
    ("sublime_text.exe", r"^(.+?)\s+-\s+Sublime Text"),
    ("atom.exe",     r"^(.+?)\s+-\s+Atom"),
]


def _resolve_lnk(lnk_path: str) -> str | None:
    """Resolve a .lnk shortcut file to its target path using IShellLink."""
    try:
        import pythoncom
        import win32com.shell.shell as shell
        import win32com.shell.shellcon as shellcon

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


def _file_uri_to_path(uri: str) -> str:
    """Convert file:///c%3A/path/... to C:\\path\\... (Windows)."""
    # urllib.parse.unquote handles %3A → : etc.
    path = urllib.parse.unquote(uri[len("file:///"):])
    return path.replace("/", os.sep)


def _vscode_workspace_path(workspace_name: str) -> str | None:
    """Look up VS Code globalStorage/storage.json for a folder matching workspace_name."""
    storage = Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "globalStorage" / "storage.json"
    if not storage.exists():
        return None
    try:
        data = json.loads(storage.read_text(encoding="utf-8"))
        for w in data.get("windowsState", {}).get("openedWindows", []):
            uri = w.get("folder", "")
            if uri.startswith("file:///"):
                p = _file_uri_to_path(uri)
                if Path(p).name == workspace_name and Path(p).exists():
                    return p
    except Exception as e:
        logger.debug("vscode storage parse failed: %s", e)
    return None


def capture_doc_title(hwnd: int, exe_path: str) -> dict | None:
    import win32gui
    base = os.path.basename(exe_path).lower()
    title = win32gui.GetWindowText(hwnd)

    # 1) 창 제목 정규식으로 절대 경로 추출 시도
    for pat_exe, pat in TITLE_PATTERNS:
        if pat_exe != base:
            continue
        m = re.match(pat, title)
        if not m:
            continue
        candidate = m.group(1).strip()
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return {"type": "document_generic", "document_path": candidate}

    # 2) Process cmdline에서 파일 인자 추출 (psutil)
    try:
        import win32process
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        for arg in proc.cmdline()[1:]:
            if os.path.isabs(arg) and os.path.exists(arg) and not arg.lower().endswith(".exe"):
                return {"type": "document_generic", "document_path": arg}
    except Exception as e:
        logger.debug("cmdline parse failed for hwnd=0x%x: %s", hwnd, e)

    # 2b) VS Code: look up workspace path from storage.json
    if base == "code.exe":
        for pat_exe, pat in TITLE_PATTERNS:
            if pat_exe != "code.exe":
                continue
            m = re.match(pat, title)
            if not m:
                continue
            groups = m.groups()
            workspace_name = groups[1].strip() if len(groups) >= 2 else groups[0].strip()
            ws_path = _vscode_workspace_path(workspace_name)
            if ws_path:
                return {"type": "document_generic", "document_path": ws_path}

    # 3) 창 제목에서 파일명 추출 후 Recent Items에서 절대경로 검색
    for pat_exe, pat in TITLE_PATTERNS:
        if pat_exe != base:
            continue
        m = re.match(pat, title)
        if not m:
            continue
        fname = m.group(1).strip()
        recent = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Recent")
        if os.path.isdir(recent):
            for entry in os.listdir(recent):
                if entry.lower().startswith(os.path.splitext(fname.lower())[0]):
                    target = _resolve_lnk(os.path.join(recent, entry))
                    if target and os.path.exists(target):
                        return {"type": "document_generic", "document_path": target}

    return None
