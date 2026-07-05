<p align="center">
  <img src="logo.png" width="120" alt="Cream's Macro">
</p>

<h1 align="center">Cream's Macro — Anime Squadron</h1>

<p align="center">
  <strong>Auto-farming macro for Roblox Anime Squadron</strong><br>
  Built with Python, OpenCV, and pywebview
</p>

<p align="center">
  <a href="https://github.com/Cweamy/Anime-Squadron-Creams-Macro/releases/latest">
    <img src="https://img.shields.io/github/v/release/Cweamy/Anime-Squadron-Creams-Macro?style=flat-square&color=blue" alt="Latest Release">
  </a>
  <a href="https://github.com/Cweamy/Anime-Squadron-Creams-Macro/releases/latest">
    <img src="https://img.shields.io/github/downloads/Cweamy/Anime-Squadron-Creams-Macro/total?style=flat-square&color=green" alt="Downloads">
  </a>
  <a href="https://github.com/Cweamy/Anime-Squadron-Creams-Macro/actions/workflows/build.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Cweamy/Anime-Squadron-Creams-Macro/build.yml?style=flat-square" alt="Build Status">
  </a>
</p>

<p align="center">
  <a href="https://discord.gg/FwU6ppjKNf">Discord</a> · <a href="https://www.youtube.com/@Cweamya">YouTube</a> · <a href="https://github.com/Cweamy/Anime-Squadron-Creams-Macro/releases/latest">Download</a>
</p>

---

<p align="center">
  <img src="preview.png" alt="Cream's Macro Preview" width="800">
</p>

## Features

- **Task Queue** — Queue multiple farming tasks with drag-and-drop reordering and looping support.
- **Loadout System** — Built-in presets (Secret Mats, Mythic Mats, Gold & Trait Farm, etc.) and custom loadouts you can save and stack.
- **Game Modes** — Challenge, Raid, Invasion, Squadron, and Story with full stage/map/chapter/difficulty selection.
- **Raid Maps** — GT (Hidden Danger, Saiyan Hunt, Ruler Dragon, The Ultimate Evil) and Eclipse (Golden Age 1–3, The Eclipse).
- **Invasion** — The Lava Continent (Ashfall Continent, Infernal Landmass, Magma Rift, Scorched Horizon).
- **Squadron/Story Maps** — GT City, Marine Lobby, Ninja Village, Eclipse — with up to 10 acts (Story) or 4 chapters (Squadron).
- **Challenge Reward Scanner** — Automatically checks challenge rewards every 30 minutes. Select desired rewards (Stat Reroll, Trait Reroll) and the macro farms them until the slot resets. Priority mode leaves the current battle instantly when rewards refresh.
- **Live Dashboard** — Win rate, run count, V/D stats, session timer, and task progress bar — all updating in real time.
- **Log Viewer** — Built-in live log feed for debugging.
- **Discord Webhooks** — Notifications with win/loss stats, battle time, task progress, session time, and optional screenshots (Roblox, fullscreen, or none).
- **Auto Reconnect** — Detects disconnects and crashes, automatically rejoins via deep link.
- **Auto Update** — Checks GitHub Releases on startup with one-click update.
- **Docked UI** — Roblox docks directly into the macro panel for a clean single-window experience.
- **Instant Stop** — Press `F2` or click Stop to halt immediately, even mid-battle.

## Download

Grab the latest `.exe` from [**Releases**](https://github.com/Cweamy/Anime-Squadron-Creams-Macro/releases/latest) — no install or Python required.

## Usage

1. Download and run `Anime Squadron Creams Macro.exe`
2. The macro will wait for Roblox — click **Launch Game** or open Anime Squadron manually
3. Roblox docks into the macro window automatically
4. Add tasks to the queue — pick mode, map, act, difficulty, and repeat count
5. Click **Start** — the macro handles everything from there

### Game Modes

| Mode | Maps | Acts / Chapters |
|------|------|-----------------|
| **Raid** | GT, Eclipse | GT: Hidden Danger, Saiyan Hunt, Ruler Dragon, The Ultimate Evil · Eclipse: Golden Age 1–3, The Eclipse |
| **Invasion** | The Lava Continent | Ashfall Continent, Infernal Landmass, Magma Rift, Scorched Horizon |
| **Squadron** | GT City, Marine Lobby, Ninja Village, Eclipse | Chapter 1–4 |
| **Story** | GT City, Marine Lobby, Ninja Village, Eclipse | Chapter 1–10 |
| **Challenge** | Regular, Aizen, Garou | Normal / Hard (Aizen & Garou) |

Each task supports Normal or Hard difficulty and any repeat count. Enable **Loop** to restart the queue after all tasks finish.

### Challenge Rewards

Select desired rewards under the Challenge Rewards section. When enabled:

- The macro checks the challenge tab every 30 minutes between runs
- If a desired reward (Stat Reroll, Trait Reroll) is found, it farms the challenge until the slot resets
- When the slot changes, it rechecks for desired rewards in the new slot
- **Priority mode** — leaves the current battle immediately when a reward refresh happens

Challenge battles are tracked separately and don't count toward your task progress.

### Loadouts

Built-in presets for common farming setups:

| Preset | Tasks |
|--------|-------|
| Gold & Trait Farm | GT City Ch.1 ×999 (loop, trait reroll check) |
| Secret Mats | Story GT/Marine/Ninja Ch.10 Hard ×15 each |
| Mythic Mats | Story GT/Marine/Ninja Ch.9 Hard ×10 each |
| Legendary Mats | Story GT/Marine/Ninja Ch.7 Hard ×10 each |
| Epic Mats | Story GT/Marine/Ninja Ch.5 Hard ×10 each |
| Rare Mats | Story GT/Marine/Ninja Ch.3 Hard ×10 each |

Save your own custom loadouts and use the **Append** dropdown to stack multiple loadouts together.

### Discord Webhook

1. Create a webhook in your Discord server (Server Settings → Integrations → Webhooks)
2. Copy the webhook URL
3. Click **Paste** in the macro's Webhook section

Each run sends an embed with mode, win rate, battle time, task progress, session time, and an optional screenshot. Supports silent mode (no notification ping).

### Hotkeys

| Key | Action |
|-----|--------|
| `F2` | Emergency stop |
| `F3` | Pause / Resume |

## Building from Source

```bash
git clone https://github.com/Cweamy/Anime-Squadron-Creams-Macro.git
cd Anime-Squadron-Creams-Macro

pip install -r requirements.txt
pip install pyinstaller

# Generate embedded assets (only needed if you modify images in assets/)
python generate_assets.py

# Build exe
python build.py
# Output: dist/Anime Squadron Creams Macro.exe
```

### Requirements

- Python 3.10+
- Windows 10/11
- Dependencies: `pywebview`, `mss`, `opencv-python-headless`, `numpy`, `keyboard`, `requests`

## How It Works

The macro uses **screen capture** (mss) and **template matching** (OpenCV) to detect UI elements in the Roblox window. It identifies the current scene (lobby, stage select, battle, results, etc.) and navigates through menus by clicking detected buttons. Victory/defeat is determined by HSV color sampling on the results screen. No memory reading or injection — purely vision-based.

## License

This project is provided as-is for personal use.
