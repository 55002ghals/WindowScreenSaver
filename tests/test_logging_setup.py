import logging
import logging.handlers
import pytest


@pytest.fixture(autouse=True)
def clean_root_logger():
    """Remove non-pytest handlers from root logger before/after each test."""
    root = logging.getLogger()
    # Save existing handlers (including pytest's LogCaptureHandler)
    original_handlers = root.handlers[:]
    # Remove any app-added handlers (non-pytest) before test
    app_handlers = [h for h in root.handlers if not h.__class__.__name__ == "LogCaptureHandler"]
    for h in app_handlers:
        root.removeHandler(h)
    yield
    # Remove any handlers added by the test (app handlers)
    for h in list(root.handlers):
        if h.__class__.__name__ != "LogCaptureHandler" and h not in original_handlers:
            root.removeHandler(h)


def _app_handlers(root):
    """Return only app-added handlers (not pytest's LogCaptureHandler)."""
    return [h for h in root.handlers if h.__class__.__name__ != "LogCaptureHandler"]


def test_setup_logging_attaches_two_handlers(tmp_path, monkeypatch):
    import src.logging_setup as lm
    monkeypatch.setattr(lm, "LOGS_DIR", tmp_path / "logs")
    from src.logging_setup import setup_logging
    setup_logging(enable_gui_handler=False)
    root = logging.getLogger()
    assert len(_app_handlers(root)) == 2


def test_file_handler_level_is_debug(tmp_path, monkeypatch):
    import src.logging_setup as lm
    monkeypatch.setattr(lm, "LOGS_DIR", tmp_path / "logs")
    from src.logging_setup import setup_logging
    setup_logging(enable_gui_handler=False)
    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].level == logging.DEBUG


def test_console_handler_level_is_info(tmp_path, monkeypatch):
    import src.logging_setup as lm
    monkeypatch.setattr(lm, "LOGS_DIR", tmp_path / "logs")
    from src.logging_setup import setup_logging
    setup_logging(enable_gui_handler=False)
    root = logging.getLogger()
    stream_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.handlers.RotatingFileHandler)
        and h.__class__.__name__ != "LogCaptureHandler"
    ]
    assert len(stream_handlers) == 1
    assert stream_handlers[0].level == logging.INFO


def test_log_format_contains_expected_fields():
    from src.logging_setup import LOG_FORMAT
    assert "%(asctime)s" in LOG_FORMAT
    assert "%(levelname)" in LOG_FORMAT
    assert "%(name)" in LOG_FORMAT
    assert "%(message)s" in LOG_FORMAT


def test_setup_logging_twice_does_not_duplicate_handlers(tmp_path, monkeypatch):
    import src.logging_setup as lm
    monkeypatch.setattr(lm, "LOGS_DIR", tmp_path / "logs")
    from src.logging_setup import setup_logging
    setup_logging(enable_gui_handler=False)
    setup_logging(enable_gui_handler=False)
    root = logging.getLogger()
    assert len(_app_handlers(root)) == 2


def test_gui_handler_adds_third_handler(tmp_path, monkeypatch):
    import queue
    import src.logging_setup as lm
    monkeypatch.setattr(lm, "LOGS_DIR", tmp_path / "logs")
    from src.logging_setup import setup_logging
    q = queue.Queue()
    setup_logging(enable_gui_handler=True, gui_queue=q)
    root = logging.getLogger()
    assert len(_app_handlers(root)) == 3
