import os
from pathlib import Path

APPDATA = Path(os.environ.get("APPDATA", Path.home())) / "WinLayoutSaver"
LAYOUTS_DIR = APPDATA / "layouts"
CONFIG_PATH = APPDATA / "config.json"
LOGS_DIR = APPDATA / "logs"
