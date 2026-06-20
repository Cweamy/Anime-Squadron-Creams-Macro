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

RAID_MAP = {
    "GT": "raid/gt.png",
    "Eclipse": "raid/eclipse.png",
}

RAID_ACT_BY_MAP = {
    "GT": {
        "Hidden Danger": "raid/hidden_danger.png",
        "Saiyan Hunt": "raid/saiyan_hunt.png",
        "Ruler Dragon": "raid/ruler_dragon.png",
        "The Ultimate Evil": "raid/ultimate_evil.png",
    },
    "Eclipse": {
        "Golden Age": "raid/golden_age.png",
        "Golden Age 2": "raid/golden_age_2.png",
        "Golden Age 3": "raid/golden_age_3.png",
        "The Eclipse": "raid/the_eclipse.png",
    },
}

SQUAD_STORY_MAP = {
    "GT City": "squadron/gt_city.png",
    "Marine Lobby": "squadron/marine_lobby.png",
    "Ninja Village": "squadron/ninja_village.png",
    "Eclipse": "squadron/eclipse.png",
}

SQUAD_CHAP_MAP = {
    "Chapter 1": "squadron/chapter1.png",
    "Chapter 2": "squadron/chapter2.png",
    "Chapter 3": "squadron/chapter3.png",
    "Chapter 4": "squadron/chapter4.png",
}

STORY_INDEX_MAP = {
    "GT City": 1, "Marine Lobby": 2, "Ninja Village": 3,
    "Eclipse": 4,
}
