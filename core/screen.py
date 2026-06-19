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

    def find_in_region(self, img_path: str, rx: int, ry: int, rw: int, rh: int,
                       threshold: float | None = None) -> tuple[int, int] | None:
        template = self._load(img_path)
        if template is None:
            return None
        screenshot = self.capture(rx, ry, rw, rh)
        if screenshot is None:
            return None

        mask = self._mask_cache.get(img_path)

        if threshold is not None:
            thresholds = [threshold]
        else:
            thresholds = [IMG_THRESHOLD_STRICT, IMG_THRESHOLD, IMG_THRESHOLD_RELAXED]

        for th in thresholds:
            hit = self._match(screenshot, template, th)
            if hit:
                cx, cy, conf = hit
                self.logger.log(f"Screen: FOUND {os.path.basename(img_path)} at center "
                                f"({rx + cx},{ry + cy}) conf={conf:.3f} th={th:.2f}")
                return rx + cx, ry + cy

            if mask is not None:
                hit = self._match(screenshot, template, th, mask)
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
            hit = self._match(screenshot, template, IMG_THRESHOLD_RELAXED)
            if hit:
                cx, cy, conf = hit
                self.logger.log(f"Screen: FOUND {name} at center "
                                f"({win_x + cx},{win_y + cy}) conf={conf:.3f}")
                return name, win_x + cx, win_y + cy
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
