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

def _read_source(rel):
    """A source file as text, for the invariants that are about the code's SHAPE
    rather than its behaviour — the ones a passing call cannot prove."""
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


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


def test_a_click_without_a_point_is_a_400_and_the_client_never_sends_one():
    """bot.log, 2026-09-28: `/api/click error: int() argument must be ... not
    'NoneType'` and a 500. The client had mapped a tap through a zero divisor —
    NaN passes every bounds check, since it compares false to everything — and
    JSON turned the NaN into null. Malformed input is the caller's 400, and the
    one funnel every tap goes through must refuse to produce it."""
    async def go():
        async with await _client() as c:
            for body in ({"x": None, "y": 5}, {"x": 5}, {"y": 5, "x": [1]}):
                r = await c.post("/api/click", json=body, headers=AUTH)
                assert r.status == 400, (body, r.status)
                assert "x and y" in (await r.json())["error"]
    _run(go())

    html = _html()
    fn = html.split("function _mapToScreen(")[1].split("\n}")[0]
    assert "Number.isFinite(x)" in fn and "Number.isFinite(y)" in fn, \
        "a NaN point still leaves _mapToScreen and reaches the server as null"
    assert re.search(r":\s*null;", fn), "a non-finite point must map to null, not through"


def test_a_click_re_targets_keyboard_mode():
    """Keyboard mode guards the window it first typed into (`D-026`). On a desktop
    the operator clicks another window on purpose and types — and the guard read
    that as a focus thief, refused, and switched the mode off (bot.log 17:32:36,
    2026-09-28, `expected 'Жан', foreground is 'Вера'`). A successful click is the
    operator choosing, so the target is re-learned from the next batch."""
    html = _html()
    click = html.split("async function doClick(")[1].split("\n}")[0]
    code = chr(10).join(ln.split("//")[0] for ln in click.splitlines())
    assert re.search(r"if \(r\.ok\) _kbExpect = ''", code), \
        "a click into another window still trips the Keyboard-mode guard"
    # ...and the guard itself must survive: a window that takes the foreground on
    # its own is still refused.
    pump = html.split("async function _kbPump(")[1].split("\n}")[0]
    assert "body.expect = _kbExpect" in pump and "refused === 'foreground'" in pump


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


# --- direct typing: the unicode path (row 17) --------------------------------

def test_unicode_typing_refuses_everything_that_is_not_a_character():
    """The seam between the two input paths, enforced at the door.

    `type_unicode` carries text. Enter is sequenced against a paste by exactly one
    function (`D-005`) and a Tab or an Escape arriving through a text field is a
    keystroke the client never meant to send — so every control character is
    refused here rather than trusted not to arrive. The cap is refused for the same
    reason a stream needs one: an unbounded batch is an unbounded time with the
    keyboard held.
    """
    from config import TYPE_CHARS_MAX
    from handlers.input import type_unicode

    for code, why in ((10, "newline"), (9, "tab"), (27, "escape"),
                      (13, "carriage return"), (127, "delete"), (0, "NUL")):
        with pytest.raises(ValueError) as e:
            type_unicode("a" + chr(code) + "b")
        assert "control" in str(e.value).lower(), f"{why} must be refused by name"
        assert f"U+{code:04X}" in str(e.value), f"{why} must be named in the error"

    with pytest.raises(ValueError) as e:
        type_unicode("x" * (TYPE_CHARS_MAX + 1))
    assert str(TYPE_CHARS_MAX) in str(e.value), "the cap must name itself"


def test_unicode_path_never_touches_a_modifier():
    """A unicode key carries no virtual-key code, so a synthetic Ctrl has nothing
    to combine WITH — the combo silently becomes a literal character. Modifiers and
    named keys stay on press_keys, and the two paths must never merge. This is the
    same shape as `D-008`'s one-file rule: the failure is silent, so a test has to
    be the thing that notices.
    """
    src = _read_source("handlers/input.py")
    body = src.split("def type_unicode(")[1].split(chr(10) + "def ")[0]
    body = re.sub(r"#.*", "", body)          # a rule must not fire on its own explanation
    body = re.sub(r'"""(.|\n)*?"""', "", body)
    for forbidden in ("press_keys", "_VK", "keybd_event", "hotkey", "pyautogui"):
        assert forbidden not in body, \
            f"type_unicode reaches for {forbidden} — the two input paths have merged"

    # And the structure Windows actually validates: the union must carry MOUSEINPUT
    # or sizeof(INPUT) is 32, whereupon SendInput rejects EVERY call with error 87
    # and sends nothing. E2 failed exactly this way before it succeeded.
    import ctypes

    from handlers.input import _INPUT
    assert ctypes.sizeof(_INPUT) == 40, "sizeof(INPUT) must be 40 on x64"


def test_astral_characters_go_out_as_one_call():
    """An emoji is two UTF-16 units — a surrogate pair — and both must ride the same
    SendInput call. Split across two calls the target can see two lone surrogates,
    which is a mangled character rather than a missing one. Measured arriving intact
    in E2 (2026-09-09); this is what keeps it that way.
    """
    import handlers.input as inp

    calls = []
    saved = inp._u32.SendInput

    def fake(n, arr, size):
        calls.append([arr[i].ki.wScan for i in range(n)])
        return n
    try:
        inp._u32.SendInput = fake
        assert inp._send_char("a") == (2, 2), "one BMP char is one down/up pair"
        assert calls[-1] == [0x0061, 0x0061]

        calls.clear()
        inp._send_char("\U0001F642")
        assert len(calls) == 1, "a surrogate pair must not be split across calls"
        assert calls[0] == [0xD83D, 0xD83D, 0xDE42, 0xDE42], calls[0]
    finally:
        inp._u32.SendInput = saved


def test_chars_endpoint_guards_the_target_instead_of_focusing_it():
    """`expect` refuses; it does not focus. E2 measured a verified focus going stale
    800ms later and putting 62 characters into an unrelated editor — focusing per
    batch would re-run that race on every batch, at typing speed. So the client
    states what it believes it is typing into and a mismatch sends nothing.
    """
    import handlers.input as inp
    import utils.window as win

    typed = []
    saved_type, saved_title = inp.type_unicode, win.get_active_window_title

    def fake(text):
        typed.append(text)
        return "Claude Code", "windowsterminal.exe", len(text)

    async def go():
        async with await _client() as c:
            r = await c.post("/api/chars", json={"text": "hi"})
            assert r.status == 401, "keystrokes into the desktop — never unauthenticated"

            r = await c.post("/api/chars", json={"text": "ok"}, headers=AUTH)
            body = await r.json()
            assert body["ok"] and body["sent"] == 2 and typed == ["ok"]

            # The guard: a foreground that is not what the caller expected sends
            # NOTHING, and says so rather than answering a cheerful ok.
            typed.clear()
            r = await c.post("/api/chars",
                             json={"text": "secret", "expect": "Some Other Window"},
                             headers=AUTH)
            body = await r.json()
            assert body["ok"] is False and body["refused"] == "foreground", body
            assert body["sent"] == 0 and typed == [], "a refused batch must not type"

            # Matching expectation types normally.
            r = await c.post("/api/chars",
                             json={"text": "yes", "expect": "Claude Code"}, headers=AUTH)
            assert (await r.json())["ok"], "a matching foreground must not be refused"
            assert typed == ["yes"]

            # A control character is a 400 naming the problem, not a 500 — checked
            # against the REAL function, since the refusal is the thing under test.
            inp.type_unicode = saved_type
            r = await c.post("/api/chars", json={"text": "a" + chr(10)}, headers=AUTH)
            assert r.status == 400 and "control" in (await r.json())["error"].lower()

    try:
        inp.type_unicode = fake
        win.get_active_window_title = lambda: "Claude Code"
        _run(go())
    finally:
        inp.type_unicode, win.get_active_window_title = saved_type, saved_title


def test_typing_sink_is_a_password_field_that_can_actually_take_focus():
    """Two independent traps, both fatal and both silent.

    `display:none` cannot take focus, so a hidden field raises no keyboard at all
    and the mode looks dead. And Chrome-for-Android ignores `autocomplete` and
    `spellcheck` on a text field, which is why xterm.js and noVNC both land on
    `type=password` inside a form — an autocorrect here rewrites characters that
    are already inside a terminal on the PC, and a keystroke cannot be un-sent.
    """
    html = _html()
    sink = html.split('id="kb-sink"')[0].rsplit("<input", 1)[1] + \
        html.split('id="kb-sink"')[1].split(">")[0]
    assert 'type="password"' in sink, "the sink must be a password field, or autocorrect stays on"
    for attr in ("autocomplete=\"off\"", "autocapitalize=\"off\"",
                 "autocorrect=\"off\"", "spellcheck=\"false\""):
        assert attr in sink, f"the sink is missing {attr}"
    assert "<form" in html.split('id="kb-sink"')[0].rsplit("<input", 1)[0][-400:], \
        "the sink must sit inside a form — the half of the trick that silences the suggestion strip"

    css = html.split("#kb-sink{")[1].split("}")[0]
    assert "display:none" not in css.replace(" ", ""), \
        "display:none cannot take focus and raises no keyboard"
    assert "font-size:16px" in css.replace(" ", ""), \
        "under 16px iOS zooms the page when the field takes focus"


def test_typing_uses_beforeinput_and_never_forwards_a_composition_in_progress():
    """`keydown` cannot carry the character on a phone — UI Events REQUIRES keyCode
    229 while a soft keyboard composes, which on Android is nearly every letter. And
    `insertCompositionText` fires repeatedly with intermediate guesses: forwarding it
    sends a predicted word letter by letter and then the committed word again.
    """
    html = _html()
    kb = html.split("function bindKbSink()")[1].split(chr(10) + "}")[0]
    assert "'beforeinput'" in kb, "beforeinput is the primary signal"
    assert "insertCompositionText" in kb and "return" in kb, \
        "composition text must be skipped, not forwarded"
    assert "'compositionend'" in kb, "the committed word arrives at compositionend"
    assert "insertText" in kb and "deleteContentBackward" in kb, \
        "the inputType switch lost a case that carries characters"


def test_named_keys_never_ride_the_character_path():
    """A unicode key carries no virtual-key code, so Enter and Backspace cannot be
    characters — they are VK codes through /api/key. The client must honour the same
    split the server enforces at its door, or the two paths merge on one surface
    only, which is how every bug in this project's typing history started.
    """
    html = _html()
    pump = html.split("async function _kbPump()")[1].split(chr(10) + "}")[0]
    assert "/api/chars" in pump and "/api/key" in pump, "both paths leave through the pump"
    chars_call = pump.split("/api/chars")[0]
    assert "op.t === 'key'" in chars_call, \
        "a named key must be routed away BEFORE the character request is built"

    kb = html.split("function bindKbSink()")[1].split(chr(10) + "}")[0]
    for it, key in (("insertLineBreak", "enter"), ("deleteContentBackward", "backspace")):
        line = [l for l in kb.splitlines() if it in l]
        assert line and f"_kbKey('{key}')" in line[0], \
            f"{it} must go out as the named key {key}, not as a character"


def test_typing_requests_chain_and_never_run_concurrently():
    """`D-011`: everything on this page rides ONE reverse-SSH pipe, so a request
    fired on a timer rather than from the previous one's completion piles up and the
    live view stops updating underneath the typing. A stream of keystrokes is the
    worst possible thing to send on a fixed interval.
    """
    html = _html()
    block = html.split("const TYPE_BATCH_MS")[1].split("function _kbRefocus")[0]
    assert "setInterval" not in block, "typing must chain from completion, never setInterval"
    pump = html.split("async function _kbPump()")[1].split(chr(10) + "}")[0]
    assert "_kbSending" in pump and "await" in pump, \
        "the pump must hold a sending flag and await each request"
    assert "while (_kbQ.length)" in pump, "the queue drains in order, one request at a time"

    # The batch window is an engineering choice justified by this transport's
    # ~133ms round trip, not a cited practice — but it must exist.
    assert re.search(r"const TYPE_BATCH_MS = \d+;", html), "the batch window must be a named constant"


def test_the_sink_is_never_empty_or_backspace_has_nothing_to_delete():
    """The bug this exists for: the sink shipped EMPTY, and an empty field with the
    caret at 0 has nothing to delete — so Backspace produced no `beforeinput`, no
    `input` and no request. Measured on iPadOS Safari, where `backspace` appeared
    **zero** times in the whole server log while the mode was in use.

    The `deleteContentBackward` branch was correct all along and simply never ran,
    which is why the suite was green while the key was dead. A test that only checks
    the branch exists cannot see that; this one checks the field it depends on.
    """
    html = _html()
    assert re.search(r"const KB_SENTINEL = '\w+';", html), \
        "the sink needs resting content, or a backspace deletes nothing and reports nothing"
    m = re.search(r"const KB_SENTINEL = '(\w+)';", html)
    assert len(m.group(1)) > 1, "one character empties on the first backspace and goes quiet again"

    arm = html.split("function _kbArmSink()")[1].split(chr(10) + "}")[0]
    assert "s.value = KB_SENTINEL" in arm, "arming must refill the buffer"
    assert "setSelectionRange" in arm, \
        "the caret must sit at the END — content before the caret is what Backspace deletes"

    kb = html.split("function bindKbSink()")[1].split(chr(10) + "}" + chr(10))[0]
    assert "sink.value = ''" not in kb, \
        "emptying the sink is the bug — that is what made Backspace unreportable"


def test_named_keys_arrive_only_as_keydown_and_are_all_mapped():
    """`beforeinput` has no `inputType` for Tab, an arrow, Delete or a Ctrl combo, so
    those can ONLY ever be seen as a keydown. Before the map existed the handler had
    a Backspace branch that was a comment and nothing else, and every one of these
    was silently dropped — an iPad with a hardware keyboard produces all of them.

    `preventDefault` is what stops a double send: it suppresses the input event, so
    the sentinel path cannot infer the same keystroke a second time.
    """
    html = _html()
    m = re.search(r"const KB_NAMED_KEYS = \{(.*?)\};", html, re.S)
    assert m, "the named-key map must exist"
    table = m.group(1)
    for key, sent in (("Backspace", "backspace"), ("Delete", "delete"), ("Tab", "tab"),
                      ("ArrowUp", "up"), ("ArrowDown", "down"), ("ArrowLeft", "left"),
                      ("ArrowRight", "right"), ("Home", "home"), ("End", "end"),
                      ("PageUp", "pageup"), ("PageDown", "pagedown"), ("Enter", "enter")):
        assert re.search(rf"{key}: '{sent}'", table), f"{key} is not mapped to {sent}"

    kd = html.split("sink.addEventListener('keydown'")[1].split(chr(10) + "  });")[0]
    assert "KB_NAMED_KEYS[e.key]" in kd, "the map must actually be consulted"
    # Scoped to the BRANCH, not the handler: preventDefault appears in the Escape
    # and combo branches too, so "it is in here somewhere" is satisfied by a version
    # that dropped it from exactly the place it matters. A mutation proved that.
    named_branch = kd.split("if (named) {")[1].split("}")[0]
    assert "e.preventDefault()" in named_branch,         "a named key that is not prevented also fires input, and sends twice"
    assert named_branch.index("e.preventDefault()") < named_branch.index("_kbKey("),         "prevent first, then send" 

    # Shift is how capitals are typed. Treating it as a combo turns every capital
    # letter into a keystroke instead of a character.
    assert "onlyShift" in kd, "shift alone must not be treated as a modifier combo"


def test_a_deletion_is_never_counted_twice_and_never_floods():
    """Two engines, two paths: one reports `deleteContentBackward`, one only changes
    the field. Both must produce exactly ONE backspace, and a select-all-delete must
    not fire a burst at a remote terminal where every one of them is destructive.
    """
    html = _html()
    inp = html.split("sink.addEventListener('input'")[1].split(chr(10) + "  });")[0]
    assert "_kbHandled" in inp, \
        "without the flag, a reported deletion is sent again by the length diff"
    assert "Math.min(" in inp, "the inferred-deletion loop must be capped"

    before = html.split("sink.addEventListener('beforeinput'")[1].split(chr(10) + "  });")[0]
    for it in ("deleteContentBackward", "insertText", "insertLineBreak"):
        line = [l for l in before.splitlines() if it in l and "_kbKey" in l or (it in l and "_kbQueue" in l)]
        assert line and "_kbHandled = true" in line[0], \
            f"{it} must mark the keystroke handled, or the input listener repeats it"

    kd = html.split("sink.addEventListener('keydown'")[1].split(chr(10) + "  });")[0]
    assert "_kbHandled = false" in kd, \
        "a new keystroke must clear the flag, or one stuck flag swallows the NEXT deletion"


def test_the_keyboard_is_measured_and_dismissed_by_the_only_things_that_work():
    """Two device facts, each of which makes the mode feel broken if ignored.

    The keyboard covers the bottom of the screen — which is where the operator just
    tapped, because that is where the caret went. There is no keyboard event to
    listen for: the keyboard opening IS a `visualViewport` resize. Telegram's own
    `viewportHeight` is NOT a substitute — a Telegram-iOS issue reports it not
    reflecting the keyboard at all, so a client trusting it scrolls the picture for
    no reason or not at all.

    And `blur()` alone leaves the keyboard up on some Android builds, so a mode
    switched OFF would still be covering the screenshot — the same class of lie as
    a toggle whose label disagrees with its state.
    """
    html = _html()
    block = html.split("function _kbKeepVisible()")[1].split("function _kbRefocus")[0]
    assert "visualViewport" in block, "the keyboard is detected by viewport resize, nothing else"
    assert "viewportHeight" not in block, \
        "Telegram's viewportHeight does not reflect the keyboard on iOS — do not measure with it"

    hide = html.split("function _kbHideKeyboard()")[1].split(chr(10) + "}")[0]
    assert "blur()" in hide and "hideKeyboard" in hide, \
        "exiting must both blur and ask Telegram to drop the keyboard"

    # The aim is a FRACTION of the image, not pixels: the frame is replaced every
    # refresh and re-laid-out, so a pixel remembered now points somewhere else next
    # frame.
    aim = html.split("function _kbAimAt(")[1].split(chr(10) + "}")[0]
    assert "fx" in aim and "fy" in aim, "the aimed point must be stored as fractions"
    keep = html.split("function _kbKeepVisible()")[1].split(chr(10) + "}")[0]
    assert "box.height * _kbAim.y" in keep, \
        "the remembered fraction must be re-multiplied by the CURRENT image box"


def test_client_and_server_agree_on_the_character_cap():
    """The client trims to a cap the server also enforces. If they drift, the phone
    sends a batch the server refuses and the operator sees typing stop with a 400
    naming a limit nothing on the phone knows about.
    """
    from config import TYPE_CHARS_MAX
    m = re.search(r"const TYPE_CHARS_MAX = (\d+);", _html())
    assert m, "the client must name its cap"
    assert int(m.group(1)) == TYPE_CHARS_MAX, \
        f"client cap {m.group(1)} != config.py TYPE_CHARS_MAX {TYPE_CHARS_MAX}"


def test_window_identity_is_strict_and_mirrors_the_client():
    """`same_window_id` guards `/api/chars`, and a guard that says yes too often is
    not a guard. Two traps, both met while writing it:

    - a single-segment title ('Claude Code') has NO tail key, and comparing bare
      tail keys makes two empties equal — which waved through every window against
      the one target row 17 exists for;
    - containment is right for "will focus find it?" and wrong for identity, since
      'Telegram' is inside 'Telegram Web - Google Chrome'.

    The client's `_sameWinId` is the same rule and the pair must not drift (`D-009`).
    """
    from utils.window import same_window_id

    same = [
        ("Claude Code", "Claude Code"),
        ("CLAUDE CODE", "claude code"),
        ("  Claude Code  ", "Claude Code"),
        # VS Code puts the open file first: no shared prefix, same tail.
        ("config.py - Tg-IDE-bot - Visual Studio Code",
         "web.py - Tg-IDE-bot - Visual Studio Code"),
    ]
    for a, b in same:
        assert same_window_id(a, b), f"{a!r} and {b!r} are the same window"

    different = [
        ("Claude Code", "Some Other Window"),
        ("Claude Code", ""),
        ("", ""),
        (None, None),
        # Both have empty tail keys — the bug this test exists for.
        ("Notepad", "Calculator"),
        # Containment is not identity.
        ("Telegram", "Telegram Web - Google Chrome"),
        # Same last segment, different project: the tail is TWO segments.
        ("main.py - OtherProject - Visual Studio Code",
         "main.py - Tg-IDE-bot - Visual Studio Code"),
    ]
    for a, b in different:
        assert not same_window_id(a, b), f"{a!r} and {b!r} are NOT the same window"

    # The client's twin must still be the same rule, or the phone and the server
    # disagree about what window it is typing into.
    js = _html().split("function _sameWinId(")[1].split(chr(10) + "}")[0]
    assert "if (x === y) return true;" in js, "client identity dropped the exact match"
    assert "return !!k && k === _tailKey(b);" in js, \
        "client identity no longer requires a NON-EMPTY tail key"
    assert "includes(" not in js, "containment leaked into the client's identity rule"


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
    # The threshold is HOLD_SLOP_PX now, not TAP_MOVE_PX: two fingers landing together
    # drift more than 8px between them, so the tap threshold made a two-finger TAP as
    # unfireable as the hold was — measured, zero right clicks ever sent (`D-024`).
    assert "HOLD_SLOP_PX" in two, "pinch detection has no movement threshold"
    assert "TAP_MOVE_PX" not in two, "the pinch branch is back on the tap threshold"

    live_end = html.split("const gEnd = e =>")[1].split("img.onpointerup")[0]
    was_two = live_end.split("const wasTwo")[1].split(";")[0]
    assert "!g.slid" in was_two and "g.moved" not in was_two, \
        "the live view's two-finger tap is gated on the 8px tap threshold again"

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


def test_a_hold_is_not_cancelled_by_a_resting_finger():
    """Measured against the live phone, 2026-09-08: 31 clicks landed in one session
    and NOT ONE right click was ever sent — zero `button: right` requests reached the
    server. The gesture never got as far as a request.

    Cause: a hold was cancelled by the TAP threshold (8px from the landing point) and,
    in the viewer, by the 3px PAN threshold. A finger resting on glass for 350ms clears
    both every time, so the timer was cleared before it could ever fire. A hold needs
    its own, coarser slop — and it must be measured from where the finger LANDED, not
    per move event, or accumulated drift never registers at all."""
    html = _html()
    assert re.search(r"const HOLD_SLOP_PX = (\d+);", html), "the hold has no slop of its own"
    slop = int(re.search(r"const HOLD_SLOP_PX = (\d+);", html).group(1))
    tap = int(re.search(r"TAP_MOVE_PX = (\d+)", html).group(1))
    assert slop > tap, "a hold is cancelled as easily as a tap — the bug this fixes"

    live = html.split("function bindImgClick()")[1].split("let _imgSuppressClick")[0]
    assert "HOLD_SLOP_PX" in live, "the live view still cancels on the tap threshold"
    assert "g.moved" in live, "the two-finger tap lost its own threshold"
    # The name appearing SOMEWHERE is not the claim — three mutations survived an
    # earlier form of these assertions. Pin the two expressions that matter.
    timer = live.split("g.holdTimer = setTimeout")[1].split("DRAG_HOLD_MS")[0]
    code = chr(10).join(ln.split("//")[0] for ln in timer.splitlines())
    assert "g.slid" in code and "g.moved" not in code,         "the hold timer is gated on the tap flag, not the hold slop"
    assert "g.held = true" in timer
    # The click is SENT from the timer, not from the release. Waiting for pointerup
    # made the gesture depend on an event the webview may replace with pointercancel,
    # and on the finger not drifting in between — measured: 0 right clicks ever sent.
    assert "'right'" in timer, "the hold still waits for the release to send anything"
    assert "g.from" in timer, "the hold anchors somewhere other than where the finger landed"
    assert "setPointerCapture" in live, "a finger drifting off the image loses its release"
    # ...and the release that follows must be swallowed, or a right click also
    # sends a left one.
    assert "_imgSuppressClick = true" in timer, "the click after the hold is not suppressed"
    # Armed, the image is a control surface. With the default touch-action the webview
    # treats a resting finger as a possible page scroll and fires pointercancel
    # mid-hold — a right click that never happens, with nothing logged anywhere.
    assert "touchAction = clickMode ? 'none'" in live,         "the webview can still claim the gesture and cancel the pointer"

    lb = _lightbox_js(html)
    down = lb.split("addEventListener('pointerdown'")[1].split("addEventListener(")[0]
    arm = down.split("_lb.dragTimer = setTimeout")[1].split("DRAG_HOLD_MS")[0]
    # Comments stripped: the code here NAMES the flag it deliberately does not use,
    # and a rule that fires on its own explanation teaches people to delete it.
    arm = chr(10).join(ln.split("//")[0] for ln in arm.splitlines())
    assert "_lb.slid" in arm and "_lb.moved" not in arm,         "the viewer arms against the 3px pan threshold, which a resting finger clears"
    move = lb.split("addEventListener('pointermove'")[1].split("addEventListener(")[0]
    assert "_lb.down.get" in move and "HOLD_SLOP_PX" in move,         "the viewer measures drift per move event instead of from the landing point"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
