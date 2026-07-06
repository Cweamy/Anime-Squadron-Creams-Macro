"""
Lightweight splash screen using only ctypes (Win32 API).
Must import before heavy modules (cv2, numpy, webview) so it shows instantly.
"""
import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_TIMER = 0x0113
WM_CREATE = 0x0001
LWA_ALPHA = 0x00000002
DT_CENTER = 0x01
DT_SINGLELINE = 0x20

SPLASH_W = 280
SPLASH_H = 120
CLASS_NAME = "CreamSplash"
BG_COLOR = 0x00170D0D

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)

user32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_long

# Without these, ctypes falls back to a default restype/argtype of plain
# c_int (32-bit) for every parameter/return value here. GetModuleHandleW
# returns a pointer-sized module handle that's routinely outside the 32-bit
# range on 64-bit Windows (ASLR randomizes the load address each run) — with
# no restype declared, that handle gets silently truncated/mis-signed on
# return, and then blows up as an OverflowError when the corrupted value is
# later passed into CreateWindowExW's own undeclared (also-c_int) hInstance
# parameter. Declaring real pointer-sized types fixes both ends.
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

_hwnd = None
_dot_count = 0
_proc_ref = None


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM

user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
]
user32.CreateWindowExW.restype = wt.HWND


def _wnd_proc(hwnd, msg, wparam, lparam):
    global _dot_count
    if msg == WM_CREATE:
        user32.SetTimer(hwnd, 1, 400, None)
        return 0
    if msg == WM_TIMER:
        _dot_count = (_dot_count + 1) % 4
        user32.InvalidateRect(hwnd, None, True)
        return 0
    if msg == WM_PAINT:
        ps = (ctypes.c_byte * 72)()
        hdc = user32.BeginPaint(hwnd, ps)

        brush = gdi32.CreateSolidBrush(BG_COLOR)
        rect = wt.RECT(0, 0, SPLASH_W, SPLASH_H)
        user32.FillRect(hdc, ctypes.byref(rect), brush)
        gdi32.DeleteObject(brush)

        gdi32.SetBkMode(hdc, 1)

        font_title = gdi32.CreateFontW(
            22, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 4, 0, "Segoe UI")
        gdi32.SelectObject(hdc, font_title)
        gdi32.SetTextColor(hdc, 0x00FFF0E6)
        r1 = wt.RECT(0, 20, SPLASH_W, 55)
        user32.DrawTextW(hdc, "Cream's Macro", -1,
                         ctypes.byref(r1), DT_CENTER | DT_SINGLELINE)
        gdi32.DeleteObject(font_title)

        font_sub = gdi32.CreateFontW(
            12, 0, 0, 0, 500, 0, 0, 0, 1, 0, 0, 4, 0, "Segoe UI")
        gdi32.SelectObject(hdc, font_sub)
        gdi32.SetTextColor(hdc, 0x009B8B7B)
        r2 = wt.RECT(0, 50, SPLASH_W, 68)
        user32.DrawTextW(hdc, "Anime Squadron", -1,
                         ctypes.byref(r2), DT_CENTER | DT_SINGLELINE)
        gdi32.DeleteObject(font_sub)

        font_load = gdi32.CreateFontW(
            13, 0, 0, 0, 500, 0, 0, 0, 1, 0, 0, 4, 0, "Segoe UI")
        gdi32.SelectObject(hdc, font_load)
        gdi32.SetTextColor(hdc, 0x00FF6A58)
        dots = "." * _dot_count
        r3 = wt.RECT(0, 80, SPLASH_W, 100)
        user32.DrawTextW(hdc, f"Loading{dots}", -1,
                         ctypes.byref(r3), DT_CENTER | DT_SINGLELINE)
        gdi32.DeleteObject(font_load)

        user32.EndPaint(hwnd, ps)
        return 0
    if msg == WM_DESTROY:
        user32.KillTimer(hwnd, 1)
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def show():
    global _hwnd, _proc_ref

    _proc_ref = WNDPROC(_wnd_proc)

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = _proc_ref
    wc.hbrBackground = gdi32.CreateSolidBrush(BG_COLOR)
    wc.lpszClassName = CLASS_NAME
    wc.hInstance = kernel32.GetModuleHandleW(None)

    user32.RegisterClassExW(ctypes.byref(wc))

    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    _hwnd = user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED,
        CLASS_NAME, "Loading",
        WS_POPUP | WS_VISIBLE,
        (sw - SPLASH_W) // 2, (sh - SPLASH_H) // 2,
        SPLASH_W, SPLASH_H,
        0, 0, wc.hInstance, 0
    )

    user32.SetLayeredWindowAttributes(_hwnd, 0, 230, LWA_ALPHA)

    try:
        dwmapi = ctypes.windll.dwmapi
        val = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            _hwnd, 33, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass

    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def show_async():
    t = threading.Thread(target=show, daemon=True)
    t.start()
    return t


def close():
    global _hwnd
    if _hwnd:
        user32.PostMessageW(_hwnd, WM_DESTROY, 0, 0)
        _hwnd = None
