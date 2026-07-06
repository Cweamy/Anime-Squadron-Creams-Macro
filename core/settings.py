import json
import os
import re
from core.constants import APP_DIR, LOADOUT_DIR


SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

_DEFAULTS = {
    "webhook_url": "",
    "webhook_enabled": True,
    "queue": [],
    "trait_farm": {"stages": {}, "last_reset": ""},
    "hotkeys": {"stop": "f2", "pause": "f3", "hide": "f4"},
    "tutorial_seen": False,
}

# Storage (settings.json + the Loadouts folder) is only written to disk once
# the user has explicitly agreed to it. Existing installs (settings.json
# already present) are treated as already-consented so returning users are
# never re-prompted.
_storage_allowed = os.path.exists(SETTINGS_FILE)


def needs_consent() -> bool:
    return not _storage_allowed


def grant_consent():
    global _storage_allowed
    _storage_allowed = True
    try:
        os.makedirs(LOADOUT_DIR, exist_ok=True)
    except OSError:
        pass
    save(dict(_DEFAULTS))


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
    if not _storage_allowed:
        return
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ── Loadouts (each saved as its own file under LOADOUT_DIR) ──

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def _loadout_filename(name: str) -> str:
    safe = _INVALID_FILENAME_CHARS.sub("_", name).strip() or "Loadout"
    return safe + ".json"


def _migrate_legacy_loadouts():
    """One-time migration for loadouts that used to live inside settings.json."""
    data = load()
    legacy = data.pop("loadouts", None)
    if not legacy:
        return
    try:
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        for name, tasks in legacy.items():
            path = os.path.join(LOADOUT_DIR, _loadout_filename(name))
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"name": name, "tasks": tasks}, f, indent=2)
    except OSError:
        return
    save(data)


def list_loadouts() -> dict:
    if _storage_allowed:
        _migrate_legacy_loadouts()
    if not os.path.isdir(LOADOUT_DIR):
        return {}
    result = {}
    try:
        filenames = os.listdir(LOADOUT_DIR)
    except OSError:
        return {}
    for fname in filenames:
        if not fname.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(LOADOUT_DIR, fname), "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if isinstance(tasks, list):
            name = payload.get("name") or os.path.splitext(fname)[0]
            result[name] = tasks
    return result


def save_loadout_file(name: str, tasks: list):
    if not _storage_allowed:
        return
    try:
        os.makedirs(LOADOUT_DIR, exist_ok=True)
        path = os.path.join(LOADOUT_DIR, _loadout_filename(name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "tasks": tasks}, f, indent=2)
    except OSError:
        pass


def delete_loadout_file(name: str):
    path = os.path.join(LOADOUT_DIR, _loadout_filename(name))
    try:
        os.remove(path)
    except OSError:
        pass
