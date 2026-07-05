"""Minimal system tray icon (Shell_NotifyIcon) with click-to-restore.

Implemented with raw ctypes instead of a pystray/Pillow dependency to keep
the Nuitka build lean. Owns a small hidden window (its own window class,
its own message pump thread) purely to receive the tray icon's callback
message — it never touches pywebview's real window, so there's no risk of
interfering with its WinForms/Edge message loop.
"""
import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
TRAY_ID = 1
CLASS_NAME = "CreamsMacroTrayWnd"


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

_state = {
    "hwnd": 0,
    "thread": None,
    "on_restore": None,
    "wndproc_cb": None,
}


def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_TRAYICON and lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
        cb = _state["on_restore"]
        if cb:
            try:
                cb()
            except Exception:
                pass
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _thread_main(ready: threading.Event):
    hinstance = kernel32.GetModuleHandleW(None)
    wndproc_cb = WNDPROC(_wndproc)
    _state["wndproc_cb"] = wndproc_cb  # keep alive, GC would crash the callback

    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = wndproc_cb
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hinstance
    wc.hIcon = 0
    wc.hCursor = 0
    wc.hbrBackground = 0
    wc.lpszMenuName = None
    wc.lpszClassName = CLASS_NAME
    user32.RegisterClassW(ctypes.byref(wc))

    hwnd = user32.CreateWindowExW(0, CLASS_NAME, CLASS_NAME, 0, 0, 0, 0, 0, 0, 0, hinstance, None)
    _state["hwnd"] = hwnd
    ready.set()

    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def _ensure_thread():
    if _state["thread"] is not None:
        return
    ready = threading.Event()
    t = threading.Thread(target=_thread_main, args=(ready,), daemon=True)
    _state["thread"] = t
    t.start()
    ready.wait(timeout=5)


def add_icon(icon_path: str, tooltip: str, on_restore):
    """Show the tray icon. on_restore fires on left click/double-click."""
    _ensure_thread()
    _state["on_restore"] = on_restore
    hwnd = _state["hwnd"]
    if not hwnd:
        return

    hicon = 0
    if icon_path:
        hicon = user32.LoadImageW(0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = TRAY_ID
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAYICON
    nid.hIcon = hicon
    nid.szTip = tooltip[:127]
    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))


def remove_icon():
    hwnd = _state["hwnd"]
    if not hwnd:
        return
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = TRAY_ID
    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
