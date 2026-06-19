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

---

<p align="center">
  <img src="preview.png" alt="Cream's Macro Preview" width="800">
</p>

## Features

- **Task Queue** — Queue multiple farming tasks with different modes, stages, and repeat counts. Supports looping.
- **Game Modes** — Challenge, Raid, Squadron, Story, and Aizen — each with full stage/chapter/difficulty selection.
- **Auto Reconnect** — Detects disconnects and crashes, automatically rejoins via deep link.
- **Discord Webhooks** — Get notified on every run with win/loss stats, battle time, screenshots, and task progress.
- **Challenge Reward Scanner** — Auto-checks challenge rewards every 30 minutes and claims matching rewards.
- **Auto Update** — Checks GitHub Releases on startup and one-click updates to the latest version.
- **Docked UI** — The Roblox window docks directly into the macro panel for a clean single-window experience.
- **Hotkey** — Press `F2` at any time to emergency stop.

## Download

Grab the latest `.exe` from [**Releases**](https://github.com/Cweamy/Anime-Squadron-Creams-Macro/releases/latest) — no install or Python required.

## Usage

1. Download and run `Anime Squadron Creams Macro.exe`
2. The macro will wait for Roblox — click **Launch Game** or open Anime Squadron manually
3. Roblox docks into the macro window automatically
4. Add tasks to the queue (mode, stage, difficulty, repeat count)
5. Click **Start**

### Task Queue

| Mode | Options |
|------|---------|
| **Challenge** | Regular challenges |
| **Raid** | Hidden Danger, Saiyan Hunt, Ruler Dragon, The Ultimate Evil |
| **Squadron** | GT City / Marine Lobby / Ninja Village + Chapter 1–4 |
| **Story** | GT City / Marine Lobby / Ninja Village + Chapter 1–10 |
| **Aizen** | Normal / Hard |

Each task can be set to Normal or Hard difficulty and repeated any number of times. Enable **Loop** to restart the queue after all tasks finish.

### Discord Webhook

1. Create a webhook in your Discord server (Server Settings → Integrations → Webhooks)
2. Copy the webhook URL
3. Click **Paste** in the macro's Webhook section

Each run sends an embed with mode, win rate, battle time, task progress, session time, and an optional screenshot.

### Hotkeys

| Key | Action |
|-----|--------|
| `F2` | Emergency stop |

## Building from Source

```bash
# Clone
git clone https://github.com/Cweamy/Anime-Squadron-Creams-Macro.git
cd Anime-Squadron-Creams-Macro

# Install dependencies
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

The macro uses **screen capture** (mss) and **template matching** (OpenCV) to detect UI elements in the Roblox window. It identifies the current scene (lobby, stage select, battle, results, etc.) and navigates through menus by clicking the detected buttons. No memory reading or injection — purely vision-based.

## License

This project is provided as-is for personal use.
