"""
Cream's Macro | Anime Squadron
Run:  python main.py
Deps: pip install -r requirements.txt
"""

import os
import time
import ctypes
import threading

import webview
import keyboard

from core import window as wm
from core.constants import REWARD_DIR, SCRIPT_DIR, FIXED_WIN_W, FIXED_WIN_H
from core.logger import Logger
from core.bot import GameBot
from core import settings as cfg
from core.version import VERSION
from core.updater import check_for_update, download_update, apply_update_and_restart

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

    def set_window(self, w):
        self._window = w

    def start_queue(self, tasks: list, config: dict):
        self.bot.execute_queue(tasks, config)

    def stop_macro(self):
        self.bot.halt()

    def get_status(self) -> dict:
        return self.bot.get_info()

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
        cfg.save(data)

    def get_loadouts(self) -> dict:
        data = cfg.load()
        return data.get("loadouts", {})

    def save_loadout(self, name: str, tasks: list):
        data = cfg.load()
        loadouts = data.get("loadouts", {})
        loadouts[name] = tasks
        data["loadouts"] = loadouts
        cfg.save(data)

    def delete_loadout(self, name: str):
        data = cfg.load()
        loadouts = data.get("loadouts", {})
        loadouts.pop(name, None)
        data["loadouts"] = loadouts
        cfg.save(data)

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

    def get_version(self) -> str:
        return VERSION

    def check_update(self) -> dict:
        result = check_for_update()
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
        if not url.startswith("https://discord.com/api/webhooks/"):
            return {"valid": False, "reason": "not_discord"}
        parts = url.replace("https://discord.com/api/webhooks/", "").split("/")
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

    def on_shown():
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

        keyboard.add_hotkey("F2", api.bot.halt, suppress=False)

    def on_closing():
        api.bot.halt()
        api.bot.undock_game()
        time.sleep(0.2)
        return True

    window.events.shown += on_shown
    window.events.closing += on_closing
    webview.start(debug=False)
    api.bot.undock_game()
    keyboard.unhook_all()


if __name__ == "__main__":
    main()
