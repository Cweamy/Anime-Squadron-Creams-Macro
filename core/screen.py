import os
import base64
import cv2
import numpy as np
import mss
from core.constants import NAV_DIR, REWARD_DIR, ASSET_DIR, IMG_THRESHOLD, IMG_THRESHOLD_STRICT, IMG_THRESHOLD_RELAXED

try:
    from core.asset_data import ASSETS as _EMBEDDED
except ImportError:
    _EMBEDDED = {}

MULTISCALE_IMAGES = set()
SCALES = [1.0, 0.9, 0.8, 0.7, 0.6, 1.1, 1.2, 1.3, 1.4]


class Screen:
    """Screen capture (mss) and template matching (cv2) with TransBlack mask support."""

    def __init__(self, logger):
        self.logger = logger
        self._sct = mss.mss()
        self._tmpl_cache: dict[str, np.ndarray] = {}
        self._mask_cache: dict[str, np.ndarray | None] = {}

    def _load(self, path: str) -> np.ndarray | None:
        if path in self._tmpl_cache:
            return self._tmpl_cache[path]

        img = None
        rel = os.path.relpath(path, ASSET_DIR).replace("\\", "/")
        if rel in _EMBEDDED:
            raw = base64.b64decode(_EMBEDDED[rel])
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None and os.path.exists(path):
            img = cv2.imread(path, cv2.IMREAD_COLOR)

        if img is None:
            self.logger.log(f"Screen: ASSET NOT FOUND - {rel}")
            return None

        self._tmpl_cache[path] = img
        self._mask_cache[path] = self._build_mask(img)
        return img

    def _build_mask(self, template: np.ndarray) -> np.ndarray | None:
        """Build a TransBlack mask only for templates with large black regions (>20%).
        Small dark areas in nav buttons are normal and don't need masking."""
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        black_ratio = 1.0 - (cv2.countNonZero(mask) / max(mask.size, 1))
        if black_ratio > 0.20:
            return mask
        return None

    def capture(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        region = {"left": x, "top": y, "width": w, "height": h}
        try:
            raw = self._sct.grab(region)
            frame = np.array(raw)
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            self.logger.log(f"Screen: capture error - {e}")
            return None

    def capture_to_file(self, x: int, y: int, w: int, h: int, path: str) -> bool:
        frame = self.capture(x, y, w, h)
        if frame is None:
            return False
        try:
            cv2.imwrite(path, frame)
            return True
        except Exception as e:
            self.logger.log(f"Screen: save error - {e}")
            return False

    def _match(self, screenshot: np.ndarray, template: np.ndarray,
               threshold: float, mask: np.ndarray | None = None):
        if (template.shape[0] > screenshot.shape[0] or
                template.shape[1] > screenshot.shape[1]):
            return None

        if mask is not None:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCORR_NORMED, mask=mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if not np.isfinite(max_val) or max_val > 1.0:
                return None
            adj_th = max(threshold, 0.92)
            if max_val >= adj_th:
                h, w = template.shape[:2]
                return max_loc[0] + w // 2, max_loc[1] + h // 2, max_val
        else:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if not np.isfinite(max_val):
                return None
            if max_val >= threshold:
                h, w = template.shape[:2]
                return max_loc[0] + w // 2, max_loc[1] + h // 2, max_val

        return None

    def _match_robust(self, screenshot: np.ndarray, template: np.ndarray,
                       threshold: float, mask: np.ndarray | None = None):
        gray_ss = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        edges_ss = cv2.Canny(gray_ss, 50, 150)
        edges_tmpl = cv2.Canny(gray_tmpl, 50, 150)

        best = None
        for scale in SCALES:
            w = int(template.shape[1] * scale)
            h = int(template.shape[0] * scale)
            if w < 10 or h < 10 or w > screenshot.shape[1] or h > screenshot.shape[0]:
                continue

            if scale == 1.0:
                s_color = template
                s_gray = gray_tmpl
                s_edges = edges_tmpl
            else:
                interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
                s_color = cv2.resize(template, (w, h), interpolation=interp)
                s_gray = cv2.resize(gray_tmpl, (w, h), interpolation=interp)
                s_edges = cv2.Canny(s_gray, 50, 150)

            for src, tmpl, th in [
                (screenshot, s_color, threshold),
                (gray_ss, s_gray, threshold),
                (edges_ss, s_edges, max(threshold - 0.15, 0.35)),
            ]:
                if tmpl.shape[0] > src.shape[0] or tmpl.shape[1] > src.shape[1]:
                    continue
                result = cv2.matchTemplate(src, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if np.isfinite(max_val) and max_val >= th:
                    hit = (max_loc[0] + tmpl.shape[1] // 2,
                           max_loc[1] + tmpl.shape[0] // 2, max_val)
                    if best is None or hit[2] > best[2]:
                        best = hit

        return best

    def find_in_region(self, img_path: str, rx: int, ry: int, rw: int, rh: int,
                       threshold: float | None = None) -> tuple[int, int] | None:
        template = self._load(img_path)
        if template is None:
            return None
        screenshot = self.capture(rx, ry, rw, rh)
        if screenshot is None:
            return None

        mask = self._mask_cache.get(img_path)
        use_multiscale = os.path.basename(img_path) in MULTISCALE_IMAGES
        match_fn = self._match_robust if use_multiscale else self._match

        if threshold is not None:
            thresholds = [threshold]
        else:
            thresholds = [IMG_THRESHOLD_STRICT, IMG_THRESHOLD, IMG_THRESHOLD_RELAXED]

        for th in thresholds:
            hit = match_fn(screenshot, template, th)
            if hit:
                cx, cy, conf = hit
                self.logger.log(f"Screen: FOUND {os.path.basename(img_path)} at center "
                                f"({rx + cx},{ry + cy}) conf={conf:.3f} th={th:.2f}")
                return rx + cx, ry + cy

            if mask is not None:
                hit = match_fn(screenshot, template, th, mask)
                if hit:
                    cx, cy, conf = hit
                    self.logger.log(f"Screen: FOUND {os.path.basename(img_path)} at center "
                                    f"({rx + cx},{ry + cy}) conf={conf:.3f} th={th:.2f} [masked]")
                    return rx + cx, ry + cy

        return None

    def find_first(self, img_names: list[str], win_x: int, win_y: int,
                   win_w: int, win_h: int) -> tuple[str, int, int] | None:
        """Capture screen ONCE, check all templates with a single pass. Fast."""
        screenshot = self.capture(win_x, win_y, win_w, win_h)
        if screenshot is None:
            return None
        for name in img_names:
            path = os.path.join(NAV_DIR, name)
            template = self._load(path)
            if template is None:
                continue
            match_fn = self._match_robust if name in MULTISCALE_IMAGES else self._match
            hit = match_fn(screenshot, template, IMG_THRESHOLD_RELAXED)
            if hit:
                cx, cy, conf = hit
                self.logger.log(f"Screen: FOUND {name} at center "
                                f"({win_x + cx},{win_y + cy}) conf={conf:.3f}")
                return name, win_x + cx, win_y + cy
        return None

    def detect_result_color(self, rx: int, ry: int, rw: int, rh: int) -> str | None:
        sx = rx + int(rw * 0.20)
        sy = ry + int(rh * 0.28)
        sw = int(rw * 0.10)
        sh = int(rh * 0.07)
        frame = self.capture(sx, sy, sw, sh)
        if frame is None:
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        green_mask = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([85, 255, 255]))
        green_pct = cv2.countNonZero(green_mask) / max(green_mask.size, 1)

        red_lo = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([12, 255, 255]))
        red_hi = cv2.inRange(hsv, np.array([160, 50, 50]), np.array([180, 255, 255]))
        red_pct = cv2.countNonZero(cv2.bitwise_or(red_lo, red_hi)) / max(red_lo.size, 1)

        self.logger.log(f"Screen: RESULT COLOR green={green_pct:.2f} red={red_pct:.2f}")

        if green_pct > red_pct and green_pct > 0.15:
            return "victory"
        if red_pct > green_pct and red_pct > 0.15:
            return "defeat"
        return None

    def find_nav(self, img_name: str, win_x: int, win_y: int, win_w: int, win_h: int,
                 threshold: float | None = None) -> tuple[int, int] | None:
        path = os.path.join(NAV_DIR, img_name)
        return self.find_in_region(path, win_x, win_y, win_w, win_h, threshold)

    def find_nav_in_subregion(self, img_name: str, rx1: int, ry1: int, rx2: int, ry2: int,
                              threshold: float | None = None) -> tuple[int, int] | None:
        path = os.path.join(NAV_DIR, img_name)
        return self.find_in_region(path, rx1, ry1, rx2 - rx1, ry2 - ry1, threshold)

    def find_reward(self, img_name: str, win_x: int, win_y: int, win_w: int, win_h: int) -> tuple[int, int] | None:
        path = os.path.join(REWARD_DIR, img_name)
        return self.find_in_region(path, win_x, win_y, win_w, win_h)
