"""
Build the exe. Run:  python build.py
Requires: pip install pyinstaller
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

EXCLUDE_MODULES = [
    "tkinter", "_tkinter", "unittest", "test", "tests",
    "setuptools", "pip", "pkg_resources",
    "xmlrpc",
    "pydoc", "doctest", "optparse",
    "pdb", "profile", "cProfile",
    "lib2to3", "ensurepip", "venv", "turtledemo",
    "sqlite3",
    "cv2.gapi", "cv2.misc", "cv2.utils",
]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "Anime Squadron Creams Macro",
    "--icon", os.path.join(ROOT, "logo.ico"),
    "--add-data", f"{os.path.join(ROOT, 'ui')};ui",
    "--add-data", f"{os.path.join(ROOT, 'logo.png')};.",
    "--add-data", f"{os.path.join(ROOT, 'logo.ico')};.",
    "--hidden-import", "core.asset_data",
    "--noupx",
    "--noconfirm",
]

for mod in EXCLUDE_MODULES:
    cmd += ["--exclude-module", mod]

cmd.append(os.path.join(ROOT, "main.py"))

print("Building exe...")
result = subprocess.run(cmd, cwd=ROOT)
if result.returncode != 0:
    print("\nBuild FAILED!")
    sys.exit(1)
print("\nDone! Check dist/Anime Squadron Creams Macro.exe")
