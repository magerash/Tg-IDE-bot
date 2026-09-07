"""Tests for remote input: the mouse buttons, drag, and the timing that got
removed with pyautogui's blanket PAUSE.

Split out of test_web.py when that file passed its 1500-line cap, the same way
test_refine.py was — by feature, not by size. What lives here is everything that
moves the operator's real mouse, plus the gesture rules in the client that decide
WHICH button a finger meant.

Same style as test_web.py: the aiohttp app booted in-process for routes, plain
regex over the client files for UI invariants.
"""
import asyncio
import os
import re
import sys

import pytest
from aiohttp.test_utils import TestClient, TestServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import WEB_TOKEN                   # noqa: E402
from handlers.web import create_web_app        # noqa: E402

AUTH = {"Authorization": f"Bearer {WEB_TOKEN}"}
INDEX = os.path.join(ROOT, "web", "index.html")
COMMON = os.path.join(ROOT, "web", "common.js")


def _run(coro):
    return asyncio.run(coro)


async def _client():
    return TestClient(TestServer(create_web_app()))


def _html():
    """index.html + the shared script it loads — the page as the browser sees it."""
    with open(INDEX, encoding="utf-8") as f, open(COMMON, encoding="utf-8") as g:
        return f.read() + chr(10) + g.read()

def _lightbox_js(html):
    """The viewer's own gesture IIFE. Splitting the page on the first
    addEventListener('pointerdown') lands in the scroll pad, which binds one too —
    and every assertion below then passes or fails about the wrong element."""
    return html.split("const box = document.getElementById('lightbox');")[1]

def test_click_takes_a_button_and_rejects_an_unknown_one():
    """A phone has one finger and a desktop has three buttons. The button must
    reach the OS, and a typo must be a 400 naming the problem — a right click
    silently downgraded to a left click is a context menu that never opens, which
    is indistinguishable from a dead gesture."""
    import pyautogui

    from utils import mouse

    calls = []
    saved = {n: getattr(pyautogui, n) for n in ("moveTo", "mouseDown", "mouseUp")}
    pyautogui.moveTo = lambda x, y: calls.append(("move", x, y))
    pyautogui.mouseDown = lambda button=None: calls.append(("down", button))
    pyautogui.mouseUp = lambda button=None: calls.append(("up", button))
    try:
        mouse.click_at(11, 22, "right")
        assert calls == [("move", 11, 22), ("down", "right"), ("up", "right")], calls

        # Absent is left (clients omit the field); a *wrong* name is an error,
        # never a silent left click.
        calls.clear()
        mouse.click_at(1, 1, "")
        assert ("down", "left") in calls
        for bad in ("four", "LEFTT", "rihgt", "0"):
            with pytest.raises(ValueError):
                mouse.click_at(1, 1, bad)

        calls.clear()
        mouse.click_at(5, 6, "left", True)
        assert [c[0] for c in calls] == ["move", "down", "up", "down", "up"], \
            "a double click is two down/up pairs, not a special API call"
    finally:
        for n, f in saved.items():
            setattr(pyautogui, n, f)

    async def go():
        async with await _client() as c:
            r = await c.post("/api/click", json={"x": 1, "y": 1, "button": "sideways"},
                             headers=AUTH)
            assert r.status == 400, "an unknown button must not reach the OS as a 500"
            assert "button" in (await r.json())["error"]
            r = await c.post("/api/drag", json={"x": 1, "y": 1, "to_x": 2, "to_y": 2})
            assert r.status == 401, "drag moves the operator's mouse — never unauthenticated"
    _run(go())


def test_double_click_gap_stays_under_the_os_window():
    """Windows merges two down/up pairs into a double click only inside
    GetDoubleClickTime — user-configurable, 500ms by default. The gap is clamped
    to a fraction of the REAL value, because a machine set to 200ms would turn
    every double click into two singles and nothing would say why."""
    import pathlib

    from config import MOUSE_DOUBLE_GAP
    from utils import mouse

    osw = mouse.double_click_time()
    assert osw > 0, "the OS double-click window must be readable or defaulted"
    assert MOUSE_DOUBLE_GAP < osw, "the configured gap already exceeds the OS window"
    src = pathlib.Path(ROOT, "utils", "mouse.py").read_text(encoding="utf-8")
    assert "double_click_time()" in src.split("def click_at")[1].split("def drag")[0], \
        "the gap is not clamped to the machine's own double-click window"


def test_drag_releases_the_button_even_when_the_move_fails():
    """A held button that never comes up wedges the desktop — every mouse move
    becomes a selection — and the phone that started it cannot see, let alone fix,
    that state. The release lives in a finally for exactly this."""
    import pyautogui

    from utils import mouse

    calls = []
    boom = [False]

    def _move(x, y):
        calls.append(("move", x, y))
        if boom[0] and len(calls) > 2:
            raise RuntimeError("display disconnected mid-drag")

    saved = {n: getattr(pyautogui, n) for n in ("moveTo", "mouseDown", "mouseUp")}
    pyautogui.moveTo = _move
    pyautogui.mouseDown = lambda button=None: calls.append(("down", button))
    pyautogui.mouseUp = lambda button=None: calls.append(("up", button))
    try:
        res = mouse.drag(0, 0, 100, 50, "left", steps=2)
        assert calls[0] == ("move", 0, 0) and calls[1] == ("down", "left")
        assert ("move", 50, 25) in calls, "a drag must interpolate — one jump starts no drag"
        assert calls[-1] == ("up", "left") and calls[-2] == ("move", 100, 50)
        assert res["to"] == [100, 50] and res["steps"] == 2

        calls.clear()
        boom[0] = True
        with pytest.raises(RuntimeError):
            mouse.drag(0, 0, 100, 50, "left", steps=4)
        assert ("up", "left") in calls, "the button stayed down after a failed drag"
    finally:
        for n, f in saved.items():
            setattr(pyautogui, n, f)


def test_every_click_path_uses_the_mouse_module():
    """pyautogui.PAUSE is 0, so a bare pyautogui.click fires the button before the
    target window has processed the move — the click lands on a control that has
    not registered the hover. utils/mouse.py owns the settle; a caller that goes
    straight to pyautogui skips it, and the symptom (a menu that opens on the
    second try) never points back here."""
    import pathlib

    import pyautogui

    import handlers.input  # noqa: F401 — importing it is what sets PAUSE

    assert pyautogui.PAUSE == 0, "the blanket 100ms-per-call sleep is back"
    src = pathlib.Path(ROOT, "handlers", "input.py").read_text(encoding="utf-8")
    assert "pyautogui.PAUSE = 0" in src, "PAUSE must be set where FAILSAFE is, not by accident"

    for name in ("handlers/web.py", "handlers/input.py", "handlers/panel.py",
                 "handlers/web_extra.py", "utils/scheduler.py"):
        body = pathlib.Path(ROOT, name).read_text(encoding="utf-8")
        # Comments stripped: a comment that NAMES the banned call ("click_at, never
        # pyautogui.click") is documentation, and a rule that fires on its own
        # explanation teaches people to delete the explanation.
        code = "\n".join(ln.split("#")[0] for ln in body.splitlines())
        for banned in ("pyautogui.click", "pyautogui.doubleClick", "pyautogui.rightClick",
                       "pyautogui.mouseDown", "pyautogui.dragTo"):
            assert banned not in code, f"{name} clicks without the settle ({banned})"

    ms = pathlib.Path(ROOT, "utils", "mouse.py").read_text(encoding="utf-8")
    scroll = ms.split("def scroll_at")[1]
    assert scroll.index("MOUSE_MOVE_SETTLE") < scroll.index("pyautogui.scroll"), \
        "the wheel is stamped with the cursor position it is injected at — the move must land first"


def test_two_finger_tap_is_a_right_click():
    """The gesture Moonlight and the Microsoft RD client both use. Long-press was
    rejected: on every client that ships it, users report it as 'the PC thinks the
    left button is held down'.

    It was previously impossible by construction — _lb.multi is set on the second
    pointerdown and pointerup returned early on it, and the pinch branch set
    moved=true on the first pixel of jitter, which two fingers landing together
    always produce."""
    html = _html()
    assert "RIGHT_TAP_MS" in html and "TAP_MOVE_PX" in html, "gesture thresholds are magic numbers"
    lb = _lightbox_js(html)

    move = lb.split("addEventListener('pointermove'")[1].split("addEventListener(")[0]
    two = move.split("_lb.ptrs.size === 2")[1]
    assert "_lb.moved = true;" not in two.split("if (Math.abs(d")[0], \
        "the pinch branch marks movement before any span change — a two-finger tap can never fire"
    assert "TAP_MOVE_PX" in two, "pinch detection has no movement threshold"

    up = lb.split("addEventListener('pointerup'")[1].split("addEventListener(")[0]
    assert up.index("peak === 2") < up.index("_lb.multi) return"), \
        "the right click is checked after the guard that swallows every two-finger gesture"
    assert "'right'" in up, "the two-finger branch does not send a right button"
    assert "_lb.down" in html, "a tap is anchored where the fingers LANDED, not where they drifted to"

    # The same gesture on the un-zoomed live view, where most taps happen. The
    # browser still synthesises a click from the first finger; it must be swallowed
    # or a right click also sends a left one.
    img = html.split("function bindImgClick()")[1].split("let _imgSuppressClick")[0]
    assert "onpointerdown" in img and "g.peak" in img, "the live view sees only clicks, not fingers"
    assert "_imgSuppressClick = true" in img, "the synthetic click after a two-finger tap is not suppressed"
    assert "_imgSuppressClick) return" in img, "the suppression flag is set but never read"


def test_drag_needs_a_hold_and_never_pans_at_the_same_time():
    """Press-and-hold arms it, because an immediate finger drag is the pan that
    reaches the rest of a zoomed screenshot and cannot be given up. Once armed the
    view must hold still: panning under an armed drag moves the picture beneath the
    gesture and the drop lands where the operator never pointed."""
    html = _html()
    assert "DRAG_HOLD_MS" in html, "the arming delay is a magic number"
    lb = _lightbox_js(html)

    down = lb.split("addEventListener('pointerdown'")[1].split("addEventListener(")[0]
    # The arming must be INSIDE the timer, not merely near a constant of that name:
    # a version that armed on touch and only cleared a timer afterwards passed an
    # earlier form of this assertion, and armed a drag on every tap.
    assert re.search(r"setTimeout\(\(\) => \{[\s\S]*?dragArmed = true[\s\S]*?\}, DRAG_HOLD_MS\)", down), \
        "drag arms without a hold"
    assert "clearTimeout(_lb.dragTimer)" in down, "the arming timer outlives its gesture"
    assert "_lb.click" in down, "drag arms outside click mode, where a tap is not a click"

    move = lb.split("addEventListener('pointermove'")[1].split("addEventListener(")[0]
    assert "if (!_lb.dragArmed) { _lb.tx" in move, "the view pans while a drag is armed"

    cancel = lb.split("addEventListener('pointercancel'")[1].split("});")[0]
    assert "dragArmed = false" in cancel, \
        "a gesture the OS steals leaves the drag armed, and the next release drags from a forgotten point"

    assert "'/api/drag'" in html, "nothing sends the drag"
    assert "to_x" in html and "to_y" in html, "the drag payload does not match the endpoint"


def test_double_tap_window_is_one_constant_on_both_surfaces():
    """Both the live view and the zoomed viewer hold a first tap back, waiting to
    see whether it is half of a double click. Two literals is how the two surfaces
    drift apart under a thumb — and the delay is paid by EVERY single click, so the
    number is a real trade-off and belongs where the other gesture thresholds are.

    280ms was tighter than any platform default (Windows GetDoubleClickTime is
    500ms) and double clicks were being missed on the phone."""
    html = _html()
    assert re.search(r"const DOUBLE_TAP_MS = (\d+);", html), "the double-tap window is not a constant"
    ms = int(re.search(r"const DOUBLE_TAP_MS = (\d+);", html).group(1))
    assert 300 <= ms <= 500, f"a {ms}ms window is outside what a thumb and a platform agree on"

    # Both timers, and no bare literal left behind in either.
    live = html.split("function bindImgClick()")[1].split("let _imgSuppressClick")[0]
    viewer = html.split("function _lbTapClick")[1].split("async function")[0]
    for name, body in (("live view", live), ("viewer", viewer)):
        assert "DOUBLE_TAP_MS)" in body, f"the {name} still hardcodes its own tap window"
        assert not re.search(r"\}, \d+\);", body), f"the {name} has a magic-number timer again"


def test_a_hold_is_a_right_click_unless_the_finger_then_moves():
    """Hold-for-right-click is what people arrive expecting, and it is also the
    drag gesture. One hold, two meanings, separated by what happens AFTER it is
    recognised: released in place = right click, moved past DRAG_MOVE_PX = drag.

    The threshold is coarser than TAP_MOVE_PX on purpose — a finger resting on
    glass for 350ms always drifts, and a drifting right click that turns into a
    16px drag is how a context menu becomes a moved file."""
    html = _html()
    assert re.search(r"const DRAG_MOVE_PX = (\d+);", html), "the drag/right-click split is a magic number"
    drag_px = int(re.search(r"const DRAG_MOVE_PX = (\d+);", html).group(1))
    tap_px = int(re.search(r"TAP_MOVE_PX = (\d+)", html).group(1))
    assert drag_px > tap_px, "committing to a drag must take more movement than merely not being a tap"

    lb = _lightbox_js(html)
    move = lb.split("addEventListener('pointermove'")[1].split("addEventListener(")[0]
    assert "DRAG_MOVE_PX" in move and "_lb.dragging = true" in move, \
        "nothing promotes an armed hold into an actual drag"

    up = lb.split("addEventListener('pointerup'")[1].split("addEventListener(")[0]
    armed = up.split("if (_lb.dragArmed) {")[1].split("\n    }")[0]
    assert "'right'" in armed, "a hold released in place does not send a right click"
    assert "doDrag(" in armed, "a hold that moved does not send a drag"
    assert armed.index("!dragging") < armed.index("doDrag("), \
        "the right-click case must be decided before the drag one, or a still finger drags 0px"

    # The live view has no drag (a finger moving there scrolls the page), so the
    # same hold has exactly one meaning — and the OS must not answer it first.
    live = html.split("function bindImgClick()")[1].split("let _imgSuppressClick")[0]
    assert "holdTimer" in live and "DRAG_HOLD_MS" in live, "no hold on the live view"
    assert "g.held = true" in live, "the hold is never recognised"
    assert "oncontextmenu" in live, "the OS 'save image' sheet answers the long press instead of us"
    css = html.split("#screen-area img{")[1].split("}")[0]
    assert "touch-callout" in css, "a long press on an <img> pops the native sheet and cancels the gesture"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
