import os
import time
from datetime import datetime


class Logger:
    def __init__(self, log_dir=None, enabled=True):
        self.enabled = enabled
        if log_dir is None:
            from core.constants import APP_DIR
            log_dir = APP_DIR
        self._path = os.path.join(log_dir, "debug.log")

    def log(self, msg: str):
        if not self.enabled:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(f"{ts} | {msg}\n")
        except OSError:
            pass
