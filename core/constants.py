import os
import sys

if hasattr(sys, '_MEIPASS'):
    # PyInstaller onefile
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
elif getattr(sys, 'frozen', False) or "__compiled__" in dir():
    # Nuitka standalone/onefile
    BUNDLE_DIR = os.path.dirname(sys.executable)
    APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
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

INVASION_MAP = {
    "The Lava Continent": "invasion/the_lava_continent.png",
}

INVASION_ACT_BY_MAP = {
    "The Lava Continent": {
        "Ashfall Continent": "invasion/ashfall_continent.png",
        "Infernal Landmass": "invasion/infernal_landmass.png",
        "Magma Rift": "invasion/magma_rift.png",
        "Scorched Horizon": "invasion/scorched_horizon.png",
    },
}

SQUAD_STORY_MAP = {
    "GT City": "squadron/gt_city.png",
    "Marine Lobby": "squadron/marine_lobby.png",
    "Ninja Village": "squadron/ninja_village.png",
    "Eclipse": "squadron/eclipse.png",
    "The Ice Continent": "squadron/the_ice_continent.png",
}

SQUAD_CHAP_MAP = {
    "Chapter 1": "squadron/chapter1.png",
    "Chapter 2": "squadron/chapter2.png",
    "Chapter 3": "squadron/chapter3.png",
    "Chapter 4": "squadron/chapter4.png",
}

# Trait farm: per-stage daily drop limits, reset at 7:00 GMT+7 (= midnight UTC).
# Each task in the queue opts in individually ("Track Trait"); progress for a
# given stage is shared across every task that farms it.
TRAIT_LIMIT = 100
GAROU_LIMIT = 30
TRAIT_KEY_AIZEN = "Aizen"
TRAIT_KEY_GAROU = "Garou"
TRAIT_KEY_GT_ULTIMATE_EVIL = "GT — The Ultimate Evil"
TRAIT_KEY_ECLIPSE_THE_ECLIPSE = "Eclipse — The Eclipse"
TRAIT_STAGES = [
    (TRAIT_KEY_AIZEN, TRAIT_LIMIT),
    (TRAIT_KEY_GAROU, GAROU_LIMIT),
    (TRAIT_KEY_GT_ULTIMATE_EVIL, TRAIT_LIMIT),
    (TRAIT_KEY_ECLIPSE_THE_ECLIPSE, TRAIT_LIMIT),
]
TRAIT_DROP_IMGS = ("drop/2_Trait.png", "drop/1_Trait.png")  # check 2 before 1
TRAIT_DROP_THRESHOLD = 0.92

