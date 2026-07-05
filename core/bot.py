import os
import time
import threading
from enum import Enum

from core.constants import (
    FIXED_WIN_W, FIXED_WIN_H, PLACE_ID,
    RAID_MAP, RAID_ACT_BY_MAP, INVASION_MAP, INVASION_ACT_BY_MAP,
    SQUAD_STORY_MAP, SQUAD_CHAP_MAP,
    TRAIT_LIMIT, GAROU_LIMIT, TRAIT_STAGES, TRAIT_DROP_IMGS, TRAIT_DROP_THRESHOLD,
    TRAIT_KEY_AIZEN, TRAIT_KEY_GAROU, TRAIT_KEY_GT_ULTIMATE_EVIL, TRAIT_KEY_ECLIPSE_THE_ECLIPSE,
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
    RESULTS = 6
    DISCONNECTED = 7


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
    "paused": "Paused",
    "resuming": "Resuming",
}

STAGE_TABS = ("tabs/challenge.png", "tabs/raid.png", "tabs/squadron.png",
              "tabs/story.png", "tabs/invasion.png", "room/friends_only.png")


class GameBot:
    def __init__(self, logger: Logger):
        self.log = logger
        self.vision = Screen(logger)
        self.input = Mouse()

        self.active = False
        self.paused = False
        self._phase = "idle"
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self._pause = threading.Event()
        self._pause.set()  # not paused by default
        self._afk_stop = threading.Event()
        self._afk_thread: threading.Thread | None = None

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
        self._challenge_priority = False
        self._in_challenge = False
        self._reward_files: list[str] = []
        self._loop_queue = False

        # Stats
        self.victories = 0
        self.defeats = 0
        self.runs = 0
        self.challenge_runs = 0
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
        self._raid_map_img = ""
        self._raid_act = ""
        self._raid_diff = ""
        self._inv_map_img = ""
        self._inv_act = ""
        self._inv_diff = ""
        self._sq_story = ""
        self._sq_chap = ""
        self._sq_diff = ""
        self._st_story_img = ""
        self._st_chap = 1
        self._st_diff = ""
        self._challenge_type = "Regular"
        self._challenge_diff = ""
        self._raid_map_name = ""
        self._raid_act_name = ""

        # Trait farm — per-stage counts shared across any task that opts in
        self._trait_track_current = False
        self._trait_counts: dict[str, int] = {}
        self._trait_last_reset = ""

        self.on_update: callable = None
        self.on_trait_update: callable = None

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
        self._challenge_priority = config.get("challenge_priority", False)
        self._reward_files = config.get("desired_rewards", [])
        self._loop_queue = config.get("start_over", False)

        queue = [t for t in tasks if int(t.get("repeat", 0)) > 0]
        if not queue:
            return

        self.victories = self.defeats = self.runs = self.challenge_runs = 0
        self._session_start = time.monotonic()
        self._last_refresh_slot = -1
        self._last_notified_run = -1

        self.active = True
        self._halt.clear()
        self._dock_game()
        self._thread = threading.Thread(target=self._worker, args=(queue,), daemon=True)
        self._thread.start()

    def halt(self):
        self._halt.set()
        self._pause.set()  # unblock if paused so thread can exit
        self.active = False
        self.paused = False
        self._phase = "idle"
        self._push()

    def pause(self):
        if self.active and not self.paused:
            self.paused = True
            self._pause.clear()
            self._phase = "paused"
            self._push()

    def resume(self):
        if self.active and self.paused:
            self.paused = False
            self._pause.set()
            self._phase = "resuming"
            self._push()

    def get_info(self) -> dict:
        total = self.victories + self.defeats
        trait_state = self.get_trait_state()
        return {
            "state": PHASE_LABELS.get(self._phase, self._phase),
            "running": self.active,
            "paused": self.paused,
            "roblox_found": bool(self._hwnd and wm.is_window(self._hwnd)),
            "run_count": self.runs,
            "victory_count": self.victories,
            "defeat_count": self.defeats,
            "challenge_runs": self.challenge_runs,
            "win_rate": round(self.victories / total * 100) if total > 0 else 0,
            "session_s": int(time.monotonic() - self._session_start) if self._session_start and self.active else 0,
            "use_task_queue": True,
            "current_task_index": self._task_idx + 1,
            "task_count": self._task_total,
            "task_run_count": self._task_runs,
            "task_run_target": self._task_target,
            "trait_tracking": trait_state["tracking"],
            "trait_stage": trait_state["current_key"],
            "trait_count": trait_state["current_count"],
            "trait_limit": trait_state["current_limit"],
            "trait_last_reset": trait_state["last_reset"],
        }

    def dock_game(self):
        self._hwnd = self._locate_game()
        if self._hwnd:
            self._dock_game()

    def undock_game(self):
        if self._hwnd:
            try:
                if wm.is_window(self._hwnd):
                    wm.set_parent(self._hwnd, 0)
                    wm.restore_borders(self._hwnd)
                    wm.move_window(self._hwnd, 0, 0, FIXED_WIN_W + 16, FIXED_WIN_H + 39)
            except Exception:
                pass
            self._docked = False

    def launch_game(self):
        url = f"roblox://experiences/start?placeId={PLACE_ID}"
        self.log.log(f"Deep link: {url}")
        os.startfile(url)

    def rejoin(self):
        self._phase = "rejoining"
        self._push()
        self.launch_game()
        self._sleep(8)
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
        self._check_trait_reset()

        if self._trait_track_current:
            trait_info = self._trait_stage_info()
            if trait_info:
                key, limit = trait_info
                count = self._trait_counts.get(key, 0)
                if count >= limit:
                    self.log.log(f"Trait farm [{key}]: already at limit ({count}/{limit}), skipping task")
                    self._notify("TRAIT LIMIT REACHED")
                    return

        if self._should_check_rewards():
            self._do_challenge_check_startup()

        while self._task_runs < self._task_target and not self._halt.is_set():
            self._ensure_game_alive()
            if self._halt.is_set():
                return

            self._navigate_to_battle()
            if self._halt.is_set():
                return

            outcome = self._watch_battle()

            if outcome == "priority_challenge":
                self._do_challenge_check_startup()
                continue

            if self._in_challenge:
                self.challenge_runs += 1
                self._push()
                if self._time_slot() != self._last_refresh_slot:
                    self.log.log("Challenge: time slot changed, checking new rewards")
                    self._leave_results()
                    self._do_challenge_check_recheck()
                    if not self._in_challenge:
                        self.log.log("Challenge: no desired reward in new slot, returning to task")
                        self._apply_task(task)
                    continue
                self.log.log("Challenge: replaying (same time slot)")
                self._replay_or_retry()
                continue

            self.runs += 1
            self._task_runs += 1
            if outcome == "victory":
                self.victories += 1
            elif outcome == "defeat":
                self.defeats += 1
            self._notify(outcome.upper() if outcome != "unknown" else "STAGE END (Detected)")

            if self._trait_track_current:
                trait_info = self._trait_stage_info()
                if trait_info:
                    key, limit = trait_info
                    count = self._trait_counts.get(key, 0)
                    if count >= limit:
                        self.log.log(f"Trait farm [{key}]: limit reached ({count}/{limit}), ending task")
                        self._notify("TRAIT LIMIT REACHED")
                        self._leave_results()
                        return

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
            order = ["lobby/create_room.png", *STAGE_TABS, "lobby/shop_icon.png"]
        else:
            order = [
                "lobby/shop_icon.png", "lobby/create_room.png", *STAGE_TABS,
                "room/start.png", "battle/team.png",
                "results/replay.png", "results/retry.png",
                "system/reconnect.png", "system/retry.png",
            ]

        hit = self.vision.find_first(order, self._rx, self._ry, self._rw, self._rh)
        if not hit:
            return Scene.UNKNOWN

        name = hit[0]
        if name == "lobby/shop_icon.png":
            return Scene.LOBBY
        if name == "lobby/create_room.png":
            return Scene.PLAY_AREA
        if name in STAGE_TABS:
            return Scene.STAGE_SELECT
        if name == "room/start.png":
            return Scene.IN_ROOM
        if name == "battle/team.png":
            return Scene.BATTLING
        if name in ("results/replay.png", "results/retry.png"):
            return Scene.RESULTS
        if name in ("system/reconnect.png", "system/retry.png"):
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
            self.log.log(f"Nav [{attempt+1}/30]: bounds=({self._rx},{self._ry},{self._rw},{self._rh}) hint={hint}")

            if self._handle_disconnect():
                continue

            scene = self._read_scene(hint)
            self.log.log(f"Nav [{attempt+1}/30]: scene={scene.name}")
            hint = ""

            if scene == Scene.LOBBY:
                self.log.log("Nav: → go_through_lobby")
                self._go_through_lobby_safe()
                hint = "post_lobby"
            elif scene == Scene.PLAY_AREA:
                self.log.log("Nav: → open_stage_menu")
                self._open_stage_menu()
            elif scene == Scene.STAGE_SELECT:
                self.log.log("Nav: → select_and_start")
                self._select_and_start()
                return
            elif scene == Scene.IN_ROOM:
                self.log.log("Nav: → click_start")
                self._click_start()
                return
            elif scene == Scene.BATTLING:
                self.log.log("Nav: → already in battle")
                return
            elif scene == Scene.RESULTS:
                self.log.log("Nav: → replay_or_retry")
                self._replay_or_retry()
                return
            elif scene == Scene.DISCONNECTED:
                self.log.log("Nav: → handle_disconnect")
                self._handle_disconnect()
            else:
                self.log.log(f"Nav [{attempt+1}/30]: UNKNOWN - no images matched")
                self._sleep(0.3)

    def _open_stage_menu(self):
        self._phase = "opening_menu"
        self._push()

        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see("lobby/create_room.png")
            if pos:
                self._tap(pos, times=2, gap=80, jitter=False)
            else:
                self._sleep(0.5)

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
            "Challenge": "tabs/challenge.png",
            "Raid": "tabs/raid.png",
            "Squadron": "tabs/squadron.png",
            "Story": "tabs/story.png",
            "Invasion": "tabs/invasion.png",
        }
        target = tab_map.get(self._mode, "tabs/challenge.png")
        confirm_map = {
            "tabs/challenge.png": lambda: self._see("challenge/panel_header.png") or self._see("challenge/regular.png"),
            "tabs/raid.png": lambda: any(self._see(img) for acts in RAID_ACT_BY_MAP.values() for img in acts.values()),
            "tabs/squadron.png": lambda: self._see("squadron/panel_header.png"),
            "tabs/story.png": lambda: self._see("story/panel_header.png"),
            "tabs/invasion.png": lambda: any(self._see(img) for img in INVASION_MAP.values()) or any(self._see(img) for acts in INVASION_ACT_BY_MAP.values() for img in acts.values()),
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
                    "tabs/story.png": (300, 790),
                    "tabs/squadron.png": (465, 790),
                    "tabs/challenge.png": (590, 770),
                    "tabs/raid.png": (735, 790),
                }
                pct = coords.get(target)
                if pct:
                    self._tap((self._rx + self._rw * pct[0] // 1000,
                               self._ry + self._rh * pct[1] // 1000), gap=200)

            self._sleep(0.6)

    def _pick_stage(self):
        self._phase = "picking_stage"
        self._push()

        if self._mode == "Challenge":
            self._pick_challenge()
        elif self._mode == "Raid":
            self._pick_map_then_act(self._raid_map_img, self._raid_act)
        elif self._mode == "Invasion":
            self._pick_map_then_act(self._inv_map_img, self._inv_act)
        elif self._mode == "Squadron":
            self._pick_sq_story_chap()
        elif self._mode == "Story":
            self._pick_story_chap()

    def _pick_map_then_act(self, map_img: str, act_img: str):
        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see(map_img)
            if pos:
                self._tap(pos, times=2, gap=100)
                self._sleep(0.5)
                break
            self._sleep(0.3)

        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see(act_img)
            if pos:
                self._tap(pos, times=2, gap=100)
                self._sleep(0.25)
                return
            self._sleep(0.3)

    def _pick_sq_story_chap(self):
        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see(self._sq_story)
            if pos:
                self._tap(pos, times=2, gap=100)
                self._sleep(0.3)
                break
            self._sleep(0.3)

        ci = {"squadron/chapter1.png": 0, "squadron/chapter2.png": 1, "squadron/chapter3.png": 2, "squadron/chapter4.png": 3}
        cidx = ci.get(self._sq_chap, 0)
        cx = self._rx + self._rw * 490 // 1000
        cy = self._ry + self._rh * (305 + cidx * 45) // 1000
        self._tap((cx, cy), times=2, gap=100)
        self._sleep(0.3)

    def _pick_story_chap(self):
        for _ in range(5):
            if self._halt.is_set():
                return
            pos = self._see(self._st_story_img)
            if pos:
                self._tap(pos, times=2, gap=100)
                self._sleep(0.3)
                break
            self._sleep(0.3)

        cx = self._rx + self._rw * 490 // 1000
        chap_y = self._ry + self._rh * 400 // 1000
        from core.mouse import move_to
        move_to(cx, chap_y)
        self._sleep(0.1)
        self._tap((cx, chap_y), times=1, gap=50, jitter=False)
        self._sleep(0.15)

        if self._st_chap >= 8:
            self.input.scroll_chapter_list(self._rx, self._ry, self._rw, self._rh)
            cy = self._ry + self._rh * (597 - (10 - self._st_chap) * 45) // 1000
        else:
            cy = self._ry + self._rh * (327 + (self._st_chap - 1) * 45) // 1000
        move_to(cx, cy)
        self._sleep(0.1)
        self._tap((cx, cy), times=2, gap=150, jitter=False)
        self._sleep(0.3)

    def _pick_challenge(self, override_type=None):
        img_map = {
            "Regular": "challenge/regular.png",
            "Aizen": "challenge/aizen.png",
            "Garou": "challenge/garou.png",
        }
        ctype = override_type or self._challenge_type
        img = img_map.get(ctype, "challenge/regular.png")
        x1 = self._rx + self._rw * 20 // 100
        y1 = self._ry + self._rh * 25 // 100
        x2 = self._rx + self._rw * 45 // 100
        y2 = self._ry + self._rh * 80 // 100
        pos = self.vision.find_nav_in_subregion(img, x1, y1, x2, y2, 0.70)
        if pos:
            self._tap(pos, times=2, gap=80, jitter=False)
        self._sleep(0.3)

    def _pick_difficulty(self):
        diff_file = {
            "Challenge": self._challenge_diff,
            "Raid": self._raid_diff,
            "Invasion": self._inv_diff,
            "Squadron": self._sq_diff,
            "Story": self._st_diff,
        }.get(self._mode, "difficulty/normal.png")

        if diff_file == "difficulty/normal.png":
            return
        if self._mode == "Challenge" and self._challenge_type == "Regular":
            return

        self._phase = "setting_diff"
        self._push()

        for _ in range(4):
            pos = self._see(diff_file)
            if pos:
                self._tap(pos, times=2, gap=100)
                self._sleep(0.5)
                return

            if self._mode == "Challenge":
                fx = self._rx + self._rw * 52 // 100
                fy = self._ry + self._rh * 59 // 100
            else:
                fx = self._rx + self._rw * 713 // 1000
                fy = self._ry + self._rh * 542 // 1000
            self._tap((fx, fy), times=2, gap=100)
            self._sleep(0.5)

    def _create_room(self):
        self._phase = "creating_room"
        self._push()

        for _ in range(6):
            if self._halt.is_set():
                return
            if self._see("room/start.png"):
                return

            pos = self._see("room/create_room.png")
            if pos:
                self._tap(pos, times=2, gap=80, jitter=False)
            else:
                self._sleep(0.5)

            found = self._spot("room/start.png", timeout=1.5)
            if found:
                return

    def _click_start(self):
        self._phase = "starting"
        self._push()
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            if self._halt.is_set():
                return

            if self._see("results/replay.png") or self._see("results/retry.png"):
                return

            pos = self._see("room/start.png")
            if pos:
                self._tap(pos, times=2, gap=60, jitter=False)
                self._sleep(1.0)
                return
            else:
                self._sleep(0.5)

            if self._see("lobby/shop_icon.png"):
                return

        self.log.log("Start: stuck for 30s, rejoining game")
        self.rejoin()

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

            if self._challenge_priority and self._should_check_rewards():
                self.log.log("Priority challenge: leaving battle to check rewards")
                self.rejoin()
                return "priority_challenge"

            if self._see("results/replay.png") or self._see("results/retry.png"):
                self._battle_ms = int((time.monotonic() - self._battle_start) * 1000)
                self._sleep(0.3)
                result = self.vision.detect_result_color(
                    self._rx, self._ry, self._rw, self._rh)
                result = result or "defeat"
                if result == "victory":
                    self._maybe_scan_trait_drop()
                return result

            if self._see("lobby/shop_icon.png"):
                return "unknown"

            if self._see("battle/team.png"):
                idle_since = 0
                self._sleep(0.1)
                continue

            if idle_since == 0:
                idle_since = time.monotonic()
            if time.monotonic() - idle_since > 60:
                return "unknown"

            self._sleep(0.1)

        return "unknown"

    def _replay_or_retry(self):
        self._phase = "post_battle"
        self._push()

        for _ in range(8):
            pos = self._see("results/retry.png")
            if pos:
                self._tap(pos, times=2, gap=60, jitter=False)
                self._sleep(1.0)
                if not self._see("results/retry.png"):
                    return
                continue

            pos = self._see("results/replay.png")
            if pos:
                self._tap(pos, times=2, gap=60, jitter=False)
                self._sleep(0.5)
                return

            if self._see("room/start.png") or self._see("battle/team.png"):
                return

            self._sleep(0.3)

    def _leave_results(self):
        for _ in range(5):
            pos = self._see("results/leave.png")
            if pos:
                self._tap(pos, times=2, gap=80, jitter=False)
                self._sleep(1.0)
                if not self._see("results/retry.png") and not self._see("results/replay.png"):
                    return
            else:
                self._sleep(0.5)

    # ══════════════════════════════════════════════════════════════
    # CHALLENGE REWARD CHECK
    # ══════════════════════════════════════════════════════════════

    def _time_slot(self):
        t = time.localtime()
        return (t.tm_hour * 60 + t.tm_min) // 30

    def _should_check_rewards(self) -> bool:
        if not self._challenge_check or self._mode == "Challenge":
            return False
        if not self._reward_files:
            return False
        if self._last_refresh_slot == -1:
            return True
        slot = self._time_slot()
        if slot != self._last_refresh_slot:
            return True
        return False

    def _navigate_to_stage_screen(self):
        self._phase = "scanning"
        self._push()
        for attempt in range(30):
            if self._halt.is_set():
                return
            self._refresh_bounds()
            if self._handle_disconnect():
                continue
            scene = self._read_scene()
            if scene == Scene.STAGE_SELECT:
                return
            elif scene == Scene.LOBBY:
                self._go_through_lobby_safe()
            elif scene == Scene.PLAY_AREA:
                self._open_stage_menu()
            elif scene == Scene.IN_ROOM or scene == Scene.BATTLING or scene == Scene.RESULTS:
                return
            else:
                self._sleep(0.3)

    def _go_through_lobby_safe(self):
        self._phase = "lobby"
        self._push()
        pos = self._see("lobby/play.png")
        if pos:
            self._tap(pos, times=3, gap=60)
        else:
            shop = self._see("lobby/shop_icon.png")
            if shop:
                self._tap((shop[0], shop[1] + 130), times=3, gap=60)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self._halt.is_set():
                return
            hit = self.vision.find_first(list(STAGE_TABS), self._rx, self._ry, self._rw, self._rh)
            if hit:
                return
            pos = self._see("lobby/create_room.png")
            if pos:
                self._tap(pos, times=2, gap=80, jitter=False)
            self._sleep(0.3)

    def _do_challenge_check_startup(self):
        self._phase = "challenge_check"
        self._push()
        self._last_refresh_slot = self._time_slot()
        self.log.log(f"Challenge check: looking for {self._reward_files}")

        self._navigate_to_stage_screen()

        saved_mode = self._mode
        self._mode = "Challenge"
        self._pick_tab()
        self._pick_challenge("Regular")

        self._sleep(1.5)
        found = self._scan_for_desired_reward()

        if found:
            self._in_challenge = True
            self._create_room()
            self._click_start()
        else:
            self.log.log("Challenge check: no desired reward found, skipping")
            self._mode = saved_mode
            self._phase = "returning"
            self._push()

    def _do_challenge_check(self):
        self._phase = "challenge_check"
        self._push()
        self._last_refresh_slot = self._time_slot()

        self._leave_results()
        self._sleep(1.0)

        for _ in range(20):
            scene = self._read_scene()
            if scene == Scene.LOBBY:
                self._go_through_lobby_safe()
                break
            elif scene == Scene.STAGE_SELECT:
                break
            self._sleep(0.3)

        saved_mode = self._mode
        self._mode = "Challenge"
        self._pick_tab()
        self._pick_challenge("Regular")

        self._sleep(1.5)
        found = self._scan_for_desired_reward()

        if found:
            self._in_challenge = True
            self._create_room()
            self._click_start()
        else:
            self.log.log("Challenge check: no desired reward found, skipping")
            self._mode = saved_mode
            self._phase = "returning"
            self._push()

    def _do_challenge_check_recheck(self):
        self._phase = "challenge_check"
        self._push()
        self._last_refresh_slot = self._time_slot()
        self._sleep(1.0)

        self._navigate_to_stage_screen()
        self._pick_tab()
        self._pick_challenge("Regular")

        self._sleep(1.5)
        found = self._scan_for_desired_reward()

        if found:
            self._in_challenge = True
            self._create_room()
            self._click_start()
        else:
            self._in_challenge = False

    def _scan_for_desired_reward(self) -> bool:
        if not self._reward_files:
            self.log.log("Challenge check: no rewards selected, skipping")
            return False
        for rf in self._reward_files:
            hit = self.vision.find_reward(rf, self._rx, self._ry, self._rw, self._rh)
            if hit:
                self.log.log(f"Challenge check: FOUND desired reward {rf}")
                return True
            else:
                self.log.log(f"Challenge check: {rf} not on screen")
        return False

    # ══════════════════════════════════════════════════════════════
    # TRAIT FARM
    # ══════════════════════════════════════════════════════════════

    def set_trait_state(self, counts: dict, last_reset: str = ""):
        """Load persisted per-stage trait progress on startup (no push —
        nothing is listening yet)."""
        self._trait_counts = {k: max(0, int(v)) for k, v in (counts or {}).items()}
        self._trait_last_reset = last_reset or time.strftime("%Y-%m-%d", time.gmtime())

    def set_trait_count(self, stage_key: str, count: int):
        self._trait_counts[stage_key] = max(0, int(count))
        self._push_trait_state()

    def get_trait_state(self) -> dict:
        stages = {key: {"count": self._trait_counts.get(key, 0), "limit": limit}
                  for key, limit in TRAIT_STAGES}
        info = self._trait_stage_info()
        return {
            "stages": stages,
            "last_reset": self._trait_last_reset,
            "tracking": bool(self._trait_track_current and info),
            "current_key": info[0] if info else "",
            "current_count": self._trait_counts.get(info[0], 0) if info else 0,
            "current_limit": info[1] if info else 0,
        }

    def _push_trait_state(self):
        if self.on_trait_update:
            try:
                self.on_trait_update(self.get_trait_state())
            except Exception:
                pass
        self._push()

    def _trait_stage_info(self) -> tuple[str, int] | None:
        """Return (stage_key, limit) if the current task's stage tracks
        trait drops, else None. Aizen/Ultimate Evil/The Eclipse cap at 100,
        Garou caps at 30."""
        if self._mode == "Challenge":
            if self._challenge_type == "Garou":
                return (TRAIT_KEY_GAROU, GAROU_LIMIT)
            if self._challenge_type == "Aizen":
                return (TRAIT_KEY_AIZEN, TRAIT_LIMIT)
        elif self._mode == "Raid":
            if self._raid_map_name == "GT" and self._raid_act_name == "The Ultimate Evil":
                return (TRAIT_KEY_GT_ULTIMATE_EVIL, TRAIT_LIMIT)
            if self._raid_map_name == "Eclipse" and self._raid_act_name == "The Eclipse":
                return (TRAIT_KEY_ECLIPSE_THE_ECLIPSE, TRAIT_LIMIT)
        return None

    def _check_trait_reset(self):
        """Trait limits reset at 7:00 GMT+7, which is exactly 00:00 UTC —
        so a UTC calendar-day change is the reset signal."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self._trait_last_reset == today:
            return
        if self._trait_last_reset and any(v > 0 for v in self._trait_counts.values()):
            self.log.log(f"Trait farm: daily reset ({self._trait_counts} -> all 0)")
            self._trait_counts = {}
        self._trait_last_reset = today
        self._push_trait_state()

    def _maybe_scan_trait_drop(self):
        if not self._trait_track_current:
            return
        info = self._trait_stage_info()
        if info is None:
            return
        key, limit = info
        self._check_trait_reset()
        count = self._trait_counts.get(key, 0)
        if count >= limit:
            return
        hit = self.vision.find_best(list(TRAIT_DROP_IMGS), self._rx, self._ry,
                                     self._rw, self._rh, TRAIT_DROP_THRESHOLD)
        if not hit:
            return
        name, conf = hit
        gained = 2 if "2_Trait" in name else 1
        new_count = min(limit, count + gained)
        self._trait_counts[key] = new_count
        self.log.log(f"Trait farm [{key}]: +{gained} drop detected ({name}, conf={conf:.3f}) "
                     f"-> {new_count}/{limit}")
        self._push_trait_state()

    # ══════════════════════════════════════════════════════════════
    # DISCONNECT & CRASH RECOVERY
    # ══════════════════════════════════════════════════════════════

    def _handle_disconnect(self) -> bool:
        pos = self._see("system/reconnect.png") or self._see("system/retry.png")
        if not pos:
            return False
        self.log.log("Disconnect detected")
        self._notify("DISCONNECTED")
        self._tap(pos)
        self._sleep(3)
        if self._see("system/reconnect.png") or self._see("system/retry.png"):
            self.log.log("Reconnect failed — rejoining via deep link")
            self.rejoin()
        return True

    def _handle_game_crash(self):
        self.log.log("Game window gone — auto-rejoin")
        self._notify("DISCONNECTED")
        self._docked = False
        self._hwnd = 0
        self.launch_game()
        self._sleep(5)
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
                self._sleep(0.3)
        elif not wm.is_foreground(self._hwnd):
            wm.activate_window(self._hwnd)
            self._sleep(0.3)

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
            self._sleep(0.05)
            wm.set_parent(hwnd, self.gui_hwnd)
            self._docked = True
            self._sleep(0.1)
        wm.move_window(hwnd, 0, 0, FIXED_WIN_W, FIXED_WIN_H)
        wm.bring_to_top(hwnd)
        self._sleep(0.1)
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
            self._sleep(2)
        return False

    # ══════════════════════════════════════════════════════════════
    # ANTI-AFK
    # ══════════════════════════════════════════════════════════════

    def start_anti_afk(self):
        if self._afk_thread and self._afk_thread.is_alive():
            return
        self._afk_stop.clear()
        self._afk_thread = threading.Thread(target=self._afk_loop, daemon=True)
        self._afk_thread.start()

    def stop_anti_afk(self):
        self._afk_stop.set()

    def _afk_loop(self):
        while not self._afk_stop.wait(60):
            if self.active:
                continue
            if self._hwnd and wm.is_window(self._hwnd):
                wm.activate_window(self._hwnd)
                wm.press_key(0x20)  # Space

    # ══════════════════════════════════════════════════════════════
    # VISION & INPUT HELPERS
    # ══════════════════════════════════════════════════════════════

    def _sleep(self, seconds: float) -> bool:
        self._pause.wait()
        return self._halt.wait(seconds)

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
            self._sleep(0.05)
        return None

    def _tap(self, pos, times=1, gap=50, jitter=True):
        if isinstance(pos, tuple) and len(pos) >= 2:
            self.log.log(f"CLICK: ({pos[0]},{pos[1]}) x{times} phase={self._phase} jitter={jitter}")
            self.input.click_multiple(pos[0], pos[1], times, gap, jitter)

    # ══════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════

    def _notify(self, event: str):
        if not self._webhook_on or not self._webhook_url:
            return
        if event not in ("DISCONNECTED", "ALL TASKS COMPLETE", "TRAIT LIMIT REACHED"):
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
        trait_state = self.get_trait_state()
        if trait_state["tracking"]:
            ctx["trait_count"] = trait_state["current_count"]
            ctx["trait_limit"] = trait_state["current_limit"]
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
        diff_file = "difficulty/hard.png" if diff == "Hard" else "difficulty/normal.png"
        self._diff = diff
        self._detail = ""
        self._trait_track_current = bool(t.get("track_trait", False))

        if self._mode == "Challenge":
            self._challenge_type = t.get("map", "Regular")
            self._challenge_diff = diff_file
            self._detail = self._challenge_type
        elif self._mode == "Raid":
            raid_map = t.get("map", "GT")
            act = t.get("act", list(RAID_ACT_BY_MAP.get(raid_map, {}).keys())[0] if raid_map in RAID_ACT_BY_MAP else "Hidden Danger")
            self._raid_map_img = RAID_MAP.get(raid_map, "raid/gt.png")
            acts = RAID_ACT_BY_MAP.get(raid_map, {})
            self._raid_act = acts.get(act, list(acts.values())[0] if acts else "raid/hidden_danger.png")
            self._raid_diff = diff_file
            self._raid_map_name = raid_map
            self._raid_act_name = act
            self._detail = f"{raid_map} — {act}"
        elif self._mode == "Invasion":
            inv_map = t.get("map", "The Lava Continent")
            acts = INVASION_ACT_BY_MAP.get(inv_map, {})
            act = t.get("act", next(iter(acts), "Ashfall Continent"))
            self._inv_map_img = INVASION_MAP.get(inv_map, "invasion/the_lava_continent.png")
            self._inv_act = acts.get(act, next(iter(acts.values()), "invasion/ashfall_continent.png"))
            self._inv_diff = diff_file
            self._detail = f"{inv_map} — {act}"
        elif self._mode == "Squadron":
            story = t.get("map", "GT City")
            chap = t.get("act", "Chapter 1")
            self._sq_story = SQUAD_STORY_MAP.get(story, "squadron/gt_city.png")
            self._sq_chap = SQUAD_CHAP_MAP.get(chap, "squadron/chapter1.png")
            self._sq_diff = diff_file
            self._detail = f"{story} {chap}"
        elif self._mode == "Story":
            story = t.get("map", "GT City")
            chap_str = t.get("act", "Chapter 1")
            self._st_story_img = SQUAD_STORY_MAP.get(story, "squadron/gt_city.png")
            self._st_chap = int(chap_str.replace("Chapter ", "")) if "Chapter" in chap_str else 1
            self._st_diff = diff_file
            self._detail = f"{story} Ch.{self._st_chap}"
