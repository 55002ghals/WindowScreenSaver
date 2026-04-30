from src.i18n import t, set_language, STRINGS, available_languages

def test_all_keys_exist_in_both_languages():
    ko_keys = set(STRINGS["ko"].keys())
    en_keys = set(STRINGS["en"].keys())
    assert ko_keys == en_keys, f"Missing in en: {ko_keys - en_keys}, Missing in ko: {en_keys - ko_keys}"

def test_t_returns_korean_by_default():
    set_language("ko")
    assert t("save_btn") == "현재 배치 저장"

def test_t_returns_english_after_switch():
    set_language("en")
    assert t("save_btn") == "Save Current Layout"
    set_language("ko")  # reset

def test_t_with_format_kwargs():
    set_language("ko")
    result = t("layout_saved", name="Screen1", count=5)
    assert "Screen1" in result
    assert "5" in result

def test_t_missing_key_returns_key():
    result = t("nonexistent_key_xyz")
    assert result == "nonexistent_key_xyz"

def test_available_languages():
    langs = available_languages()
    assert "ko" in langs
    assert "en" in langs

def test_set_language_invalid_code_does_not_change_language():
    set_language("ko")
    set_language("xx")  # invalid
    assert t("save_btn") == "현재 배치 저장"  # still ko


def test_mode_strings_present_in_all_languages():
    """ko/en 양쪽에 모드 관련 4개 키가 모두 존재하고 비어있지 않아야 한다."""
    required_keys = ("mode_fast", "mode_full", "mode_fast_desc", "mode_full_desc")
    for lang in ("ko", "en"):
        for key in required_keys:
            assert key in STRINGS[lang], f"'{key}' missing in lang='{lang}'"
            assert STRINGS[lang][key].strip(), f"'{key}' is empty in lang='{lang}'"


def test_task13_strings_present_in_all_languages():
    """Task-13 신규 키가 ko/en 양쪽에 비어있지 않게 존재해야 한다."""
    from src.i18n import STRINGS
    required_keys = (
        "saved_at_format",
        "not_matched_label",
        "preview_btn",
        "ar_section_title",
        "mode_label",
        "screenshot_missing_msg",
        "preview_window_title",
    )
    for lang in ("ko", "en"):
        for key in required_keys:
            assert key in STRINGS[lang], f"'{key}' missing in lang='{lang}'"
            assert STRINGS[lang][key].strip(), f"'{key}' empty in lang='{lang}'"


def test_task14_keys_present_in_both_languages():
    from src.i18n import STRINGS
    keys = ["run_now_btn", "run_now_success_msg", "run_now_failed_msg", "migrate_task_log"]
    for k in keys:
        assert k in STRINGS["ko"], f"missing ko: {k}"
        assert k in STRINGS["en"], f"missing en: {k}"
        assert STRINGS["ko"][k]
        assert STRINGS["en"][k]


def test_task13_saved_at_format_is_strftime_compatible():
    """saved_at_format은 strftime 포맷 문자열이어야 한다 (예외 없이 적용 가능)."""
    from datetime import datetime
    from src.i18n import STRINGS
    sample = datetime(2026, 4, 29, 14, 24, 56)
    for lang in ("ko", "en"):
        fmt = STRINGS[lang]["saved_at_format"]
        out = sample.strftime(fmt)
        assert out
        assert out == "26.04.29/14:24:56"
