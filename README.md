# Fast Auto Clicker

A tiny, fast, accurate auto clicker for Windows. One Python file, no installs beyond Python itself.

Press **F6** to start clicking where your mouse is, press **F6** again to stop. It holds a steady **5–10 ms** interval (100–200 clicks per second) or anything you set.

## Features

- **Fast and steady:** a click interval down to 1 ms, measured at exactly 200 clicks/s at 5 ms and 100 clicks/s at 10 ms.
- **Global hotkey:** F6 (or any F1–F12) starts and stops it, even while a game has focus.
- **Live speed change:** edit the interval while it runs and it takes effect immediately.
- **Left, right or middle** mouse button.
- **Game-friendly clicks:** each click holds the button for half the interval, so games that check the mouse once per frame are more likely to catch it.
- **Remembers your settings** in `settings.json` next to the script.
- **Shows the live click rate** it is actually achieving.
- **No dependencies:** only the Python standard library (`tkinter`, `ctypes`) and Windows APIs (`SendInput`, `GetAsyncKeyState`, `timeBeginPeriod`).

## Requirements

- Windows 10 or 11
- Python 3.8 or newer with tkinter (included in the standard python.org installer and in Anaconda/Miniconda)

## How to run

1. Download `autoclicker.pyw` (or clone this repo).
2. Double-click `autoclicker.pyw`, or run:

   ```powershell
   pythonw autoclicker.pyw
   ```

   Use `python autoclicker.pyw` instead if you want to see a console window.

3. A small window opens and stays on top.

**Optional:** make a Desktop shortcut whose target is `pythonw.exe` (full path) followed by the full path to `autoclicker.pyw` in quotes.

## How to use

1. Move the mouse to where you want to click.
2. Press **F6** to start.
3. Press **F6** again to stop.

### Changing the speed

Type a number in the **Interval (ms)** box. Smaller is faster:

| Interval | Clicks per second |
|---------:|------------------:|
| 5 ms     | 200 |
| 8 ms     | 125 (default) |
| 10 ms    | 100 |
| 50 ms    | 20 |

The minimum is 1 ms. You can also pick the mouse button and a different hotkey (F1–F12) in the same window.

## How it stays accurate

Windows normally only wakes sleeping programs about every 15.6 ms, which makes 5–10 ms intervals uneven. The clicker:

- requests 1 ms timer resolution with `timeBeginPeriod(1)`,
- opts out of Windows 11 power throttling, so timing stays accurate when the window is minimised or behind a fullscreen game,
- schedules clicks against a high-resolution clock, sleeping most of each gap and spinning for the last ~1.5 ms.

The spin uses some CPU while clicking, and none while it is stopped.

## Limitations

- **Admin games:** if a game runs as administrator, run the clicker as administrator too, or Windows blocks the clicks.
- **Some games ignore simulated input,** especially ones with anti-cheat or that read the mouse through raw input only.
- **Frame rate caps the useful speed:** a game running at 60 FPS can't register more than about 60 clicks per second, however fast the clicker goes.
- Use it responsibly and check the rules of any online game before using it there.

## Troubleshooting

If the window doesn't open, run `python autoclicker.pyw` to see the error. Errors are also written to `autoclicker.log` next to the script.

## License

[MIT](LICENSE)
