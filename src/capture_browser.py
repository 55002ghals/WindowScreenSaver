"""Capture URLs from a Chromium browser window via UI Automation SelectionItemPattern."""
import logging
import time

logger = logging.getLogger("capture_browser")

# Partial-match keywords for address bar Name (locale-independent)
_ADDR_NAME_KEYWORDS = ("Address", "주소", "URL", "검색")

# Exact-match Name fallbacks (Chrome/Edge/Brave/Whale ko+en union, from UIA dump 2026-05-05)
_ADDR_NAME_EXACT = (
    "주소창 및 검색창",        # Chrome ko (confirmed via dump)
    "주소 및 검색창",          # Chrome ko (older)
    "주소창",
    "주소 표시줄과 검색",
    "Address and search bar",
    "Search or enter web address",
    "Search or type a URL",
    "Search or type URL",
)


def _get_uia():
    """Lazy-init UIAutomationCore COM client."""
    import comtypes.client
    uia_dll = comtypes.client.GetModule("UIAutomationCore.dll")
    uia = comtypes.client.CreateObject(
        "{ff48dba4-60ef-4201-aa87-54103eef594e}",
        interface=uia_dll.IUIAutomation,
    )
    return uia, uia_dll


def _is_incognito(uia, uia_dll, root_elem) -> bool:
    try:
        name = root_elem.CurrentName or ""
        if "InPrivate" in name or "시크릿" in name or "Incognito" in name:
            return True
    except Exception:
        pass
    return False


def _find_all_tabitems(uia, uia_dll, root_elem):
    """Return IUIAutomationElementArray of all TabItem descendants, or None."""
    try:
        cond = uia.CreatePropertyCondition(
            uia_dll.UIA_ControlTypePropertyId,
            uia_dll.UIA_TabItemControlTypeId,
        )
        elems = root_elem.FindAll(uia_dll.TreeScope_Descendants, cond)
        n = elems.Length if elems else 0
        logger.info("tabitems found: %d", n)
        return elems if n > 0 else None
    except Exception as e:
        logger.warning("_find_all_tabitems failed: %s", e)
        return None


def _find_selected_index(uia, uia_dll, tab_items) -> int:
    """Return index of the currently selected tab item (0 if not determinable)."""
    try:
        for i in range(tab_items.Length):
            elem = tab_items.GetElement(i)
            try:
                pat = elem.GetCurrentPattern(uia_dll.UIA_SelectionItemPatternId)
                if pat:
                    iface = pat.QueryInterface(uia_dll.IUIAutomationSelectionItemPattern)
                    if iface.CurrentIsSelected:
                        return i
            except Exception:
                pass
    except Exception as e:
        logger.debug("_find_selected_index failed: %s", e)
    return 0


def _read_address_bar_once(uia, uia_dll, root_elem) -> str | None:
    """Single attempt to read address bar value. Returns None if not found/empty."""
    try:
        # Strategy 1: ControlType=Edit, Name partial-match (locale-independent)
        cond_edit = uia.CreatePropertyCondition(
            uia_dll.UIA_ControlTypePropertyId,
            uia_dll.UIA_EditControlTypeId,
        )
        edits = root_elem.FindAll(uia_dll.TreeScope_Descendants, cond_edit)
        if edits:
            for i in range(edits.Length):
                e = edits.GetElement(i)
                try:
                    name = e.CurrentName or ""
                except Exception:
                    continue
                if any(kw in name for kw in _ADDR_NAME_KEYWORDS):
                    try:
                        vp = e.GetCurrentPattern(uia_dll.UIA_ValuePatternId)
                        if vp:
                            val = vp.QueryInterface(uia_dll.IUIAutomationValuePattern).CurrentValue
                            if val:
                                logger.info(
                                    "addr bar matched via partial-name name=%r value=%r",
                                    name, val[:120],
                                )
                                return val
                    except Exception:
                        pass

        # Strategy 2: Exact Name match (extended list)
        for exact_name in _ADDR_NAME_EXACT:
            cond_name = uia.CreatePropertyCondition(uia_dll.UIA_NamePropertyId, exact_name)
            elem = root_elem.FindFirst(uia_dll.TreeScope_Descendants, cond_name)
            if elem is not None:
                try:
                    vp = elem.GetCurrentPattern(uia_dll.UIA_ValuePatternId)
                    if vp:
                        val = vp.QueryInterface(uia_dll.IUIAutomationValuePattern).CurrentValue
                        if val:
                            logger.info(
                                "addr bar matched via exact-name name=%r value=%r",
                                exact_name, val[:120],
                            )
                            return val
                except Exception:
                    pass

    except Exception as e:
        logger.debug("_read_address_bar_once error: %s", e)
    return None


def _read_address_bar_with_retry(uia, uia_dll, root_elem, attempts: int = 10, interval_ms: int = 50) -> str:
    """Retry reading address bar up to `attempts` times, sleeping `interval_ms` between tries."""
    for attempt in range(attempts):
        val = _read_address_bar_once(uia, uia_dll, root_elem)
        if val:
            return val
        if attempt < attempts - 1:
            time.sleep(interval_ms / 1000.0)

    # All attempts failed — dump Edit element names for diagnostics
    try:
        cond_edit = uia.CreatePropertyCondition(
            uia_dll.UIA_ControlTypePropertyId,
            uia_dll.UIA_EditControlTypeId,
        )
        edits = root_elem.FindAll(uia_dll.TreeScope_Descendants, cond_edit)
        n = edits.Length if edits else 0
        names = []
        for i in range(n):
            try:
                names.append(repr(edits.GetElement(i).CurrentName))
            except Exception:
                names.append("<?>")
        logger.warning(
            "addr bar NOT FOUND — dumping %d Edit elements: %s",
            n, ", ".join(names),
        )
    except Exception as e:
        logger.warning("addr bar NOT FOUND and dump failed: %s", e)
    return ""


def capture_browser_window(hwnd: int) -> dict | None:
    """Returns {"type": "chromium", "browser_tabs": [...], "active_tab_index": N}."""
    try:
        uia, uia_dll = _get_uia()
        root_elem = uia.ElementFromHandle(hwnd)
    except Exception as e:
        logger.warning("UIA init failed for hwnd=0x%x: %s", hwnd, e)
        return None

    try:
        exe = ""
        import win32process, win32api, ctypes
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            h = win32api.OpenProcess(0x1000, False, pid)
            buf = ctypes.create_unicode_buffer(260)
            sz = ctypes.c_ulong(260)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(int(h), 0, buf, ctypes.byref(sz))
            exe = buf.value
            win32api.CloseHandle(h)
        except Exception:
            pass
    except Exception:
        exe = ""
    logger.info("capture_browser: hwnd=0x%x exe=%s", hwnd, exe)

    if _is_incognito(uia, uia_dll, root_elem):
        logger.info("capture_browser: skip incognito hwnd=0x%x", hwnd)
        return None

    tab_items = _find_all_tabitems(uia, uia_dll, root_elem)
    tab_count = tab_items.Length if tab_items else 0
    logger.info("capture_browser: hwnd=0x%x tab_count=%d", hwnd, tab_count)

    if tab_count == 0:
        return None

    original_active = _find_selected_index(uia, uia_dll, tab_items)
    logger.info("capture_browser: original_active_index=%d", original_active)

    urls = []
    for i in range(tab_count):
        item = tab_items.GetElement(i)
        try:
            sip = item.GetCurrentPattern(uia_dll.UIA_SelectionItemPatternId)
            sip = sip.QueryInterface(uia_dll.IUIAutomationSelectionItemPattern)
            sip.Select()
        except Exception as e:
            logger.warning("capture_browser: tab %d Select() failed: %s", i, e)
            urls.append("")
            continue

        url = _read_address_bar_with_retry(uia, uia_dll, root_elem, attempts=10, interval_ms=50)
        tab_title = ""
        try:
            tab_title = (item.CurrentName or "")[:80]
        except Exception:
            pass
        logger.info("capture_browser: tab %d/%d url=%r title=%r", i, tab_count, (url or "")[:120], tab_title)
        urls.append(url or "")

    # Restore original active tab
    try:
        orig_item = tab_items.GetElement(original_active)
        sip = orig_item.GetCurrentPattern(uia_dll.UIA_SelectionItemPatternId)
        sip = sip.QueryInterface(uia_dll.IUIAutomationSelectionItemPattern)
        sip.Select()
    except Exception as e:
        logger.warning("capture_browser: restore active tab failed: %s", e)

    return {"type": "chromium", "browser_tabs": urls, "active_tab_index": original_active}
