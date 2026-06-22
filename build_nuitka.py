"""
Build the exe with Nuitka (compiles Python to C — smaller, faster, lower AV
false-positive rate than PyInstaller).

Requires a python.org CPython (NOT the Microsoft Store build — Nuitka rejects it):
    py -3.12 -m pip install nuitka
    py -3.12 build_nuitka.py

Output: dist-nuitka/Anime Squadron Creams Macro.exe
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE_NAME = "Anime Squadron Creams Macro.exe"

# Stdlib / packages we never touch — kept out of the compile entirely.
NOFOLLOW = [
    "tkinter", "unittest", "pydoc", "doctest", "pdb", "test", "tests",
    "distutils", "setuptools", "pip", "pkg_resources", "lib2to3",
    "ensurepip", "venv", "sqlite3", "xmlrpc", "turtledemo",
    # webview backends we don't use (we run WinForms + Edge Chromium)
    "webview.platforms.cef", "webview.platforms.gtk",
    "webview.platforms.cocoa", "webview.platforms.android",
    "webview.platforms.mshtml",
]

# Prebuilt DLLs pulled in by dependencies that our usage never exercises.
#   opencv_videoio_ffmpeg — 28 MB; only needed for VideoCapture/VideoWriter,
#   we only do image template matching + PNG encode/decode.
NOINCLUDE_DLLS = [
    "*opencv_videoio_ffmpeg*",
]

# We disable Nuitka's bundled pywebview plugin because (as of 4.1.2) it forgets
# to include 'webview.platforms.win32', which winforms.py imports unconditionally
# — causing a runtime "pythonnet cannot be loaded" crash. We include the needed
# backend modules ourselves instead. (The webview DLLs are handled by the
# separate 'dll-files' plugin, so nothing is lost.)
INCLUDE_MODULES = [
    "core.asset_data",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.platforms.win32",
]

cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--enable-plugin=no-qt",          # we use the WebView2/WinForms backend, not Qt
    "--disable-plugin=pywebview",     # buggy win32 exclusion — we include backends manually
    "--windows-console-mode=disable",
    f"--windows-icon-from-ico={os.path.join(ROOT, 'logo.ico')}",
    "--include-data-dir=ui=ui",
    "--include-data-files=logo.png=logo.png",
    "--include-data-files=logo.ico=logo.ico",
    "--python-flag=no_site",
    "--python-flag=no_asserts",
    "--python-flag=no_docstrings",
    "--lto=no",
    "--remove-output",
    "--assume-yes-for-downloads",
    f"--output-filename={EXE_NAME}",
    "--output-dir=dist-nuitka",
]

for mod in INCLUDE_MODULES:
    cmd += [f"--include-module={mod}"]
for mod in NOFOLLOW:
    cmd += [f"--nofollow-import-to={mod}"]
for dll in NOINCLUDE_DLLS:
    cmd += [f"--noinclude-dlls={dll}"]

cmd.append(os.path.join(ROOT, "main.py"))

print("Building exe with Nuitka...")
result = subprocess.run(cmd, cwd=ROOT)
if result.returncode != 0:
    print("\nBuild FAILED!")
    sys.exit(1)
print(f"\nDone! Check dist-nuitka/{EXE_NAME}")
