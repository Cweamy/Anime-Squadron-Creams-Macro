import os
import json
import time
import threading
from datetime import datetime, timezone

import requests
from core.screen import Screen
from core.constants import SCRIPT_DIR

VERSION = "1.0.0"
LOGO_URL = None

TITLES = {
    "VICTORY":              "🏆 Run Complete — Victory!",
    "DEFEAT":               "💀 Run Complete — Defeat",
    "STAGE END (Detected)": "🏁 Run Complete",
    "STAGE END (Direct)":   "🏁 Run Complete",
    "STAGE END (Retry)":    "💀 Run Complete — Defeat",
    "REPLAY":               "🔄 Replaying Stage",
    "DISCONNECTED":         "⚠️ Disconnected — Reconnecting",
    "ALL TASKS COMPLETE":   "✅ All Tasks Complete",
}

COLORS = {
    "VICTORY":              0x4CAF50,
    "DEFEAT":               0xF44336,
    "STAGE END (Detected)": 0x607D8B,
    "STAGE END (Direct)":   0x607D8B,
    "STAGE END (Retry)":    0xF44336,
    "REPLAY":               0x42A5F5,
    "DISCONNECTED":         0xFF9800,
    "ALL TASKS COMPLETE":   0xC9D1D9,
}


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _fmt_battle_time(ms: int) -> str:
    if ms <= 0:
        return "—"
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"


def _winrate(vic: int, dft: int) -> str:
    total = vic + dft
    if total == 0:
        return "— (0/0)"
    pct = vic / total * 100
    return f"{pct:.0f}% ({vic}/{dft})"


def send_webhook(url: str, ctx: dict, screen: Screen,
                 win_x: int, win_y: int, win_w: int, win_h: int,
                 silent: bool = False, screenshot_mode: str = "roblox"):
    if not url or not url.startswith("http"):
        return

    def _do():
        event = ctx.get("event", "")
        title = TITLES.get(event, f"📋 {event}")
        color = COLORS.get(event, 0x888888)

        vic = ctx.get("victory_count", 0)
        dft = ctx.get("defeat_count", 0)
        runs = ctx.get("run_count", 0)
        dur_ms = ctx.get("battle_duration_ms", 0)
        total_s = ctx.get("total_runtime_s", 0)

        mode = ctx.get("mode", "")
        detail = ctx.get("detail", "")
        diff = ctx.get("diff", "")
        mode_str = mode
        if detail:
            mode_str += f" — {detail}"
        if diff:
            mode_str += f" ({diff})"

        fields = []

        if mode_str:
            fields.append({
                "name": "🎮 Mode",
                "value": f"```{mode_str}```",
                "inline": False,
            })

        fields.append({
            "name": "📊 Win Rate",
            "value": f"```{_winrate(vic, dft)}```",
            "inline": True,
        })

        fields.append({
            "name": "🏅 Total Runs",
            "value": f"```{runs}```",
            "inline": True,
        })

        if dur_ms > 0:
            fields.append({
                "name": "⏱️ Battle Time",
                "value": f"```{_fmt_battle_time(dur_ms)}```",
                "inline": True,
            })

        if ctx.get("use_task_queue"):
            ti = ctx.get("current_task_index", 0)
            tc = ctx.get("task_count", 0)
            tr = ctx.get("task_run_count", 0)
            tt = ctx.get("task_run_target", 0)
            fields.append({
                "name": "📋 Task Progress",
                "value": f"```Task {ti}/{tc} — Run {tr}/{tt}```",
                "inline": False,
            })

        if total_s > 0:
            fields.append({
                "name": "⏳ Session Time",
                "value": f"```{_fmt_duration(total_s)}```",
                "inline": True,
            })

        now = datetime.now(timezone.utc)

        embed = {
            "title": title,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Cream's Macro v{VERSION} • {now.strftime('%m/%d/%Y %I:%M %p UTC')}",
            },
            "timestamp": now.isoformat(),
        }

        logo_path = os.path.join(SCRIPT_DIR, "logo.png")
        files_to_send = {}

        if os.path.exists(logo_path):
            embed["thumbnail"] = {"url": "attachment://logo.png"}

        tmp = None
        has_screenshot = False
        if screenshot_mode != "none":
            tmp = os.path.join(os.environ.get("TEMP", "."),
                               f"anime_squadron_{int(time.time() * 1000)}.png")
            if screenshot_mode == "fullscreen":
                from core.window import get_screen_size
                sw, sh = get_screen_size()
                has_screenshot = screen.capture_to_file(0, 0, sw, sh, tmp)
            else:
                has_screenshot = screen.capture_to_file(win_x, win_y, win_w, win_h, tmp)

        if has_screenshot and tmp and os.path.exists(tmp):
            embed["image"] = {"url": "attachment://screenshot.png"}

        payload = {"embeds": [embed]}
        if silent:
            payload["flags"] = 4096
        payload_json = json.dumps(payload)

        try:
            multipart_files = []

            if os.path.exists(logo_path):
                multipart_files.append(
                    ("files[0]", ("logo.png", open(logo_path, "rb"), "image/png"))
                )

            if has_screenshot and tmp and os.path.exists(tmp):
                multipart_files.append(
                    ("files[1]", ("screenshot.png", open(tmp, "rb"), "image/png"))
                )

            if multipart_files:
                requests.post(
                    url,
                    data={"payload_json": payload_json},
                    files=multipart_files,
                    timeout=15,
                )
                for _, (_, fobj, _) in multipart_files:
                    fobj.close()
            else:
                requests.post(url, json=payload, timeout=10)
        except Exception:
            pass
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    threading.Thread(target=_do, daemon=True).start()
