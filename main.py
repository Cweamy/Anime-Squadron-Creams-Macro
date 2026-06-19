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
from core.updater import check_for_update, download_update, apply_update_and_restart, check_update_async

wm.set_dpi_aware()

GUI_TITLE = "Cream's Macro | Anime Squadron"
PANEL_WIDTH = 350
GUI_WIDTH_FULL = FIXED_WIN_W + PANEL_WIDTH
GUI_WIDTH_SMALL = PANEL_WIDTH
GUI_HEIGHT = FIXED_WIN_H
ICO_PATH = os.path.join(SCRIPT_DIR, "logo.ico")


def _set_icon(hwnd: int):
    if not os.path.exists(ICO_PATH):
        return
    user32 = ctypes.windll.user32
    hicon = user32.LoadImageW(0, ICO_PATH, 1, 0, 0, 0x0010)
    if hicon:
        user32.SendMessageW(hwnd, 0x0080, 0, hicon)
        user32.SendMessageW(hwnd, 0x0080, 1, hicon)


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

    window = webview.create_window(
        GUI_TITLE,
        url=ui_path,
        js_api=api,
        width=GUI_WIDTH_SMALL + 16,
        height=GUI_HEIGHT + 39,
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
        return True

    window.events.shown += on_shown
    window.events.closing += on_closing
    webview.start(debug=False)
    keyboard.unhook_all()


if __name__ == "__main__":
    main()
