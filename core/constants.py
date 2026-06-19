import os
import sys

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    APP_DIR = BUNDLE_DIR

SCRIPT_DIR = BUNDLE_DIR
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")
NAV_DIR = os.path.join(ASSET_DIR, "nav")
REWARD_DIR = os.path.join(ASSET_DIR, "rewards")

GAME_TITLE = "Roblox"
PLACE_ID = "71132543521245"
FIXED_WIN_W = 1152
FIXED_WIN_H = 756
LOOP_INTERVAL_MS = 50
CLICK_DELAY_MS = 50
IMG_THRESHOLD = 0.80
IMG_THRESHOLD_STRICT = 0.88
IMG_THRESHOLD_RELAXED = 0.70
MAX_STATE_RETRIES = 20
REFRESH_INTERVAL_MS = 1800000  # 30 minutes

RAID_ACT_MAP = {
    "Hidden Danger": "raid_act1.png",
    "Saiyan Hunt": "raid_act2.png",
    "Ruler Dragon": "raid_act3.png",
    "The Ultimate Evil": "raid_act4.png",
}

SQUAD_STORY_MAP = {
    "GT City": "squadron_story1.png",
    "Marine Lobby": "squadron_story2.png",
    "Ninja Village": "squadron_story3.png",
}

SQUAD_CHAP_MAP = {
    "Chapter 1": "squadron_ch1.png",
    "Chapter 2": "squadron_ch2.png",
    "Chapter 3": "squadron_ch3.png",
    "Chapter 4": "squadron_ch4.png",
}

STORY_INDEX_MAP = {"GT City": 1, "Marine Lobby": 2, "Ninja Village": 3}
