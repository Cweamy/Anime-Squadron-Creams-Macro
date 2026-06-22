import os
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shcore = ctypes.windll.shcore

SW_RESTORE = 9
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_BORDER = 0x00800000
WS_THICKFRAME = 0x00040000
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_TOP = 0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except (OSError, AttributeError):
        pass
    try:
        shcore.SetProcessDpiAwareness(2)
        return
    except (OSError, AttributeError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (OSError, AttributeError):
        pass


def get_process_name(hwnd: int) -> str:
    """Get the executable name for a window's owning process."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == 0:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    buf = ctypes.create_unicode_buffer(260)
    size = wt.DWORD(260)
    kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return os.path.basename(buf.value).lower()


def find_window(title_substr: str) -> int:
    """Find a visible window whose title contains the substring."""
    results = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_substr.lower() in buf.value.lower():
                    results.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return results[0] if results else 0


def find_roblox_window() -> int:
    """Find Roblox by checking BOTH title and process name (RobloxPlayerBeta.exe)."""
    results = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                if "roblox" in title:
                    proc = get_process_name(hwnd)
                    if "robloxplayerbeta" in proc:
                        results.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return results[0] if results else 0


def is_window(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def move_window(hwnd: int, x: int, y: int, w: int, h: int):
    user32.MoveWindow(hwnd, x, y, w, h, True)


def activate_window(hwnd: int):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def is_foreground(hwnd: int) -> bool:
    return user32.GetForegroundWindow() == hwnd


def remove_borders(hwnd: int):
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style &= ~WS_CAPTION
    style &= ~WS_BORDER
    style &= ~WS_THICKFRAME
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)


def restore_borders(hwnd: int):
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style |= WS_CAPTION | WS_BORDER | WS_THICKFRAME
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)


def set_parent(child: int, parent: int):
    """Make child a child window of parent. Pass parent=0 to unparent."""
    user32.SetParent(child, parent)


def set_always_on_top(hwnd: int, on: bool = True):
    flag = HWND_TOPMOST if on else HWND_NOTOPMOST
    user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE)


def bring_to_top(hwnd: int):
    """Bring a child window to the top of its sibling z-order."""
    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE)


def get_screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


def press_key(vk: int):
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 0x0002, 0)  # KEYEVENTF_KEYUP


def send_key_to_window(hwnd: int, vk: int):
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
