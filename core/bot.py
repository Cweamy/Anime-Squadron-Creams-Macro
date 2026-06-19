"""
GameBot — automated farming engine for Anime Squadron.

Original sequential architecture: instead of a tick-based state machine,
the bot runs a blocking task loop where each step waits for its expected
screen transition before proceeding.
"""

import os
import time
import threading
from enum import Enum

from core.constants import (
    FIXED_WIN_W, FIXED_WIN_H, PLACE_ID,
    RAID_ACT_MAP, SQUAD_STORY_MAP, SQUAD_CHAP_MAP, STORY_INDEX_MAP,
    NAV_DIR,
)
from core.screen import Screen
from core.mouse import Mouse
from core.logger import Logger
from core import window as wm
from core import webhook as notify


class Scene(Enum):
    UNKNOWN = 0
    LOBBY = 1
    PLAY_AREA = 2
    STAGE_SELECT = 3
    IN_ROOM = 4
    BATTLING = 5
    VICTORY = 6
    DEFEAT = 7
    RESULTS = 8
    DISCONNECTED = 9


PHASE_LABELS = {
    "idle": "Idle",
    "waiting": "Waiting for Roblox",
    "rejoining": "Rejoining...",
    "scanning": "Scanning",
    "lobby": "Entering lobby",
    "opening_menu": "Opening room",
    "selecting_tab": "Selecting tab",
    "picking_stage": "Picking stage",
    "setting_diff": "Setting difficulty",
    "creating_room": "Creating room",
    "starting": "Starting battle",
    "battling": "In battle",
    "post_battle": "Processing result",
    "challenge_check": "Checking rewards",
    "returning": "Returning to mode",
}

STAGE_TABS = ("challenge_tab.png", "raid_tab.png", "squadron_tab.png",
              "story_tab.png", "friends_only_btn.png")

BATTLE_END_IMGS = ("victory_banner.png", "defeat_banner.png",
                   "retry_btn.png", "replay_btn.png")

BATTLE_ACTIVE_IMGS = ("team_btn.png",) + BATTLE_END_IMGS


class GameBot:
    def __init__(self, logger: Logger):
        self.log = logger
        self.vision = Screen(logger)
        self.input = Mouse()

        self.active = False
        self._phase = "idle"
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()

        # Window
        self._hwnd = 0
        self.gui_hwnd = 0
        self._docked = False
        self._rx = self._ry = 0
        self._rw = FIXED_WIN_W
        self._rh = FIXED_WIN_H

        # Config (set per queue)
        self._webhook_url = ""
        self._webhook_on = True
        self._webhook_silent = False
        self._screenshot_mode = "roblox"
        self._challenge_check = False
        self._reward_files: list[str] = []
        self._loop_queue = False

        # Stats
        self.victories = 0
        self.defeats = 0
        self.runs = 0
        self._task_idx = 0
        self._task_total = 0
        self._task_runs = 0
        self._task_target = 0
        self._session_start = 0
        self._battle_start = 0
        self._battle_ms = 0
        self._last_notified_run = -1
        self._last_refresh_slot = -1

        # Current task config
        self._mode = ""
        self._detail = ""
        self._diff = ""
        self._raid_act = ""
        self._raid_diff = ""
        self._sq_story = ""
        self._sq_chap = ""
        self._sq_diff = ""
        self._st_idx = 1
        self._st_chap = 1
        self._st_diff = ""
        self._az_diff = ""

        self.on_update: callable = None

    # ══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════

    def execute_queue(self, tasks: list[dict], config: dict):
        if self.active:
            return
        self._hwnd = self._locate_game()
        if not self._hwnd:
            return

        self._webhook_url = config.get("webhook_url", "")
        self._webhook_on = config.get("webhook_enabled", True)
        self._webhook_silent = config.get("webhook_silent", False)
        self._screenshot_mode = config.get("screenshot_mode", "roblox")
        self._challenge_check = config.get("check_challenges", False)
        self._reward_files = config.get("desired_rewards", [])
        self._loop_queue = config.get("start_over", False)

        queue = [t for t in tasks if int(t.get("repeat", 0)) > 0]
        if not queue:
            return

        self.victories = self.defeats = self.runs = 0
        self._session_start = time.monotonic()
        self._last_refresh_slot = self._time_slot()
        self._last_notified_run = -1

        self.active = True
        self._halt.clear()
        self._dock_game()
        self._thread = threading.Thread(target=self._worker, args=(queue,), daemon=True)
        self._thread.start()

    def halt(self):
        self._halt.set()
        self.active = False
        self._phase = "idle"
        self._push()

    def get_info(self) -> dict:
        return {
            "state": PHASE_LABELS.get(self._phase, self._phase),
            "running": self.active,
            "roblox_found": bool(self._hwnd and wm.is_window(self._hwnd)),
            "run_count": self.runs,
            "victory_count": self.victories,
            "defeat_count": self.defeats,
            "use_task_queue": True,
            "current_task_index": self._task_idx + 1,
            "task_count": self._task_total,
            "task_run_count": self._task_runs,
            "task_run_target": self._task_target,
        }

    def dock_game(self):
        self._hwnd = self._locate_game()
        if self._hwnd:
            self._dock_game()

    def undock_game(self):
        if self._docked and self._hwnd and wm.is_window(self._hwnd):
            wm.set_parent(self._hwnd, 0)
            wm.restore_borders(self._hwnd)
            self._docked = False

    def launch_game(self):
        url = f"roblox://experiences/start?placeId={PLACE_ID}"
        self.log.log(f"Deep link: {url}")
        os.startfile(url)

    def rejoin(self):
        self._phase = "rejoining"
        self._push()
        self.launch_game()
        time.sleep(8)
        if not self._hwnd or not wm.is_window(self._hwnd):
            self.log.log("Rejoin: window gone, polling for new one")
            if not self._poll_for_game(90):
                self._phase = "idle"
                self._push()
                return False
        self._dock_game()
        self._phase = "idle"
        self._push()
        return True

    def poll_for_game(self, timeout=120):
        return self._poll_for_game(timeout)

    # ══════════════════════════════════════════════════════════════
    # WORKER — runs in background thread
    # ══════════════════════════════════════════════════════════════

    def _worker(self, queue: list[dict]):
        self._task_total = len(queue)
        try:
            while not self._halt.is_set():
                for idx, task in enumerate(queue):
                    if self._halt.is_set():
                        return
                    self._task_idx = idx
                    self._run_task(task)
                if not self._loop_queue:
                    break
            self._notify("ALL TASKS COMPLETE")
        except Exception as e:
            self.log.log(f"Worker error: {e}")
        finally:
            self.active = False
            self._phase = "idle"
            self._push()

    def _run_task(self, task: dict):
        self._apply_task(task)
        self._task_runs = 0

        while self._task_runs < self._task_target and not self._halt.is_set():
            self._ensure_game_alive()
            if self._halt.is_set():
                return

            self._navigate_to_battle()
            if self._halt.is_set():
                return

            outcome = self._watch_battle()

            self.runs += 1
            self._task_runs += 1
            if outcome == "victory":
                self.victories += 1
            elif outcome == "defeat":
                self.defeats += 1
            self._notify(outcome.upper() if outcome != "unknown" else "DEFEAT")

            if self._task_runs >= self._task_target:
                self._leave_results()
                return

            if self._should_check_rewards():
                self._do_challenge_check()
            else:
                self._replay_or_retry()

    # ══════════════════════════════════════════════════════════════
    # SCENE IDENTIFICATION
    # ══════════════════════════════════════════════════════════════

    def _read_scene(self, hint: str = "") -> Scene:
        """Identify current screen with a single capture."""
        if hint == "post_lobby":
            order = ["create_room_btn.png", *STAGE_TABS, "shop_icon.png"]
        else:
            order = [
                "shop_icon.png", "create_room_btn.png", *STAGE_TABS,
                "start_btn.png", "team_btn.png",
                "victory_banner.png", "defeat_banner.png",
                "retry_btn.png", "replay_btn.png", "reconnect_btn.png",
            ]

        hit = self.vision.find_first(order, self._rx, self._ry, self._rw, self._rh)
        if not hit:
            return Scene.UNKNOWN

        name = hit[0]
        if name == "shop_icon.png":
            return Scene.LOBBY
        if name == "create_room_btn.png":
            return Scene.PLAY_AREA
        if name in STAGE_TABS:
            return Scene.STAGE_SELECT
        if name == "start_btn.png":
            return Scene.IN_ROOM
        if name == "team_btn.png":
            return Scene.BATTLING
        if name in ("victory_banner.png", "defeat_banner.png",
                     "retry_btn.png", "replay_btn.png"):
            return Scene.RESULTS
        if name == "reconnect_btn.png":
            return Scene.DISCONNECTED
        return Scene.UNKNOWN

    # ══════════════════════════════════════════════════════════════
    # NAVIGATION — sequential, blocking steps
    # ══════════════════════════════════════════════════════════════

    def _navigate_to_battle(self):
        self._phase = "scanning"
        self._push()
        hint = ""

        for attempt in range(30):
            if self._halt.is_set():
                return
            self._refresh_bounds()

            if self._handle_disconnect():
                continue

            scene = self._read_scene(hint)
            hint = ""

            if scene == Scene.LOBBY:
                self._go_through_lobby()
                hint = "post_lobby"
            elif scene == Scene.PLAY_AREA:
                self._open_stage_menu()
            elif scene == Scene.STAGE_SELECT:
                self._select_and_start()
                return
            elif scene == Scene.IN_ROOM:
                self._click_start()
                return
            elif scene == Scene.BATTLING:
                return
            elif scene == Scene.RESULTS:
                self._replay_or_retry()
                return
            elif scene == Scene.DISCONNECTED:
                self._handle_disconnect()
            else:
                time.sleep(0.2)

    def _go_through_lobby(self):
        self._phase = "lobby"
        self._push()

        pos = self._see("play_btn.png")
        if pos:
            self._tap(pos, times=3, gap=60)
        else:
            shop = self._see("shop_icon.png")
            if shop:
                self._tap((shop[0], shop[1] + 130), times=3, gap=60)

        cr_x = self._rx + self._rw * 48 // 100
        cr_y = self._ry + self._rh * 79 // 100

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self._halt.is_set():
                return

            hit = self.vision.find_first(list(STAGE_TABS), self._rx, self._ry, self._rw, self._rh)
            if hit:
                self._select_and_start()
                return

            self._tap((cr_x, cr_y), times=1, gap=30)
            time.sleep(0.12)

    def _open_stage_menu(self):
        self._phase = "opening_menu"
        self._push()

        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see("create_room_btn.png")
            if pos:
                self._tap(pos, times=2, gap=80)
            else:
                cx = self._rx + self._rw * 48 // 100
                cy = self._ry + self._rh * 79 // 100
                self._tap((cx, cy), times=2, gap=80)

            found = self._spot(*STAGE_TABS, timeout=1.5)
            if found:
                self._select_and_start()
                return

    def _select_and_start(self):
        self._pick_tab()
        self._pick_stage()
        self._pick_difficulty()
        self._create_room()
        self._click_start()

    def _pick_tab(self):
        self._phase = "selecting_tab"
        self._push()

        tab_map = {
            "Challenge": "challenge_tab.png",
            "Raid": "raid_tab.png",
            "Squadron": "squadron_tab.png",
            "Story": "story_tab.png",
            "Aizen": "challenge_tab.png",
        }
        target = tab_map.get(self._mode, "challenge_tab.png")
        confirm_map = {
            "challenge_tab.png": lambda: self._see("challenge_detection.png") or self._see("regular_challenge_btn.png"),
            "raid_tab.png": lambda: any(self._see(f"raid_act{i}.png") for i in range(1, 5)),
            "squadron_tab.png": lambda: self._see("squadron_detection.png"),
            "story_tab.png": lambda: self._see("story_detection.png"),
        }
        confirm = confirm_map.get(target)

        for _ in range(8):
            if self._halt.is_set():
                return
            if confirm and confirm():
                return

            pos = self._see(target)
            if pos:
                self._tap(pos, gap=200)
            else:
                coords = {
                    "story_tab.png": (300, 790),
                    "squadron_tab.png": (465, 790),
                    "challenge_tab.png": (590, 770),
                    "raid_tab.png": (735, 790),
                }
                pct = coords.get(target, (590, 770))
                self._tap((self._rx + self._rw * pct[0] // 1000,
                           self._ry + self._rh * pct[1] // 1000), gap=200)

            time.sleep(0.6)

    def _pick_stage(self):
        self._phase = "picking_stage"
        self._push()

        if self._mode == "Raid":
            self._pick_raid_act()
        elif self._mode == "Squadron":
            self._pick_sq_story_chap()
        elif self._mode == "Story":
            self._pick_story_chap()
        elif self._mode == "Aizen":
            self._pick_aizen()
        elif self._mode == "Challenge":
            self._pick_regular_challenge()

    def _pick_raid_act(self):
        for _ in range(5):
            if self._see(self._raid_act):
                self._tap(self._see(self._raid_act), times=2, gap=100)
                time.sleep(0.6)
                return
            act_idx = {"raid_act1.png": 0, "raid_act2.png": 1, "raid_act3.png": 2, "raid_act4.png": 3}
            i = act_idx.get(self._raid_act, 0)
            ay = self._ry + self._rh * (28 + i * 13) // 100
            self._tap((self._rx + self._rw * 49 // 100, ay), times=2, gap=100)
            time.sleep(0.6)

    def _pick_sq_story_chap(self):
        si = {"squadron_story1.png": 0, "squadron_story2.png": 1, "squadron_story3.png": 2}
        idx = si.get(self._sq_story, 0)
        sx = self._rx + self._rw * 320 // 1000
        sy = self._ry + self._rh * (320 + idx * 85) // 1000
        self._tap((sx, sy), times=2, gap=100)
        time.sleep(0.7)

        ci = {"squadron_ch1.png": 0, "squadron_ch2.png": 1, "squadron_ch3.png": 2, "squadron_ch4.png": 3}
        cidx = ci.get(self._sq_chap, 0)
        cx = self._rx + self._rw * 490 // 1000
        cy = self._ry + self._rh * (305 + cidx * 45) // 1000
        self._tap((cx, cy), times=2, gap=100)
        time.sleep(0.7)

    def _pick_story_chap(self):
        sx = self._rx + self._rw * 320 // 1000
        sy = self._ry + self._rh * (320 + (self._st_idx - 1) * 85) // 1000
        self._tap((sx, sy), times=2, gap=100)
        time.sleep(0.7)

        cx = self._rx + self._rw * 490 // 1000
        if self._st_chap >= 8:
            self.input.scroll_chapter_list(self._rx, self._ry, self._rw, self._rh)
            cy = self._ry + self._rh * (597 - (10 - self._st_chap) * 45) // 1000
        else:
            cy = self._ry + self._rh * (327 + (self._st_chap - 1) * 45) // 1000
        from core.mouse import move_to
        move_to(cx, cy)
        time.sleep(0.2)
        self._tap((cx, cy), times=2, gap=200)
        time.sleep(0.7)

    def _pick_aizen(self):
        x1 = self._rx + self._rw * 20 // 100
        y1 = self._ry + self._rh * 25 // 100
        x2 = self._rx + self._rw * 45 // 100
        y2 = self._ry + self._rh * 80 // 100
        pos = self.vision.find_nav_in_subregion("aizen_btn.png", x1, y1, x2, y2, 0.70)
        if pos:
            self._tap(pos, times=2, gap=80)
        else:
            self._tap((self._rx + self._rw * 30 // 100,
                        self._ry + self._rh * 65 // 100), times=2, gap=100)
        time.sleep(0.8)

    def _pick_regular_challenge(self):
        x1 = self._rx + self._rw * 20 // 100
        y1 = self._ry + self._rh * 25 // 100
        x2 = self._rx + self._rw * 45 // 100
        y2 = self._ry + self._rh * 55 // 100
        pos = self.vision.find_nav_in_subregion("regular_challenge_btn.png", x1, y1, x2, y2, 0.70)
        if pos:
            self._tap((pos[0], pos[1] - 8), times=2, gap=50, jitter=False)
        else:
            rx = self._rx + self._rw * 333 // 1000
            ry = self._ry + self._rh * 440 // 1000 - 8
            self._tap((rx, ry), times=2, gap=100, jitter=False)
        time.sleep(0.8)

    def _pick_difficulty(self):
        diff_file = {
            "Raid": self._raid_diff,
            "Squadron": self._sq_diff,
            "Story": self._st_diff,
            "Aizen": self._az_diff,
        }.get(self._mode, "normal_btn.png")

        if diff_file == "normal_btn.png" or self._mode == "Challenge":
            return

        self._phase = "setting_diff"
        self._push()

        for _ in range(4):
            pos = self._see(diff_file)
            if pos:
                self._tap(pos, times=2, gap=100)
                time.sleep(0.5)
                return

            if self._mode == "Aizen":
                fx = self._rx + self._rw * 52 // 100
                fy = self._ry + self._rh * 59 // 100
            else:
                fx = self._rx + self._rw * 713 // 1000
                fy = self._ry + self._rh * 542 // 1000
            self._tap((fx, fy), times=2, gap=100)
            time.sleep(0.5)

    def _create_room(self):
        self._phase = "creating_room"
        self._push()

        for _ in range(6):
            if self._halt.is_set():
                return
            if self._see("start_btn.png"):
                return

            pos = self._see("create_room_stage_btn.png")
            if pos:
                self._tap(pos, times=2, gap=80)
            else:
                fpos = self._see("friends_only_btn.png")
                if fpos:
                    self._tap((fpos[0] + 166, fpos[1] + 5), times=2, gap=80)
                else:
                    self._tap((self._rx + self._rw * 650 // 1000,
                               self._ry + self._rh * 675 // 1000), times=2, gap=80)

            found = self._spot("start_btn.png", timeout=1.2)
            if found:
                return

    def _click_start(self):
        self._phase = "starting"
        self._push()

        for _ in range(10):
            if self._halt.is_set():
                return

            for img in ("victory_banner.png", "defeat_banner.png", "retry_btn.png"):
                if self._see(img, th=0.55 if "banner" in img else None):
                    return

            pos = self._see("start_btn.png")
            if pos:
                self._tap(pos, times=2, gap=60)
                found = self._spot(*BATTLE_ACTIVE_IMGS, timeout=2.0)
                if found:
                    return
            else:
                sb_x = self._rx + self._rw * 777 // 1000
                sb_y = self._ry + self._rh * 708 // 1000
                self._tap((sb_x, sb_y), times=2, gap=80)
                found = self._spot(*BATTLE_ACTIVE_IMGS, timeout=1.5)
                if found:
                    return

            if self._see("shop_icon.png"):
                return

    # ══════════════════════════════════════════════════════════════
    # BATTLE MONITORING
    # ══════════════════════════════════════════════════════════════

    def _watch_battle(self) -> str:
        self._phase = "battling"
        self._push()
        self._battle_start = time.monotonic()
        idle_since = 0

        while not self._halt.is_set():
            self._refresh_bounds()
            if not self._hwnd or not wm.is_window(self._hwnd):
                self._handle_game_crash()
                return "unknown"

            if self._handle_disconnect():
                return "unknown"

            vic = self._see("victory_banner.png", th=0.55)
            if vic:
                self._battle_ms = int((time.monotonic() - self._battle_start) * 1000)
                return "victory"

            dft = self._see("defeat_banner.png", th=0.55)
            if dft:
                self._battle_ms = int((time.monotonic() - self._battle_start) * 1000)
                return "defeat"

            if self._see("retry_btn.png"):
                self._battle_ms = int((time.monotonic() - self._battle_start) * 1000)
                return "defeat"

            if self._see("replay_btn.png"):
                self._battle_ms = int((time.monotonic() - self._battle_start) * 1000)
                return "unknown"

            if self._see("shop_icon.png"):
                return "unknown"

            if self._see("team_btn.png"):
                idle_since = 0
                time.sleep(0.1)
                continue

            if idle_since == 0:
                idle_since = time.monotonic()
            if time.monotonic() - idle_since > 60:
                return "unknown"

            time.sleep(0.1)

        return "unknown"

    def _replay_or_retry(self):
        self._phase = "post_battle"
        self._push()

        for _ in range(8):
            pos = self._see("retry_btn.png")
            if pos:
                self._tap(pos, times=2, gap=60)
                time.sleep(1.0)
                if not self._see("retry_btn.png"):
                    return
                continue

            pos = self._see("replay_btn.png")
            if pos:
                self._tap(pos, times=2, gap=60)
                time.sleep(0.5)
                return

            if self._see("start_btn.png") or self._see("team_btn.png"):
                return

            time.sleep(0.3)

    def _leave_results(self):
        for _ in range(5):
            pos = self._see("leave_btn.png")
            if pos:
                self._tap(pos, times=2, gap=80)
                time.sleep(1.0)
                if not self._see("retry_btn.png") and not self._see("replay_btn.png"):
                    return
            else:
                lx = self._rx + self._rw * 548 // 1000
                ly = self._ry + self._rh * 702 // 1000
                self._tap((lx, ly), times=2, gap=80)
                time.sleep(1.0)

    # ══════════════════════════════════════════════════════════════
    # CHALLENGE REWARD CHECK
    # ══════════════════════════════════════════════════════════════

    def _time_slot(self):
        t = time.localtime()
        return (t.tm_hour * 60 + t.tm_min) // 30

    def _should_check_rewards(self) -> bool:
        if not self._challenge_check or self._mode == "Challenge":
            return False
        slot = self._time_slot()
        if slot != self._last_refresh_slot:
            return True
        return False

    def _do_challenge_check(self):
        self._phase = "challenge_check"
        self._push()
        self._last_refresh_slot = self._time_slot()

        self._leave_results()
        time.sleep(1.0)

        for _ in range(20):
            scene = self._read_scene()
            if scene == Scene.LOBBY:
                self._go_through_lobby()
                break
            elif scene == Scene.STAGE_SELECT:
                break
            time.sleep(0.3)

        saved_mode = self._mode
        self._mode = "Challenge"
        self._pick_tab()
        self._pick_regular_challenge()

        time.sleep(1.5)
        found = False
        for rf in self._reward_files:
            if self.vision.find_reward(rf, self._rx, self._ry, self._rw, self._rh):
                found = True
                self.log.log(f"Reward found: {rf}")
                break

        if found:
            self._create_room()
            self._click_start()
        else:
            self._mode = saved_mode
            self._phase = "returning"
            self._push()

    # ══════════════════════════════════════════════════════════════
    # DISCONNECT & CRASH RECOVERY
    # ══════════════════════════════════════════════════════════════

    def _handle_disconnect(self) -> bool:
        pos = self._see("reconnect_btn.png")
        if not pos:
            return False
        self.log.log("Disconnect detected")
        self._notify("DISCONNECTED")
        self._tap(pos)
        time.sleep(3)
        if self._see("reconnect_btn.png"):
            self.log.log("Reconnect failed — rejoining via deep link")
            self.rejoin()
        return True

    def _handle_game_crash(self):
        self.log.log("Game window gone — auto-rejoin")
        self._notify("DISCONNECTED")
        self._docked = False
        self._hwnd = 0
        self.launch_game()
        time.sleep(5)
        self._poll_for_game(90)
        self._dock_game()

    def _ensure_game_alive(self):
        if not self._hwnd or not wm.is_window(self._hwnd):
            self._handle_game_crash()
            return
        self._refresh_bounds()

        if self._docked and self.gui_hwnd:
            if not wm.is_foreground(self.gui_hwnd) and not wm.is_foreground(self._hwnd):
                wm.activate_window(self.gui_hwnd)
                time.sleep(0.3)
        elif not wm.is_foreground(self._hwnd):
            wm.activate_window(self._hwnd)
            time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════
    # WINDOW MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def _locate_game(self) -> int:
        if self._hwnd and wm.is_window(self._hwnd):
            return self._hwnd
        hwnd = wm.find_roblox_window()
        self._hwnd = hwnd
        return hwnd

    def _dock_game(self):
        hwnd = self._hwnd
        if not hwnd or not wm.is_window(hwnd):
            return
        if not self._docked and self.gui_hwnd:
            wm.remove_borders(hwnd)
            time.sleep(0.05)
            wm.set_parent(hwnd, self.gui_hwnd)
            self._docked = True
            time.sleep(0.1)
        wm.move_window(hwnd, 0, 0, FIXED_WIN_W, FIXED_WIN_H)
        wm.bring_to_top(hwnd)
        time.sleep(0.1)
        self._refresh_bounds()

    def _refresh_bounds(self):
        if self._hwnd and wm.is_window(self._hwnd):
            x, y, w, h = wm.get_window_rect(self._hwnd)
            self._rx, self._ry, self._rw, self._rh = x, y, w, h

    def _poll_for_game(self, timeout_s: int = 60) -> bool:
        self._phase = "waiting"
        self._push()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._halt.is_set():
                return False
            hwnd = wm.find_roblox_window()
            if hwnd:
                self._hwnd = hwnd
                return True
            time.sleep(2)
        return False

    # ══════════════════════════════════════════════════════════════
    # VISION & INPUT HELPERS
    # ══════════════════════════════════════════════════════════════

    def _see(self, img: str, th=None) -> tuple[int, int] | None:
        return self.vision.find_nav(img, self._rx, self._ry, self._rw, self._rh, th)

    def _spot(self, *images: str, timeout: float = 3.0) -> tuple[str, int, int] | None:
        """Wait for any of the images. One screen capture per poll cycle."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._halt.is_set():
                return None
            hit = self.vision.find_first(list(images), self._rx, self._ry, self._rw, self._rh)
            if hit:
                return hit
            time.sleep(0.05)
        return None

    def _tap(self, pos, times=1, gap=50, jitter=True):
        if isinstance(pos, tuple) and len(pos) >= 2:
            self.input.click_multiple(pos[0], pos[1], times, gap, jitter)

    # ══════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════

    def _notify(self, event: str):
        if not self._webhook_on or not self._webhook_url:
            return
        if event not in ("DISCONNECTED", "ALL TASKS COMPLETE"):
            if self.runs == self._last_notified_run:
                return
            self._last_notified_run = self.runs

        ctx = {
            "event": event,
            "mode": self._mode,
            "detail": self._detail,
            "diff": self._diff,
            "run_count": self.runs,
            "victory_count": self.victories,
            "defeat_count": self.defeats,
            "battle_duration_ms": self._battle_ms,
            "use_task_queue": True,
            "current_task_index": self._task_idx + 1,
            "task_count": self._task_total,
            "task_run_count": self._task_runs,
            "task_run_target": self._task_target,
            "total_runtime_s": int(time.monotonic() - self._session_start) if self._session_start else 0,
        }
        notify.send_webhook(self._webhook_url, ctx, self.vision,
                            self._rx, self._ry, self._rw, self._rh,
                            silent=self._webhook_silent,
                            screenshot_mode=self._screenshot_mode)

    def _push(self):
        if self.on_update:
            try:
                self.on_update(self.get_info())
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════
    # TASK CONFIG
    # ══════════════════════════════════════════════════════════════

    def _apply_task(self, t: dict):
        self._mode = t.get("mode", "Challenge")
        self._task_target = int(t.get("repeat", 10))
        diff = t.get("diff", "Normal")
        diff_file = "hard_btn.png" if diff == "Hard" else "normal_btn.png"
        self._diff = diff
        self._detail = ""

        if self._mode == "Raid":
            act = t.get("act", "Hidden Danger")
            self._raid_act = RAID_ACT_MAP.get(act, "raid_act1.png")
            self._raid_diff = diff_file
            self._detail = act
        elif self._mode == "Squadron":
            story = t.get("map", "GT City")
            chap = t.get("act", "Chapter 1")
            self._sq_story = SQUAD_STORY_MAP.get(story, "squadron_story1.png")
            self._sq_chap = SQUAD_CHAP_MAP.get(chap, "squadron_ch1.png")
            self._sq_diff = diff_file
            self._detail = f"{story} {chap}"
        elif self._mode == "Story":
            story = t.get("map", "GT City")
            chap_str = t.get("act", "Chapter 1")
            self._st_idx = STORY_INDEX_MAP.get(story, 1)
            self._st_chap = int(chap_str.replace("Chapter ", "")) if "Chapter" in chap_str else 1
            self._st_diff = diff_file
            self._detail = f"{story} Ch.{self._st_chap}"
        elif self._mode == "Aizen":
            self._az_diff = diff_file
