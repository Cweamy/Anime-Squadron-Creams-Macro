import json
import os
from core.constants import APP_DIR


SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

_DEFAULTS = {
    "webhook_url": "",
    "webhook_enabled": True,
    "queue": [],
}


def load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return dict(_DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in _DEFAULTS.items():
            data.setdefault(k, v)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save(data: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass
