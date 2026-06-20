import os
import sys
import threading
import subprocess
import requests

from core.version import VERSION, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def check_for_update() -> dict | None:
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        latest = data.get("tag_name", "")
        if not latest:
            return None
        if _parse_version(latest) <= _parse_version(VERSION):
            return None
        exe_asset = None
        for asset in data.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                exe_asset = asset
                break
        return {
            "version": latest.lstrip("v"),
            "tag": latest,
            "notes": data.get("body", ""),
            "download_url": exe_asset["browser_download_url"] if exe_asset else None,
            "file_name": exe_asset["name"] if exe_asset else None,
        }
    except Exception:
        return None


def download_update(url: str, callback=None) -> str | None:
    if not getattr(sys, "frozen", False):
        return None
    try:
        current_exe = sys.executable
        new_exe = current_exe + ".update"
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(new_exe, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if callback and total:
                    callback(int(downloaded / total * 100))
        return new_exe
    except Exception:
        return None


def apply_update_and_restart(new_exe_path: str):
    current_exe = sys.executable
    old_exe = current_exe + ".old"
    batch = os.path.join(os.path.dirname(current_exe), "_update.bat")
    with open(batch, "w") as f:
        f.write("@echo off\n")
        f.write("timeout /t 2 /nobreak >nul\n")
        f.write(f'if exist "{old_exe}" del /f "{old_exe}"\n')
        f.write(f'move /y "{current_exe}" "{old_exe}"\n')
        f.write(f'move /y "{new_exe_path}" "{current_exe}"\n')
        f.write(f'start "" "{current_exe}"\n')
        f.write(f'del /f "{old_exe}"\n')
        f.write(f'del "%~f0"\n')
    subprocess.Popen(
        ["cmd", "/c", batch],
        creationflags=0x08000000,
        close_fds=True,
    )
    os._exit(0)


def check_update_async(callback):
    def _run():
        result = check_for_update()
        if result:
            callback(result)
    threading.Thread(target=_run, daemon=True).start()
