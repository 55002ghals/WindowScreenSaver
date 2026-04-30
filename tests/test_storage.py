import json
import sys
import pytest
from pathlib import Path


def test_save_layout_creates_file(tmp_appdata):
    from src.storage import save_layout, LAYOUTS_DIR
    data = {"windows": [{"title": "Notepad", "rect": [0, 0, 800, 600]}]}
    path = save_layout("Screen1", data)
    assert path.exists()
    assert path == LAYOUTS_DIR / "Screen1.json"


def test_save_layout_correct_content(tmp_appdata):
    from src.storage import save_layout, LAYOUTS_DIR
    data = {"windows": [{"title": "Notepad"}]}
    save_layout("MyLayout", data)
    content = json.loads((LAYOUTS_DIR / "MyLayout.json").read_text(encoding="utf-8"))
    assert content == data


def test_load_layout_returns_saved_dict(tmp_appdata):
    from src.storage import save_layout, load_layout
    data = {"windows": [{"title": "Chrome", "rect": [100, 100, 1920, 1080]}]}
    save_layout("Screen1", data)
    loaded = load_layout("Screen1")
    assert loaded == data


def test_list_layouts_returns_names(tmp_appdata):
    from src.storage import save_layout, list_layouts
    save_layout("Alpha", {"windows": []})
    save_layout("Beta", {"windows": []})
    names = list_layouts()
    assert "Alpha" in names
    assert "Beta" in names


def test_list_layouts_sorted(tmp_appdata):
    from src.storage import save_layout, list_layouts
    save_layout("Zebra", {"windows": []})
    save_layout("Apple", {"windows": []})
    names = list_layouts()
    assert names == sorted(names)


def test_next_layout_name_screen1_when_empty(tmp_appdata):
    from src.storage import next_layout_name
    assert next_layout_name() == "Screen1"


def test_next_layout_name_auto_increments(tmp_appdata):
    from src.storage import save_layout, next_layout_name
    save_layout("Screen1", {"windows": []})
    assert next_layout_name() == "Screen2"


def test_next_layout_name_skips_existing(tmp_appdata):
    from src.storage import save_layout, next_layout_name
    save_layout("Screen1", {"windows": []})
    save_layout("Screen2", {"windows": []})
    assert next_layout_name() == "Screen3"


def test_delete_layout_removes_file(tmp_appdata):
    from src.storage import save_layout, delete_layout, LAYOUTS_DIR
    save_layout("Screen1", {"windows": []})
    delete_layout("Screen1")
    assert not (LAYOUTS_DIR / "Screen1.json").exists()


def test_delete_layout_nonexistent_does_not_raise(tmp_appdata):
    from src.storage import delete_layout
    # Should not raise
    delete_layout("DoesNotExist")


def test_list_layouts_empty_when_no_dir(tmp_appdata):
    from src.storage import list_layouts, LAYOUTS_DIR
    # Layouts dir doesn't exist yet
    assert not LAYOUTS_DIR.exists()
    assert list_layouts() == []


def test_load_nonexistent_layout_raises_file_not_found_error(tmp_appdata):
    from src.storage import load_layout
    with pytest.raises(FileNotFoundError) as exc_info:
        load_layout("DoesNotExist")
    assert "DoesNotExist" in str(exc_info.value)


def test_load_layout_corrupted_json_raises_value_error(tmp_appdata):
    from src.storage import LAYOUTS_DIR
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
    bad_file = LAYOUTS_DIR / "Corrupt.json"
    bad_file.write_text("{ not valid json !!!", encoding="utf-8")
    from src.storage import load_layout
    with pytest.raises(ValueError) as exc_info:
        load_layout("Corrupt")
    assert "Corrupt" in str(exc_info.value)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only filename restriction")
def test_save_layout_with_invalid_chars_raises(tmp_appdata):
    from src.storage import save_layout
    # Windows does not allow these characters in filenames
    with pytest.raises(OSError):
        save_layout("Screen/Invalid", {"windows": []})


def test_default_config_has_auto_rollback_mode_fast():
    from src.storage import _default_config
    cfg = _default_config()
    assert cfg["auto_rollback"]["mode"] == "fast"


# ─────────────────────────────────────────────────────────────────────────────
# Task-13: screenshot_path + delete 동반 삭제 (UT-ST1 ~ UT-ST2)
# ─────────────────────────────────────────────────────────────────────────────

def test_st1_screenshot_path_returns_png_under_layouts_dir(tmp_appdata):
    from src.storage import screenshot_path, LAYOUTS_DIR
    p = screenshot_path("Screen1")
    assert p == LAYOUTS_DIR / "Screen1.png"


def test_st2_delete_layout_removes_png_too(tmp_appdata):
    from src.storage import save_layout, delete_layout, screenshot_path, LAYOUTS_DIR
    save_layout("Screen1", {"windows": []})
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
    png = screenshot_path("Screen1")
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert png.exists()

    delete_layout("Screen1")

    assert not (LAYOUTS_DIR / "Screen1.json").exists()
    assert not png.exists()
