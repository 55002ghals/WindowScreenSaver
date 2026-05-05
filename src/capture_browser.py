"""Capture URLs from a Chromium browser window via UI Automation + Ctrl+Tab cycling."""
import ctypes
import logging
import time

logger = logging.getLogger("capture_browser")

# SendInput constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_TAB     = 0x09
VK_1       = 0x31


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_union(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", INPUT_union)]


def _send_key_combo(*vkeys):
    """Press all vkeys down then release all in reverse order."""
    n = len(vkeys)
    inputs = (INPUT * (n * 2))()
    for i, vk in enumerate(vkeys):
        inputs[i].type = INPUT_KEYBOARD
        inputs[i]._input.ki.wVk = vk
    for i, vk in enumerate(reversed(vkeys)):
        idx = n + i
        inputs[idx].type = INPUT_KEYBOARD
        inputs[idx]._input.ki.wVk = vk
        inputs[idx]._input.ki.dwFlags = KEYEVENTF_KEYUP
    ctypes.windll.user32.SendInput(n * 2, inputs, ctypes.sizeof(INPUT))


def _send_ctrl_tab():
    _send_key_combo(VK_CONTROL, VK_TAB)


def _send_ctrl_digit(digit: int):
    vk = 0x30 + digit  # VK_0..VK_9
    _send_key_combo(VK_CONTROL, vk)


def _get_uia():
    """Lazy-init UIAutomationCore COM client."""
    import comtypes.client
    uia_dll = comtypes.client.GetModule("UIAutomationCore.dll")
    uia = comtypes.client.CreateObject(
        "{ff48dba4-60ef-4201-aa87-54103eef594e}",
        interface=uia_dll.IUIAutomation,
    )
    return uia, uia_dll


def _get_element_from_handle(uia, uia_dll, hwnd: int):
    return uia.ElementFromHandle(hwnd)


def _find_address_bar(uia, uia_dll, root_elem):
    """Walk UIA tree to find the address/search bar element and return its Value."""
    try:
        # Chrome/Edge address bar has AutomationId "addressEditBox" or name containing "Address"
        # Try by AutomationId first
        cond_id = uia.CreatePropertyCondition(
            uia_dll.UIA_AutomationIdPropertyId,
            "addressEditBox",
        )
        elem = root_elem.FindFirst(uia_dll.TreeScope_Descendants, cond_id)
        if elem is None:
            # Fallback: search by Name "주소 및 검색창" (ko) or "Address and search bar" (en)
            for name in ("Address and search bar", "주소 및 검색창", "Search or enter web address"):
                cond_name = uia.CreatePropertyCondition(
                    uia_dll.UIA_NamePropertyId,
                    name,
                )
                elem = root_elem.FindFirst(uia_dll.TreeScope_Descendants, cond_name)
                if elem is not None:
                    break
        if elem is None:
            return None
        val_pattern = elem.GetCurrentPattern(uia_dll.UIA_ValuePatternId)
        if val_pattern is None:
            return None
        val_iface = val_pattern.QueryInterface(uia_dll.IUIAutomationValuePattern)
        return val_iface.CurrentValue
    except Exception as e:
        logger.debug("_find_address_bar failed: %s", e)
        return None


def _count_tabs(uia, uia_dll, root_elem) -> int:
    """Count tab strip children (TabItem elements)."""
    try:
        cond = uia.CreatePropertyCondition(
            uia_dll.UIA_ControlTypePropertyId,
            uia_dll.UIA_TabItemControlTypeId,
        )
        elems = root_elem.FindAll(uia_dll.TreeScope_Descendants, cond)
        return elems.Length if elems else 0
    except Exception as e:
        logger.debug("_count_tabs failed: %s", e)
        return 0


def _get_active_tab_index(uia, uia_dll, root_elem) -> int:
    """Find the index of the currently selected tab."""
    try:
        cond = uia.CreatePropertyCondition(
            uia_dll.UIA_ControlTypePropertyId,
            uia_dll.UIA_TabItemControlTypeId,
        )
        elems = root_elem.FindAll(uia_dll.TreeScope_Descendants, cond)
        if not elems:
            return 0
        for i in range(elems.Length):
            elem = elems.GetElement(i)
            try:
                sel_pattern = elem.GetCurrentPattern(uia_dll.UIA_SelectionItemPatternId)
                if sel_pattern:
                    sel_iface = sel_pattern.QueryInterface(uia_dll.IUIAutomationSelectionItemPattern)
                    if sel_iface.CurrentIsSelected:
                        return i
            except Exception:
                pass
        return 0
    except Exception as e:
        logger.debug("_get_active_tab_index failed: %s", e)
        return 0


def _is_incognito(uia, uia_dll, root_elem) -> bool:
    """Detect InPrivate/Incognito window via UIA Name or window title."""
    try:
        name = root_elem.CurrentName or ""
        if "InPrivate" in name or "시크릿" in name or "Incognito" in name:
            return True
    except Exception:
        pass
    return False


def capture_browser_window(hwnd: int) -> dict | None:
    """Returns {"type": "chromium", "browser_tabs": [...], "active_tab_index": N}."""
    import win32gui

    try:
        uia, uia_dll = _get_uia()
        root_elem = _get_element_from_handle(uia, uia_dll, hwnd)
    except Exception as e:
        logger.warning("UIA init failed for hwnd=0x%x: %s", hwnd, e)
        return None

    if _is_incognito(uia, uia_dll, root_elem):
        logger.debug("capture_browser: skipping incognito hwnd=0x%x", hwnd)
        return None

    tab_count = _count_tabs(uia, uia_dll, root_elem)
    if tab_count <= 0:
        logger.debug("capture_browser: no tabs found for hwnd=0x%x", hwnd)
        return None

    original_active = _get_active_tab_index(uia, uia_dll, root_elem)

    saved_fg = win32gui.GetForegroundWindow()
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.05)

    # Move to first tab (Ctrl+1)
    _send_ctrl_digit(1)
    time.sleep(0.08)

    urls = []
    for i in range(tab_count):
        url = _find_address_bar(uia, uia_dll, root_elem)
        urls.append(url or "")
        if i < tab_count - 1:
            _send_ctrl_tab()
            time.sleep(0.1)

    # Restore original active tab: Ctrl+1 then Ctrl+Tab N times
    _send_ctrl_digit(1)
    time.sleep(0.05)
    for _ in range(original_active):
        _send_ctrl_tab()
        time.sleep(0.05)

    # Restore focus
    if saved_fg and saved_fg != hwnd:
        try:
            win32gui.SetForegroundWindow(saved_fg)
        except OSError:
            pass

    return {
        "type": "chromium",
        "browser_tabs": urls,
        "active_tab_index": original_active,
    }
