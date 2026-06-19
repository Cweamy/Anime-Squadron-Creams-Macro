"""
Build the exe. Run:  python build.py
Requires: pip install pyinstaller
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "Anime Squadron Cream's Macro",
    "--icon", os.path.join(ROOT, "logo.ico"),
    "--add-data", f"{os.path.join(ROOT, 'ui')};ui",
    "--add-data", f"{os.path.join(ROOT, 'logo.png')};.",
    "--add-data", f"{os.path.join(ROOT, 'logo.ico')};.",
    "--hidden-import", "core.asset_data",
    "--noconfirm",
    os.path.join(ROOT, "main.py"),
]

print("Building exe...")
print(" ".join(cmd))
result = subprocess.run(cmd, cwd=ROOT)
if result.returncode != 0:
    print("\nBuild FAILED!")
    sys.exit(1)
print("\nDone! Check dist/Anime Squadron Cream's Macro.exe")
