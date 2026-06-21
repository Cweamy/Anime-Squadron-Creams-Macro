"""
Reads all PNGs from all subdirectories under assets/, encodes them as
base64 strings, and writes core/asset_data.py.

Run this once before building the exe:
    python generate_assets.py

After running, the images are baked into the code — no separate files needed at runtime.
"""
import os
import base64
import glob

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
OUTPUT = os.path.join(os.path.dirname(__file__), "core", "asset_data.py")

EXCLUDE = {"icons"}

DIRS = []
for _d in os.listdir(ASSET_DIR):
    if _d.lower() in EXCLUDE:
        continue
    _full = os.path.join(ASSET_DIR, _d)
    if os.path.isdir(_full):
        DIRS.append(_full)


def main():
    entries = {}
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for img_path in sorted(glob.glob(os.path.join(d, "*.png"))):
            name = os.path.basename(img_path)
            if name.startswith("_"):
                continue
            rel = os.path.relpath(img_path, ASSET_DIR).replace("\\", "/")
            with open(img_path, "rb") as f:
                data = f.read()
            entries[rel] = base64.b64encode(data).decode("ascii")
            print(f"  Packed: {rel} ({len(data)} bytes)")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("# Auto-generated — do not edit. Run generate_assets.py to rebuild.\n")
        f.write("ASSETS = {\n")
        for key, b64 in entries.items():
            f.write(f'    "{key}": (\n')
            for i in range(0, len(b64), 76):
                f.write(f'        "{b64[i:i+76]}"\n')
            f.write("    ),\n")
        f.write("}\n")

    print(f"\nWrote {len(entries)} assets to {OUTPUT}")


if __name__ == "__main__":
    main()
