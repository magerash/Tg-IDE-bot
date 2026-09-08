"""E2 readback — reads one line and prints its code points, so the comparison never
touches a clipboard.

The 2026-09-09 run found the sent ``e`` + U+0301 arriving as precomposed U+00E9. Three
things could have done that: the terminal's input line, the terminal's copy, or the paste
into the chat. This removes the last two — the line is read in-process by ``input()`` and
reported as hex, which is pure ASCII and survives any transport.

    python tools/experiments/e2_readback.py

Then, from another shell, fire the typer at this window and press Enter here:

    python tools/experiments/e2_unicode_type.py --require WindowsTerminal --countdown 15
"""
from __future__ import annotations

import sys
import unicodedata


def main() -> int:
    print("readback ready — type or inject a line here, then press Enter")
    try:
        got = input("> ")
    except (EOFError, KeyboardInterrupt):
        print("\nnothing read")
        return 1

    print(f"\n  length      : {len(got)} code points")
    print(f"  code points : {' '.join(f'U+{ord(c):04X}' for c in got)}")
    nfc = unicodedata.normalize("NFC", got)
    nfd = unicodedata.normalize("NFD", got)
    print(f"  is NFC      : {got == nfc}")
    print(f"  is NFD      : {got == nfd}")
    print(f"  stdin enc   : {sys.stdin.encoding}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
