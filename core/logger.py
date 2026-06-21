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
        self._recent: list[str] = []

    def log(self, msg: str):
        if not self.enabled:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {msg}"
        self._recent.append(line)
        if len(self._recent) > 50:
            self._recent = self._recent[-50:]
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def get_recent(self, count: int = 20) -> list[str]:
        return self._recent[-count:]
