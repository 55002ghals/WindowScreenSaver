import logging
import logging.handlers
import queue
from datetime import datetime

from src.paths import LOGS_DIR

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s %(name)-12s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging(enable_gui_handler: bool = False, gui_queue: queue.Queue = None) -> None:
    root = logging.getLogger()
    # Prevent duplicate handlers; ignore pytest's LogCaptureHandler
    app_handlers = [h for h in root.handlers if h.__class__.__name__ != "LogCaptureHandler"]
    if app_handlers:
        return
    root.setLevel(logging.DEBUG)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # File handler
    today = datetime.now().strftime("%Y%m%d")
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / f"app-{today}.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(console_handler)

    # GUI queue handler (optional)
    if enable_gui_handler and gui_queue is not None:
        queue_handler = logging.handlers.QueueHandler(gui_queue)
        queue_handler.setLevel(logging.DEBUG)
        root.addHandler(queue_handler)
