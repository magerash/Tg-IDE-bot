"""E2 / E6 — does a ``KEYEVENTF_UNICODE`` keystroke reach Claude Code in Windows Terminal
at typing speed, and do Cyrillic, combining marks and emoji survive the same path?

Experiment from docs/analysis/remote-control-architecture.md §18. Row 17 is gated on it.

    python tools/experiments/e2_unicode_type.py            # countdown, then type into the focused window
    python tools/experiments/e2_unicode_type.py --dry      # print the plan, send nothing
    python tools/experiments/e2_unicode_type.py --rates 10,20 --countdown 5 --no-e6

After the countdown it types marker strings into WHATEVER WINDOW HAS FOCUS. It never sends
Enter, a control character or a modifier. Read the target's input line back against the
expected line this script prints, byte for byte — that comparison is the result.

Mechanism (the one row 17 will ship): ``SendInput`` with ``wVk = 0``, the UTF-16 code unit in
``wScan`` and ``KEYEVENTF_UNICODE``. Windows delivers ``VK_PACKET``; ``TranslateMessage`` turns
it into ``WM_CHAR`` with that exact unit, and ``VkKeyScanW`` is never consulted, so the active
keyboard layout cannot mangle it. Code points above the BMP go as two units (a surrogate pair),
each its own down/up.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.window import get_active_window_process, get_active_window_title  # noqa: E402

_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_u32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
_u32.SendInput.restype = wintypes.UINT


def _key(unit: int, up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, unit, flags, 0, 0))


def send_char(ch: str) -> tuple[int, int]:
    """One character → its UTF-16 units, each a down/up pair, in ONE SendInput call.

    Returns (events requested, events inserted). Refuses control characters: this path
    carries text and nothing else — Enter has its own, sequenced, path (D-005).
    """
    if ord(ch) < 0x20 or ch == "\x7f":
        raise ValueError(f"control character U+{ord(ch):04X} refused")
    units = [int.from_bytes(ch.encode("utf-16-le")[i:i + 2], "little")
             for i in range(0, len(ch.encode("utf-16-le")), 2)]
    events = []
    for u in units:
        events.append(_key(u, False))
        events.append(_key(u, True))
    arr = (INPUT * len(events))(*events)
    sent = _u32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    return len(events), sent


def type_burst(text: str, cps: float, dry: bool) -> dict:
    """Type *text* at *cps* characters per second, pacing against the clock (not sleep
    accumulation) so the effective rate is the requested one, not "requested minus overhead"."""
    period = 1.0 / cps
    t0 = time.perf_counter()
    short = 0
    for i, ch in enumerate(text):
        target = t0 + i * period
        while (now := time.perf_counter()) < target:
            time.sleep(min(0.002, target - now))
        if not dry:
            want, got = send_char(ch)
            if got != want:
                short += 1
                err = _k32.GetLastError()
                print(f"    ! U+{ord(ch):04X} inserted {got}/{want} (GetLastError={err})")
    elapsed = time.perf_counter() - t0
    return {"cps_requested": cps, "chars": len(text), "elapsed_s": round(elapsed, 3),
            "cps_effective": round(len(text) / elapsed, 1) if elapsed else None,
            "short_calls": short}


def codepoints(s: str) -> str:
    return " ".join(f"U+{ord(c):04X}" for c in s)


E2_ALPHABET = "0123456789ABCDEFGHIJ"          # order is visible; a drop or a swap shows
E6_TEXT = "Привет_мир é é 🙂 ✓ ∑ №"    # Cyrillic · precomposed é · e + U+0301 · astral emoji · symbols


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rates", default="5,10,20,50", help="chars per second, comma-separated")
    ap.add_argument("--countdown", type=float, default=12, help="seconds to focus the target")
    ap.add_argument("--no-e6", action="store_true", help="skip the mixed-script burst")
    ap.add_argument("--dry", action="store_true", help="print the plan, send nothing")
    ap.add_argument("--require", default="", metavar="PROC",
                    help="abort unless the foreground process name contains this (e.g. WindowsTerminal)")
    ap.add_argument("--require-title", default="", metavar="TEXT",
                    help="abort unless the foreground window TITLE contains this. A terminal is one "
                         "process for every tab in it, so --require cannot tell a shell tab from a "
                         "Claude Code tab; the title is what changes per tab (and is why D-007 uses "
                         "the process for terminal-NESS and the title is only ever a target hint)")
    a = ap.parse_args()
    rates = [float(r) for r in a.rates.split(",") if r]

    bursts = [(f"[r{int(r):02d}]{E2_ALPHABET}", r) for r in rates]
    if not a.no_e6:
        bursts.append((f"[e6]{E6_TEXT}", 10.0))
    expected = " ".join(t for t, _ in bursts) + " "

    print("E2/E6 unicode typing experiment")
    print(f"  bursts   : {[(t, r) for t, r in bursts]}")
    print(f"  expected : {expected!r}")
    if not a.no_e6:
        print(f"  e6 units : {codepoints(E6_TEXT)}")
    print(f"  INPUT is {ctypes.sizeof(INPUT)} bytes (40 expected on x64)")
    if a.dry:
        for t, r in bursts:
            print(" ", type_burst(t, r, dry=True))
        print("dry run — nothing sent")
        return 0

    own_console = _k32.GetConsoleWindow()
    print(f"\nFOCUS THE TARGET WINDOW NOW — typing starts in {a.countdown:.0f}s", flush=True)
    for left in range(int(a.countdown), 0, -1):
        print(f"  {left}…", end=" ", flush=True)
        time.sleep(1)
    print()
    fg = _u32.GetForegroundWindow()
    if own_console and fg == own_console:
        print("ABORT: the foreground window is still this script's own console")
        return 2
    proc = get_active_window_process()
    print(f"  target   : {get_active_window_title()!r} / {proc!r}")
    if a.require and a.require.lower() not in proc.lower():
        print(f"ABORT: foreground process {proc!r} does not match --require {a.require!r}; nothing sent")
        return 3
    title = get_active_window_title()
    if a.require_title and a.require_title.lower() not in title.lower():
        print(f"ABORT: foreground title {title!r} does not contain --require-title "
              f"{a.require_title!r}; nothing sent")
        return 4

    results = []
    for text, cps in bursts:
        print(f"  typing {text!r} at {cps:g} cps  → fg {get_active_window_title()!r}", flush=True)
        results.append(type_burst(text, cps, dry=False))
        send_char(" ")
        time.sleep(0.4)          # a visible gap between bursts, and a settle for the terminal

    print(f"\n  foreground after: {get_active_window_title()!r} / {get_active_window_process()!r}")
    print("\nresults:")
    for r in results:
        print("  ", r)
    print(f"\nexpected line, compare byte for byte:\n  {expected!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
