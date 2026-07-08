"""
Cream's Macro | Anime Squadron
Run:  python main.py
Deps: pip install -r requirements.txt
"""

import os
import json
import time
import ctypes
import threading

# Splash screen before heavy imports (cv2/numpy/webview take seconds to load)
from core.splash import show_async as _show_splash, close as _close_splash
_splash_thread = _show_splash()

import webview
import keyboard

from core import window as wm
from core import tray
from core.constants import REWARD_DIR, SCRIPT_DIR, FIXED_WIN_W, FIXED_WIN_H
from core.logger import Logger
from core.bot import GameBot
from core import settings as cfg
from core.version import VERSION
from core.updater import check_for_update, download_update, apply_update_and_restart

HOTKEY_DEFAULTS = {"stop": "f2", "pause": "f3", "hide": "f4"}
HOTKEY_ACTIONS = tuple(HOTKEY_DEFAULTS.keys())

wm.set_dpi_aware()

GUI_TITLE = "Cream's Macro | Anime Squadron"
PANEL_WIDTH = 350
GUI_WIDTH_FULL = FIXED_WIN_W + PANEL_WIDTH
GUI_WIDTH_SMALL = PANEL_WIDTH
GUI_HEIGHT = FIXED_WIN_H
GUI_HEIGHT_COMPACT = 300
ICO_PATH = os.path.join(SCRIPT_DIR, "logo.ico")


def _set_icon(hwnd: int):
    if not os.path.exists(ICO_PATH):
        return
    user32 = ctypes.windll.user32
    small = user32.LoadImageW(0, ICO_PATH, 1, 16, 16, 0x0010)
    big = user32.LoadImageW(0, ICO_PATH, 1, 48, 48, 0x0010)
    if small:
        user32.SendMessageW(hwnd, 0x0080, 0, small)
    if big:
        user32.SendMessageW(hwnd, 0x0080, 1, big)


class Api:
    def __init__(self):
        self.logger = Logger()
        self.bot = GameBot(self.logger)
        self._window = None
        self._poll_thread = None
        self._hidden = False
        self._on_hotkeys_changed = None

        tf = cfg.load().get("trait_farm", {})
        self.bot.set_trait_state(tf.get("stages", {}), tf.get("last_reset", ""))
        self.bot.on_trait_update = self._on_trait_update

    def _on_trait_update(self, state: dict):
        data = cfg.load()
        counts = {key: info["count"] for key, info in state["stages"].items()}
        data["trait_farm"] = {"stages": counts, "last_reset": state["last_reset"]}
        cfg.save(data)

    def needs_storage_consent(self) -> bool:
        return cfg.needs_consent()

    def grant_storage_consent(self) -> dict:
        cfg.grant_consent()
        return {"ok": True}

    def set_window(self, w):
        self._window = w

    def start_queue(self, tasks: list, config: dict):
        self.bot.execute_queue(tasks, config)

    def update_challenge_settings(self, check_challenges: bool, challenge_priority: bool, desired_rewards: list):
        # Applied immediately, even mid-run — otherwise toggling Enabled/
        # Priority/rewards after pressing Start had no effect until the next
        # queue restart, since execute_queue() only reads config once.
        self.bot._challenge_check = check_challenges
        self.bot._challenge_priority = challenge_priority
        self.bot._reward_files = desired_rewards

    def stop_macro(self):
        self.bot.halt()

    def pause_macro(self):
        self.bot.pause()

    def resume_macro(self):
        self.bot.resume()

    def get_status(self) -> dict:
        return self.bot.get_info()

    def get_trait_state(self) -> dict:
        return self.bot.get_trait_state()

    def get_hotkeys(self) -> dict:
        data = cfg.load()
        keys = dict(HOTKEY_DEFAULTS)
        keys.update(data.get("hotkeys", {}))
        return keys

    def set_hotkey(self, action: str, key: str) -> dict:
        if action not in HOTKEY_ACTIONS or not key:
            return {"ok": False}
        data = cfg.load()
        keys = dict(HOTKEY_DEFAULTS)
        keys.update(data.get("hotkeys", {}))
        keys[action] = key.lower()
        data["hotkeys"] = keys
        cfg.save(data)
        if self._on_hotkeys_changed:
            self._on_hotkeys_changed(keys)
        return {"ok": True}

    def reset_hotkey(self, action: str) -> dict:
        if action not in HOTKEY_ACTIONS:
            return {"ok": False}
        data = cfg.load()
        keys = dict(HOTKEY_DEFAULTS)
        keys.update(data.get("hotkeys", {}))
        keys[action] = HOTKEY_DEFAULTS[action]
        data["hotkeys"] = keys
        cfg.save(data)
        if self._on_hotkeys_changed:
            self._on_hotkeys_changed(keys)
        return {"ok": True, "key": HOTKEY_DEFAULTS[action]}

    def toggle_hide(self):
        if self._hidden:
            self.restore_from_tray()
        else:
            self.hide_to_tray()

    def hide_to_tray(self):
        if self._hidden or not self._window:
            return
        self._hidden = True
        window = self._window

        if self.bot._docked:
            # Roblox is docked in the window — only collapse the macro panel,
            # keep the game visible instead of hiding the whole window.
            window.evaluate_js("window.__hideMacroPanel && window.__hideMacroPanel()")

            def _shrink():
                time.sleep(0.28)
                window.resize(FIXED_WIN_W + 16, GUI_HEIGHT + 39)

            threading.Thread(target=_shrink, daemon=True).start()
        else:
            window.hide()

        tray.add_icon(ICO_PATH, "Cream's Macro (panel hidden) — click to restore", self.restore_from_tray)

    def restore_from_tray(self):
        if not self._hidden or not self._window:
            return
        self._hidden = False
        tray.remove_icon()

        if self.bot._docked:
            self._window.resize(GUI_WIDTH_FULL + 16, GUI_HEIGHT + 39)
            self._window.evaluate_js("window.__showMacroPanel && window.__showMacroPanel()")
        else:
            self._window.show()

    def set_trait_count(self, stage_key: str, count: int):
        self.bot.set_trait_count(stage_key, count)

    def position_roblox(self):
        self.bot.dock_game()

    def launch_roblox(self):
        self.bot.launch_game()

    def rejoin_game(self):
        threading.Thread(target=lambda: (
            self.bot.rejoin() and self._expand()
        ), daemon=True).start()

    def load_settings(self) -> dict:
        return cfg.load()

    def save_webhook(self, url: str, enabled: bool):
        data = cfg.load()
        data["webhook_url"] = url
        data["webhook_enabled"] = enabled
        cfg.save(data)

    def save_settings_full(self, data: dict):
        existing = cfg.load()
        existing.update(data)
        cfg.save(existing)

    def get_loadouts(self) -> dict:
        return cfg.list_loadouts()

    def save_loadout(self, name: str, tasks: list):
        cfg.save_loadout_file(name, tasks)

    def delete_loadout(self, name: str):
        cfg.delete_loadout_file(name)

    def export_loadout(self, name: str, tasks: list) -> dict:
        if not self._window:
            return {"ok": False}
        try:
            os.makedirs(cfg.LOADOUT_DIR, exist_ok=True)
        except OSError:
            pass
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=cfg.LOADOUT_DIR,
            save_filename=f"{name}.json",
            file_types=("JSON Files (*.json)", "All files (*.*)"),
        )
        if not result:
            return {"ok": False}
        path = result if isinstance(result, str) else result[0]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": name, "tasks": tasks}, f, indent=2)
            return {"ok": True}
        except OSError:
            return {"ok": False}

    def import_loadout(self) -> dict:
        if not self._window:
            return {"ok": False}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=cfg.LOADOUT_DIR if os.path.isdir(cfg.LOADOUT_DIR) else "",
            file_types=("JSON Files (*.json)", "All files (*.*)"),
        )
        if not result:
            return {"ok": False}
        path = result[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"ok": False}

        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, list) or not tasks:
            return {"ok": False}
        name = (payload.get("name") if isinstance(payload, dict) else None) \
            or os.path.splitext(os.path.basename(path))[0]

        cfg.save_loadout_file(name, tasks)
        return {"ok": True, "name": name, "tasks": tasks}

    def get_reward_files(self) -> list:
        files = set()
        if os.path.isdir(REWARD_DIR):
            files.update(f for f in os.listdir(REWARD_DIR) if f.lower().endswith(".png"))
        try:
            from core.asset_data import ASSETS
            for key in ASSETS:
                if key.startswith("rewards/") and key.lower().endswith(".png"):
                    files.add(key.split("/", 1)[1])
        except ImportError:
            pass
        return sorted(files)

    def get_reward_icons(self) -> dict:
        icon_map = {
            "stat_reroll.png": "Icons/Stat.png",
            "trait_reroll.png": "Icons/Trait.png",
            "gem.png": "Icons/Gem.png",
        }
        result = {}
        try:
            from core.asset_data import ASSETS
            for reward_file, asset_key in icon_map.items():
                if asset_key in ASSETS:
                    result[reward_file] = ASSETS[asset_key]
        except ImportError:
            pass
        return result

    def get_logs(self) -> list:
        return self.logger.get_recent(20)

    def get_version(self) -> str:
        return VERSION

    def open_github(self):
        import webbrowser
        from core.version import GITHUB_REPO
        webbrowser.open(f"https://github.com/{GITHUB_REPO}")

    def open_youtube(self):
        import webbrowser
        webbrowser.open("https://www.youtube.com/@Cweamya")

    def open_discord(self):
        import webbrowser
        webbrowser.open("https://discord.gg/FwU6ppjKNf")

    def get_display_scale(self) -> int:
        return wm.get_display_scale_percent()

    def open_display_settings(self):
        try:
            os.startfile("ms-settings:display")
        except OSError:
            pass

    def check_update(self) -> dict:
        result = check_for_update(self.logger)
        return result if result else {}

    def do_update(self, url: str) -> dict:
        def on_progress(pct):
            if self._window:
                self._window.evaluate_js(f"onUpdateProgress({pct})")
        path = download_update(url, callback=on_progress)
        if path:
            self.bot.halt()
            self.bot.undock_game()
            keyboard.unhook_all()
            apply_update_and_restart(path)
            return {"ok": True}
        return {"ok": False}

    def validate_webhook(self, url: str) -> dict:
        if not url:
            return {"valid": False, "reason": "empty"}
        prefixes = (
            "https://discord.com/api/webhooks/",
            "https://canary.discord.com/api/webhooks/",
            "https://ptb.discord.com/api/webhooks/",
        )
        prefix = next((p for p in prefixes if url.startswith(p)), None)
        if not prefix:
            return {"valid": False, "reason": "not_discord"}
        parts = url[len(prefix):].split("/")
        if len(parts) < 2 or not parts[0].isdigit():
            return {"valid": False, "reason": "bad_format"}
        return {"valid": True, "reason": "ok"}

    def start_roblox_poll(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        def _poll():
            while True:
                hwnd = wm.find_roblox_window()
                if hwnd:
                    self.bot._hwnd = hwnd
                    self._expand()
                    time.sleep(0.3)
                    if self.bot.gui_hwnd:
                        self.bot._dock_game()
                    break
                time.sleep(2)
        self._poll_thread = threading.Thread(target=_poll, daemon=True)
        self._poll_thread.start()

    def _expand(self):
        if self._window:
            self._window.resize(GUI_WIDTH_FULL + 16, GUI_HEIGHT + 39)
            self._window.move(0, 0)


def _find_gui(title: str) -> int:
    for _ in range(20):
        hwnd = wm.find_window(title)
        if hwnd:
            return hwnd
        time.sleep(0.25)
    return 0


def main():
    api = Api()
    ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")

    screen_w, screen_h = wm.get_screen_size()
    start_w = GUI_WIDTH_SMALL + 16
    start_h = GUI_HEIGHT_COMPACT
    start_x = (screen_w - start_w) // 2
    start_y = (screen_h - start_h) // 2

    window = webview.create_window(
        GUI_TITLE,
        url=ui_path,
        js_api=api,
        width=start_w,
        height=start_h,
        x=start_x,
        y=start_y,
        resizable=False,
        on_top=True,
        text_select=False,
    )
    api.set_window(window)

    def _register_hotkeys(keys: dict):
        keyboard.unhook_all()
        actions = {
            "stop": api.bot.halt,
            "pause": lambda: api.bot.resume() if api.bot.paused else api.bot.pause(),
            "hide": api.toggle_hide,
        }
        for action, fn in actions.items():
            key = keys.get(action) or HOTKEY_DEFAULTS[action]
            try:
                keyboard.add_hotkey(key, fn, suppress=False)
            except (ValueError, ImportError):
                keyboard.add_hotkey(HOTKEY_DEFAULTS[action], fn, suppress=False)

    def on_shown():
        _close_splash()
        gui_hwnd = _find_gui(GUI_TITLE)
        if gui_hwnd:
            api.bot.gui_hwnd = gui_hwnd
            _set_icon(gui_hwnd)

            roblox = wm.find_roblox_window()
            if roblox:
                api.bot._hwnd = roblox
                api._expand()
                time.sleep(0.3)
                api.bot._dock_game()
            else:
                api.start_roblox_poll()

        api.bot.start_anti_afk()
        _register_hotkeys(api.get_hotkeys())
        api._on_hotkeys_changed = _register_hotkeys

    def on_closing():
        tray.remove_icon()
        api.bot.stop_anti_afk()
        api.bot.halt()
        if api.bot._hwnd and wm.is_window(api.bot._hwnd):
            wm.set_parent(api.bot._hwnd, 0)
            wm.restore_borders(api.bot._hwnd)
            wm.move_window(api.bot._hwnd, 100, 100, FIXED_WIN_W + 16, FIXED_WIN_H + 39)
            api.bot._docked = False
        time.sleep(0.1)
        return True

    window.events.shown += on_shown
    window.events.closing += on_closing
    webview.start(debug=False)
    keyboard.unhook_all()


if __name__ == "__main__":
    main()
