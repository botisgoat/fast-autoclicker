"""Fast Auto Clicker for Windows.

Press the hotkey (default F6) to start clicking at the mouse cursor,
press it again to stop. Interval, mouse button and hotkey are set in
the window and saved to settings.json next to this file.

No third-party packages: uses only the Python standard library and
Windows APIs (SendInput, GetAsyncKeyState, timeBeginPeriod).
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "settings.json")
LOG_FILE = os.path.join(HERE, "autoclicker.log")

DEFAULTS = {"interval_ms": 8.0, "button": "left", "hotkey": "F6"}
MIN_INTERVAL_MS = 1.0
MAX_INTERVAL_MS = 10000.0

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")

# ---------------------------------------------------------------- SendInput
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wt.UINT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short

# (down flag, up flag)
BUTTONS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}

HOTKEYS = {f"F{n}": 0x6F + n for n in range(1, 13)}  # F1=0x70 ... F12=0x7B


def send_mouse(flags):
    """Send one mouse event at the current cursor position."""
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi.dwFlags = flags
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def send_key(vk, up=False):
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki.wVk = vk
    inp.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


# ------------------------------------------------------------ timer setup
class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [("Version", wt.ULONG), ("ControlMask", wt.ULONG),
                ("StateMask", wt.ULONG)]


def setup_timing():
    """Ask Windows for 1 ms timer resolution and keep it even when the
    window is minimised or behind a fullscreen game (Windows 11 otherwise
    drops back to ~15.6 ms for hidden windows)."""
    winmm.timeBeginPeriod(1)
    try:
        state = PROCESS_POWER_THROTTLING_STATE(
            Version=1,
            # EXECUTION_SPEED (0x1) | IGNORE_TIMER_RESOLUTION (0x4)
            ControlMask=0x1 | 0x4,
            StateMask=0,  # 0 = do NOT throttle
        )
        kernel32.SetProcessInformation(
            kernel32.GetCurrentProcess(), 4,  # ProcessPowerThrottling
            ctypes.byref(state), ctypes.sizeof(state))
    except Exception:
        pass


def teardown_timing():
    winmm.timeEndPeriod(1)


def wait_until(deadline):
    """Sleep most of the way, then spin for the last ~1.5 ms for accuracy."""
    remaining = deadline - time.perf_counter()
    if remaining > 0.002:
        time.sleep(remaining - 0.0015)
    while time.perf_counter() < deadline:
        pass


# ------------------------------------------------------------ click engine
class Clicker:
    def __init__(self, inject=send_mouse):
        self.inject = inject
        self.interval_ms = DEFAULTS["interval_ms"]
        self.button = DEFAULTS["button"]
        self.clicks = 0
        self.active = threading.Event()
        self.quit = threading.Event()
        self._wake = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start_thread(self):
        self.thread.start()

    def start(self):
        self.active.set()
        self._wake.set()

    def stop(self):
        self.active.clear()

    def toggle(self):
        self.stop() if self.active.is_set() else self.start()

    def shutdown(self):
        self.active.clear()
        self.quit.set()
        self._wake.set()

    def _loop(self):
        while not self.quit.is_set():
            if not self.active.is_set():
                self._wake.wait(0.1)
                self._wake.clear()
                continue
            nxt = time.perf_counter()
            while self.active.is_set() and not self.quit.is_set():
                iv = max(self.interval_ms, MIN_INTERVAL_MS) / 1000.0
                down, up = BUTTONS.get(self.button, BUTTONS["left"])
                wait_until(nxt)
                self.inject(down)
                # hold the button for half the interval so games that check
                # the button state once per frame still see the press
                wait_until(nxt + iv / 2)
                self.inject(up)
                self.clicks += 1
                nxt += iv
                now = time.perf_counter()
                if now - nxt > iv:  # fell behind: resync, don't burst
                    nxt = now


# ---------------------------------------------------------- hotkey watcher
class HotkeyWatcher(threading.Thread):
    """Polls the key state globally (works while a game has focus) and
    calls on_press once per key press."""

    def __init__(self, vk, on_press):
        super().__init__(daemon=True)
        self.vk = vk
        self.on_press = on_press
        self.quit = threading.Event()

    def run(self):
        was_down = False
        while not self.quit.is_set():
            down = bool(user32.GetAsyncKeyState(self.vk) & 0x8000)
            if down and not was_down:
                try:
                    self.on_press()
                except Exception:
                    log_exception()
            was_down = down
            time.sleep(0.01)


# ---------------------------------------------------------------- helpers
def log_exception(*args):
    """Append a traceback to autoclicker.log (pythonw has no console)."""
    if len(args) == 3 and isinstance(args[1], BaseException):
        text = "".join(traceback.format_exception(*args))
    elif len(args) == 1 and hasattr(args[0], "exc_value"):  # threading hook
        a = args[0]
        text = "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback))
    else:
        text = traceback.format_exc()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except Exception:
        pass


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    try:
        s["interval_ms"] = min(max(float(s["interval_ms"]), MIN_INTERVAL_MS), MAX_INTERVAL_MS)
    except Exception:
        s["interval_ms"] = DEFAULTS["interval_ms"]
    if s.get("button") not in BUTTONS:
        s["button"] = DEFAULTS["button"]
    if s.get("hotkey") not in HOTKEYS:
        s["hotkey"] = DEFAULTS["hotkey"]
    return s


def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        log_exception()


# -------------------------------------------------------------------- GUI
def main():
    import tkinter as tk
    from tkinter import ttk

    setup_timing()
    settings = load_settings()

    clicker = Clicker()
    clicker.interval_ms = settings["interval_ms"]
    clicker.button = settings["button"]
    clicker.start_thread()

    root = tk.Tk()
    root.title("Fast Auto Clicker")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.report_callback_exception = log_exception

    pad = {"padx": 10, "pady": 4}
    frm = ttk.Frame(root, padding=10)
    frm.grid()

    # interval
    ttk.Label(frm, text="Interval (ms):").grid(row=0, column=0, sticky="w", **pad)
    interval_var = tk.StringVar(value=f"{settings['interval_ms']:g}")
    spin = ttk.Spinbox(frm, from_=MIN_INTERVAL_MS, to=MAX_INTERVAL_MS, increment=1,
                       textvariable=interval_var, width=8)
    spin.grid(row=0, column=1, sticky="w", **pad)
    rate_lbl = ttk.Label(frm, text="")
    rate_lbl.grid(row=0, column=2, sticky="w", **pad)

    # button
    ttk.Label(frm, text="Mouse button:").grid(row=1, column=0, sticky="w", **pad)
    button_var = tk.StringVar(value=settings["button"])
    bfrm = ttk.Frame(frm)
    bfrm.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
    for name in ("left", "right", "middle"):
        ttk.Radiobutton(bfrm, text=name.title(), value=name,
                        variable=button_var).pack(side="left", padx=(0, 8))

    # hotkey
    ttk.Label(frm, text="Start/stop hotkey:").grid(row=2, column=0, sticky="w", **pad)
    hotkey_var = tk.StringVar(value=settings["hotkey"])
    hk = ttk.Combobox(frm, values=list(HOTKEYS), textvariable=hotkey_var,
                      width=6, state="readonly")
    hk.grid(row=2, column=1, sticky="w", **pad)

    status = tk.Label(frm, text="", font=("Segoe UI", 12, "bold"), width=34)
    status.grid(row=3, column=0, columnspan=3, pady=(10, 2))
    hint = ttk.Label(frm, text="", foreground="#555")
    hint.grid(row=4, column=0, columnspan=3)

    watcher = {"w": None}

    def set_hotkey(*_):
        name = hotkey_var.get()
        if watcher["w"]:
            watcher["w"].quit.set()
        w = HotkeyWatcher(HOTKEYS[name], clicker.toggle)
        w.start()
        watcher["w"] = w
        settings["hotkey"] = name
        save_settings(settings)
        hint.config(text=f"Press {name} anywhere (even in a game) to start / stop.")

    def apply_interval(*_):
        try:
            v = float(interval_var.get())
        except ValueError:
            return
        v = min(max(v, MIN_INTERVAL_MS), MAX_INTERVAL_MS)
        clicker.interval_ms = v
        settings["interval_ms"] = v
        save_settings(settings)
        rate_lbl.config(text=f"= {1000.0 / v:.0f} clicks/s target")

    def apply_button(*_):
        clicker.button = button_var.get()
        settings["button"] = clicker.button
        save_settings(settings)

    interval_var.trace_add("write", apply_interval)
    button_var.trace_add("write", apply_button)
    hotkey_var.trace_add("write", set_hotkey)
    apply_interval()
    set_hotkey()

    last = {"t": time.perf_counter(), "c": 0}

    def refresh():
        now = time.perf_counter()
        c = clicker.clicks
        rate = (c - last["c"]) / max(now - last["t"], 1e-6)
        last.update(t=now, c=c)
        if clicker.active.is_set():
            status.config(text=f"CLICKING  —  {rate:.0f} clicks/s", fg="#0a0")
        else:
            status.config(text="STOPPED", fg="#c00")
        root.after(250, refresh)

    def on_close():
        clicker.shutdown()
        if watcher["w"]:
            watcher["w"].quit.set()
        teardown_timing()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh()
    root.mainloop()


if __name__ == "__main__":
    sys.excepthook = log_exception
    threading.excepthook = log_exception
    try:
        main()
    except Exception:
        log_exception()
        raise
