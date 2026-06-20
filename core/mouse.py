import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT),
    ]


def _send_input(inp: INPUT):
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _abs_coords(x: int, y: int):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    return int(x * 65535 / sw), int(y * 65535 / sh)


def move_to(x: int, y: int):
    ax, ay = _abs_coords(x, y)
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi.dx = ax
    inp.mi.dy = ay
    inp.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    _send_input(inp)


def move_relative(dx: int, dy: int):
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.dwFlags = MOUSEEVENTF_MOVE
    _send_input(inp)


def click(x: int, y: int):
    move_to(x, y)
    time.sleep(0.005)
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
    _send_input(inp)
    time.sleep(0.005)
    inp2 = INPUT(type=INPUT_MOUSE)
    inp2.mi.dwFlags = MOUSEEVENTF_LEFTUP
    _send_input(inp2)


def scroll_down(amount: int = -120):
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi.mouseData = ctypes.c_ulong(amount & 0xFFFFFFFF)
    inp.mi.dwFlags = MOUSEEVENTF_WHEEL
    _send_input(inp)


class Mouse:
    """Stateful mouse with jitter and retry-based offset."""

    def __init__(self):
        self._click_count = 0

    def _jitter_offset(self, retry: int = 0) -> tuple[int, int]:
        idx = self._click_count % 4
        offsets = [(1, 0), (0, -1), (-1, 0), (0, 1)]
        jx, jy = offsets[idx]
        extra = min(retry // 2, 5)
        if idx == 0:
            jx += extra
        elif idx == 1:
            jy -= extra
        elif idx == 2:
            jx -= extra
        else:
            jy += extra
        return jx, jy

    def click_at(self, x: int, y: int, delay_ms: int = 50,
                 jitter: bool = True, retry: int = 0):
        if jitter:
            jx, jy = self._jitter_offset(retry)
        else:
            jx, jy = 0, 0
        self._click_count += 1

        cx, cy = x + jx, y + jy
        move_to(cx, cy)
        time.sleep(0.01)
        move_relative(1, 0)
        time.sleep(0.005)
        click(cx, cy)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    def click_multiple(self, x: int, y: int, count: int = 3,
                       interval_ms: int = 150, jitter: bool = True, retry: int = 0):
        for _ in range(count):
            self.click_at(x, y, interval_ms, jitter, retry)

    def scroll_chapter_list(self, win_x: int, win_y: int, win_w: int, win_h: int):
        hx = win_x + win_w * 490 // 1000
        hy = win_y + win_h * 440 // 1000
        move_to(hx, hy)
        time.sleep(0.12)
        move_relative(1, 0)
        time.sleep(0.12)
        start = time.monotonic()
        while time.monotonic() - start < 2.5:
            scroll_down(-120)
            time.sleep(0.06)
        time.sleep(0.4)
