import logging
import re as _re
import time
from typing import Optional

logger = logging.getLogger("capture")


def _auto_title_pattern(title: str) -> str:
    sep = " - "
    if sep in title:
        app_name = title.rsplit(sep, 1)[-1].strip()
        return _re.escape(app_name) + "$"
    return _re.escape(title) + "$"


def _get_placement_state(show_cmd: int) -> str:
    try:
        import win32con
        if show_cmd == win32con.SW_SHOWMINIMIZED:
            return "minimized"
        if show_cmd == win32con.SW_SHOWMAXIMIZED:
            return "maximized"
    except (ImportError, AttributeError):
        pass
    return "normal"


def _is_cloaked(hwnd: int) -> bool:
    try:
        import ctypes
        DWMWA_CLOAKED = 14
        cloaked = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return cloaked.value != 0
    except Exception:  # ctypes call may fail on some windows versions
        return False


def _get_exe_path(hwnd: int) -> Optional[str]:
    try:
        import win32process, win32api
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(int(handle), 0, buf, ctypes.byref(size))
            return buf.value
        finally:
            win32api.CloseHandle(handle)
    except Exception as e:
        logger.warning("OpenProcess failed for hwnd=%s: %s", hwnd, e)
        return None


def _build_hmonitor_index_map() -> dict:
    """Build a mapping of HMONITOR handle → index for monitor_index assignment."""
    try:
        import ctypes
        import win32api

        hmonitor_to_index = {}
        counter = [0]

        def _enum_proc(hmonitor, hdc, lprect, lparam):
            hmonitor_to_index[hmonitor] = counter[0]
            counter[0] += 1
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_long),
            ctypes.c_long,
        )
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_proc), 0)
        return hmonitor_to_index
    except Exception as e:
        logger.warning("failed to build hmonitor index map: %s", e)
        return {}


def list_current_windows() -> list[dict]:
    import win32gui, win32con

    t0 = time.perf_counter()
    logger.info("enumerating windows")

    hmonitor_to_index = _build_hmonitor_index_map()

    results = []
    all_hwnds = []

    def _enum_cb(hwnd, _):
        all_hwnds.append(hwnd)

    win32gui.EnumWindows(_enum_cb, None)

    skipped = 0
    for i, hwnd in enumerate(all_hwnds):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                logger.debug("skipped invisible hwnd=%s", hwnd)
                skipped += 1
                continue
            title = win32gui.GetWindowText(hwnd)
            if not title:
                logger.debug("skipped no-title hwnd=%s", hwnd)
                skipped += 1
                continue
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                logger.debug("skipped tool window hwnd=%s title='%s'", hwnd, title)
                skipped += 1
                continue
            if _is_cloaked(hwnd):
                logger.debug("skipped cloaked hwnd=%s title='%s'", hwnd, title)
                skipped += 1
                continue

            class_name = win32gui.GetClassName(hwnd)
            exe_path = _get_exe_path(hwnd)
            if exe_path is None:
                logger.warning("skipped hwnd=%s (no exe path)", hwnd)
                skipped += 1
                continue

            placement = win32gui.GetWindowPlacement(hwnd)
            show_cmd = placement[1] if placement else 1
            if placement and len(placement) > 4:
                ltrb = list(placement[4])  # [left, top, right, bottom]
                normal_rect = [ltrb[0], ltrb[1], ltrb[2] - ltrb[0], ltrb[3] - ltrb[1]]  # stored as [x, y, w, h] (XYWH)
            else:
                normal_rect = [0, 0, 800, 600]  # stored as [x, y, w, h] (XYWH)
            min_pos = list(placement[2]) if placement and len(placement) > 2 else [-1, -1]
            max_pos = list(placement[3]) if placement and len(placement) > 3 else [-1, -1]
            state = _get_placement_state(show_cmd)

            # For normal state windows (including Windows-Snap positions), GetWindowRect
            # gives the actual visible screen position. rcNormalPosition stores the
            # pre-snap restore position, which doesn't match what the user sees.
            if state == "normal":
                try:
                    r = win32gui.GetWindowRect(hwnd)
                    normal_rect = [r[0], r[1], r[2] - r[0], r[3] - r[1]]
                except OSError:
                    pass  # keep rcNormalPosition as fallback

            is_uwp = exe_path.lower().endswith("applicationframehost.exe")

            try:
                import ctypes
                hwnd_monitor = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST=2
                monitor_index = hmonitor_to_index.get(hwnd_monitor, 0)
            except Exception:
                monitor_index = 0

            entry = {
                "hwnd": hwnd,
                "exe_path": exe_path,
                "exe_args": "",
                "cwd": "",
                "title_snapshot": title,
                "title_pattern": _auto_title_pattern(title),
                "class_name": class_name,
                "placement": {
                    "state": state,
                    "normal_rect": normal_rect,
                    "min_pos": min_pos,
                    "max_pos": max_pos,
                },
                "monitor_index": monitor_index,
                "z_order": i,
                "is_topmost": False,
                "is_uwp": is_uwp,
            }
            results.append(entry)
            logger.debug(
                "hwnd=0x%x exe=%s title='%s' state=%s rect=%s",
                hwnd, exe_path, title, state, normal_rect
            )
        except Exception as e:
            logger.warning("error processing hwnd=%s: %s", hwnd, e)
            skipped += 1

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info("found %d candidates (%d skipped) in %dms", len(results), skipped, elapsed_ms)
    return results


def capture_virtual_screen(path) -> bool:
    """모든 모니터 합친 가상 데스크톱 전체를 PNG로 캡처해 path에 저장.
    PIL 미설치 또는 캡처 실패 시 False 반환 (예외 전파 안 함)."""
    try:
        from PIL import ImageGrab
    except ImportError:
        logger.warning("capture_virtual_screen: Pillow not installed — screenshot skipped")
        return False
    try:
        img = ImageGrab.grab(all_screens=True)
        img.save(str(path), "PNG")
        logger.info("captured virtual screen → %s", path)
        return True
    except Exception as e:
        logger.warning("capture_virtual_screen failed: %s", e)
        return False
