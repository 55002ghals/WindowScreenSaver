import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("monitors")


class MatchResult(Enum):
    MATCH = "MATCH"
    PRIMARY_ONLY = "PRIMARY_ONLY"
    NO_MATCH = "NO_MATCH"


def list_current_monitors() -> list[dict]:
    """
    Enumerate current monitors using EnumDisplayMonitors + GetMonitorInfoW.
    Returns list of {index, rect: [x,y,w,h], primary, scale}.
    """
    try:
        import ctypes
        import win32api

        monitors = []

        def _monitor_enum_proc(hmonitor, hdc, lprect, lparam):
            try:
                info = win32api.GetMonitorInfo(hmonitor)
                rect = info["Monitor"]  # (left, top, right, bottom)
                x, y = rect[0], rect[1]
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                primary = bool(info.get("Flags", 0) & 1)
                monitors.append({
                    "index": len(monitors),
                    "rect": [x, y, w, h],
                    "primary": primary,
                    "scale": _get_dpi_scale(hmonitor),
                })
            except Exception as e:
                logger.warning("failed to get monitor info: %s", e)
            return True  # continue enumeration

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,  # HMONITOR
            ctypes.c_ulong,  # HDC
            ctypes.POINTER(ctypes.c_long),  # LPRECT
            ctypes.c_long,  # LPARAM
        )
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_monitor_enum_proc), 0)

        logger.info("enumerated %d monitors: %s", len(monitors), [
            f"#{m['index']}{'★' if m['primary'] else ''} {m['rect'][2]}x{m['rect'][3]}"
            for m in monitors
        ])
        return monitors
    except Exception as e:
        logger.warning("monitor enumeration failed: %s", e)
        return []


def _get_dpi_scale(hmonitor) -> float:
    try:
        import ctypes
        MDT_EFFECTIVE_DPI = 0
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        return dpi_x.value / 96.0
    except Exception:
        return 1.0


def compare_monitors(saved: list[dict], current: list[dict]) -> MatchResult:
    """
    Compare saved monitor configuration to current.
    Returns MATCH, PRIMARY_ONLY, or NO_MATCH.
    """
    saved_primary = next((m for m in saved if m.get("primary")), None)
    current_primary = next((m for m in current if m.get("primary")), None)

    if saved_primary is None or current_primary is None:
        logger.warning("could not determine primary monitor in saved or current config")
        return MatchResult.NO_MATCH

    # Compare primary monitors (rect + scale)
    primary_matches = (
        saved_primary.get("rect") == current_primary.get("rect")
        and saved_primary.get("scale", 1.0) == current_primary.get("scale", 1.0)
    )

    if not primary_matches:
        logger.warning(
            "primary monitor mismatch: saved=%s current=%s",
            saved_primary.get("rect"), current_primary.get("rect"),
        )
        return MatchResult.NO_MATCH

    # Compare external monitors (set comparison by rect tuples)
    def _external_rects(monitors):
        return frozenset(
            tuple(m.get("rect", [])) for m in monitors if not m.get("primary")
        )

    saved_ext = _external_rects(saved)
    current_ext = _external_rects(current)

    if saved_ext != current_ext:
        logger.warning(
            "external monitor mismatch: saved_ext=%s current_ext=%s",
            saved_ext, current_ext,
        )
        return MatchResult.PRIMARY_ONLY

    return MatchResult.MATCH


def filter_to_primary(saved_windows: list[dict], saved_monitors: list[dict]) -> list[dict]:
    """Return only windows that were on the primary monitor when saved."""
    primary = next((m for m in saved_monitors if m.get("primary")), None)
    if primary is None:
        return saved_windows  # can't determine, return all
    primary_idx = primary.get("index", 0)
    filtered = [w for w in saved_windows if w.get("monitor_index") == primary_idx]
    return filtered


def clamp_rect_to_monitor(rect: list, monitor: dict) -> list:
    """
    Clamp rect [x, y, w, h] so it fits within monitor rect.
    Clamps size first so position clamp uses corrected dimensions.
    """
    mx, my, mw, mh = monitor["rect"]
    x, y, w, h = rect
    # Clamp size first so position clamp uses corrected dimensions
    w = min(w, mw)
    h = min(h, mh)
    # Then clamp position
    x = max(mx, min(x, mx + mw - w))
    y = max(my, min(y, my + mh - h))
    return [x, y, w, h]
