import json
import logging
from pathlib import Path

logger = logging.getLogger("storage")

from src.paths import APPDATA, LAYOUTS_DIR, CONFIG_PATH


def _ensure_dirs():
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)


def save_layout(name: str, layout_data: dict) -> Path:
    _ensure_dirs()
    path = LAYOUTS_DIR / f"{name}.json"
    logger.info("saving layout '%s' to %s", name, path)
    try:
        path.write_text(json.dumps(layout_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.error("failed to write %s: %s", path, e)
        raise
    windows_count = len(layout_data.get("windows", []))
    logger.info("saved '%s' (%d windows)", name, windows_count)
    return path


def load_layout(name: str) -> dict:
    path = LAYOUTS_DIR / f"{name}.json"
    logger.info("loading layout '%s' from %s", name, path)
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except FileNotFoundError:
        raise FileNotFoundError(f"Layout not found: {name}") from None
    except json.JSONDecodeError as e:
        logger.error("JSON parse error in %s: %s", path, e)
        raise ValueError(f"Corrupted layout file: {path}") from e
    logger.info("loaded '%s' (%d windows)", name, len(data.get("windows", [])))
    return data


def list_layouts() -> list[str]:
    if not LAYOUTS_DIR.exists():
        return []
    return sorted(p.stem for p in LAYOUTS_DIR.glob("*.json"))


def delete_layout(name: str) -> None:
    json_path = LAYOUTS_DIR / f"{name}.json"
    png_path = LAYOUTS_DIR / f"{name}.png"
    json_path.unlink(missing_ok=True)
    png_path.unlink(missing_ok=True)
    logger.info("deleted layout '%s' (json + png)", name)


def screenshot_path(name: str) -> Path:
    """Layout과 짝이 되는 PNG 경로 반환 (실제 파일 존재 여부와 무관)."""
    return LAYOUTS_DIR / f"{name}.png"


def next_layout_name() -> str:
    existing = set(list_layouts())
    i = 1
    while f"Screen{i}" in existing:
        i += 1
    return f"Screen{i}"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return _default_config()
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_config()


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def _default_config() -> dict:
    return {
        "auto_rollback": {
            "enabled": False,
            "layout_name": "",
            "mode": "fast",
            "startup_delay_seconds": 10,
            "app_launch_timeout_seconds": 60,
            "per_window_retry_ms": 500,
        },
        "ui": {"language": "ko"},
    }
