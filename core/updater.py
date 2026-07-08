import os
import sys
import threading
import subprocess
import requests

from core.version import VERSION, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
# GitHub replaces spaces with dots in uploaded asset filenames, so the exe
# build_nuitka.py names "Anime Squadron Creams Macro.exe" actually ends up
# hosted as this — used as a best-effort fallback download link if the API
# call below is rate limited.
FALLBACK_EXE_NAME = "Anime.Squadron.Creams.Macro.exe"


def _parse_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def _latest_tag_via_redirect(logger=None) -> str | None:
    """github.com/OWNER/REPO/releases/latest 302-redirects to the tagged
    release page — reading the Location header off that redirect tells us
    the latest tag without ever touching api.github.com, which caps
    unauthenticated requests at 60/hour *per IP*. Many unrelated users can
    share a public IP (school/office networks, large-scale CGNAT some ISPs
    use), so that limit can get exhausted across a whole user base, not
    just from one person restarting the app a lot. Before this fix, a
    rate-limited (403) response looked identical to "already up to date",
    since the JSON call's non-200 status just returned None silently.
    """
    try:
        resp = requests.head(RELEASES_PAGE, allow_redirects=False, timeout=10)
        location = resp.headers.get("Location", "")
        if "/releases/tag/" in location:
            return location.rsplit("/releases/tag/", 1)[-1]
    except Exception as e:
        if logger:
            logger.log(f"Update check: redirect lookup failed - {e}")
    return None


def check_for_update(logger=None) -> dict | None:
    try:
        latest = _latest_tag_via_redirect(logger)
        if not latest:
            return None
        if _parse_version(latest) <= _parse_version(VERSION):
            return None

        # There's genuinely something newer — worth spending one real API
        # call (subject to the 60/hr limit) to get the exact asset URL and
        # release notes.
        try:
            resp = requests.get(API_URL, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
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
            if logger:
                logger.log(f"Update check: API returned {resp.status_code} "
                           f"(likely rate limited) — using a direct link instead")
        except Exception as e:
            if logger:
                logger.log(f"Update check: API call failed - {e}")

        # API call failed/rate limited, but the redirect already confirmed
        # a newer tag exists — still tell the user, with a best-effort
        # direct link instead of the exact asset metadata.
        return {
            "version": latest.lstrip("v"),
            "tag": latest,
            "notes": "",
            "download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{latest}/{FALLBACK_EXE_NAME}",
            "file_name": FALLBACK_EXE_NAME,
        }
    except Exception as e:
        if logger:
            logger.log(f"Update check failed: {e}")
        return None


def _exe_path() -> str:
    return os.path.abspath(sys.argv[0])


def download_update(url: str, callback=None) -> str | None:
    if not sys.argv[0].lower().endswith(".exe"):
        return None
    try:
        current_exe = _exe_path()
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
    current_exe = _exe_path()
    old_exe = current_exe + ".old"
    batch = os.path.join(os.path.dirname(current_exe), "_update.bat")
    exe_dir = os.path.dirname(current_exe)
    pid = os.getpid()
    exe_name = os.path.basename(current_exe)
    with open(batch, "w") as f:
        f.write("@echo off\n")
        f.write(f'taskkill /F /IM "{exe_name}" >nul 2>&1\n')
        f.write(f':waitloop\n')
        f.write(f'timeout /t 2 /nobreak >nul\n')
        f.write(f'tasklist /FI "IMAGENAME eq {exe_name}" /NH 2>nul | findstr /i "{exe_name}" >nul\n')
        f.write(f'if not errorlevel 1 goto waitloop\n')
        f.write("timeout /t 2 /nobreak >nul\n")
        # Clean leftover extraction folders (PyInstaller _MEI*, Nuitka onefile_*)
        f.write(f'for /d %%i in ("%TEMP%\\_MEI*") do rd /s /q "%%i" >nul 2>&1\n')
        f.write(f'for /d %%i in ("%TEMP%\\onefile_*") do rd /s /q "%%i" >nul 2>&1\n')
        f.write(f'if exist "{old_exe}" del /f "{old_exe}"\n')
        f.write(f'move /y "{current_exe}" "{old_exe}"\n')
        f.write(f'move /y "{new_exe_path}" "{current_exe}"\n')
        f.write(f'cd /d "{exe_dir}"\n')
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
