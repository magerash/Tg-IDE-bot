"""Smoke tests for the web dashboard: API endpoints + HTML/JS consistency.

Run: python -m pytest tests/ -q
Boots the aiohttp app in-process (no bot token, no network, no Telegram).
"""
import asyncio
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from config import WEB_TOKEN  # noqa: E402
from handlers.web import create_web_app  # noqa: E402
from utils import project  # noqa: E402

AUTH = {"Authorization": f"Bearer {WEB_TOKEN}"}
INDEX = os.path.join(ROOT, "web", "index.html")
COMMON = os.path.join(ROOT, "web", "common.js")
REFINE = os.path.join(ROOT, "web", "refine.html")


def _run(coro):
    return asyncio.run(coro)


async def _client():
    return TestClient(TestServer(create_web_app()))


# --- API smoke ---

def test_api_endpoints_respond():
    async def go():
        async with await _client() as c:
            for path in ["/api/status", "/api/folders", "/api/project", "/api/windows"]:
                r = await c.get(path, headers=AUTH)
                assert r.status == 200, path
                data = await r.json()
                assert data["ok"] is True, path
    _run(go())


def test_unauthorized_is_json_401():
    async def go():
        async with await _client() as c:
            r = await c.get("/api/status")
            assert r.status == 401
            data = await r.json()  # must be JSON, not HTML error page
            assert data["ok"] is False
    _run(go())


def test_project_switch_and_restore():
    async def go():
        original = project.get_dir()
        try:
            async with await _client() as c:
                r = await c.get("/api/folders", headers=AUTH)
                folders = (await r.json())["folders"]
                assert folders, "no project folders found"
                target = folders[0]
                r = await c.post("/api/project", headers=AUTH, json={"folder": target})
                data = await r.json()
                assert data["ok"] and data["current"] == target
                # unknown folder rejected
                r = await c.post("/api/project", headers=AUTH, json={"folder": "no_such_dir_x"})
                assert (await r.json())["ok"] is False
        finally:
            project.set_dir(original)
    _run(go())


def test_restart_requires_auth():
    """Restart endpoint exists and rejects unauthenticated calls.
    (Authorized restart is NOT tested — it would re-exec the test process.)"""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/restart")
            assert r.status == 401
            assert (await r.json())["ok"] is False
    _run(go())


def test_stt_requires_auth_and_key():
    """STT endpoint rejects unauthenticated; authorized without key → friendly error."""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/stt", data=b"xxx")
            assert r.status == 401
            r = await c.post("/api/stt", headers=AUTH, data=b"xxx",
                             skip_auto_headers=["Content-Type"])
            data = await r.json()
            from config import GROQ_API_KEY
            if not GROQ_API_KEY:
                assert data["ok"] is False and "GROQ_API_KEY" in data["error"]
            # humanize flag must not break the endpoint
            r = await c.post("/api/stt?humanize=1", headers=AUTH, data=b"xxx",
                             skip_auto_headers=["Content-Type"])
            assert r.status in (200, 400)
    _run(go())


def test_humanize_module():
    """humanize() passes empty text through and module imports clean."""
    from utils.humanize import humanize
    assert asyncio.run(humanize("  ")) == "  "


def test_improve_endpoint_auth_and_validation():
    """/api/improve rejects unauthenticated calls and empty text."""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/improve", json={"text": "x"})
            assert r.status == 401
            r = await c.post("/api/improve", headers=AUTH, json={"text": "  "})
            assert (await r.json())["ok"] is False
    _run(go())


def test_improve_styles_match_ui_and_twin_is_optional(tmp_path, monkeypatch):
    """Style keys must match the #imp-style dropdown (drift guard), the twin
    block must only appear when the profile exists, and a missing profile must
    be reported — not crash — so the toggle never looks silently dead."""
    from utils import improve as imp

    # server styles == UI options
    sel = re.search(r'<select id="imp-style".*?</select>', _html(), re.S).group(0)
    opts = set(re.findall(r'option value="(\w+)"', sel))
    assert opts == set(imp.STYLES), f"UI styles {opts} != server {set(imp.STYLES)}"

    # missing profile dir -> None, no raise
    monkeypatch.setattr(imp, "HAE_PROFILE_DIR", str(tmp_path / "nope"))
    imp._twin_cache.update(key=None, text=None)
    assert imp._twin_context() is None

    # present profile -> injected into system prompt only when twin=True
    prof = tmp_path / "profile"
    prof.mkdir()
    (prof / "persona.md").write_text("OPERATOR-PERSONA-MARK", encoding="utf-8")
    (prof / "principles.md").write_text("PRINCIPLES-MARK", encoding="utf-8")
    monkeypatch.setattr(imp, "HAE_PROFILE_DIR", str(prof))
    imp._twin_cache.update(key=None, text=None)

    seen = {}

    async def fake_chat(system, text):
        seen["system"] = system
        return "improved"

    monkeypatch.setattr(imp, "chat", fake_chat)
    out, used = asyncio.run(imp.improve("raw", "structured", twin=True))
    assert out == "improved" and used is True
    assert "OPERATOR-PERSONA-MARK" in seen["system"] and "PRINCIPLES-MARK" in seen["system"]

    out, used = asyncio.run(imp.improve("raw", "structured", twin=False))
    assert used is False and "OPERATOR-PERSONA-MARK" not in seen["system"]


def test_improve_never_auto_sends_and_saves_draft_first():
    """doImprove must push the original to History BEFORE the request and must
    not send the result — the user reads it and sends themselves."""
    html = _html()
    m = re.search(r"async function doImprove\(\).*?\n\}", html, re.S)
    assert m, "doImprove missing"
    body = m.group(0)
    hist = body.find("addHistory('draft'")
    call = body.find("api('POST', '/api/improve'")
    assert 0 <= hist < call, "original text must hit History before the LLM call"
    assert "doType(" not in body, "improve must never auto-send"
    assert re.search(r"/api/improve'[^;]*?,\s*\d{4,}\s*\)", body), "no explicit timeout"
    # history knows the new kind
    assert "draft: 'type-input'" in html and ".hist-kind.draft" in html


def test_scheduler_add_list_remove(tmp_path):
    """add_job/list_jobs/remove_job round-trip on an isolated store file."""
    from utils import scheduler
    scheduler.SCHEDULE_FILE = str(tmp_path / "sched.json")

    async def go():
        j = await scheduler.add_job("hello", 9999999999, True, "SomeWindow")
        jobs = await scheduler.list_jobs()
        assert any(x["id"] == j["id"] for x in jobs)
        assert await scheduler.remove_job(j["id"]) is True
        assert await scheduler.remove_job(j["id"]) is False  # already gone
    _run(go())


def test_schedule_endpoints():
    """List needs auth; create rejects a past time (no window/file side effects)."""
    async def go():
        async with await _client() as c:
            assert (await c.get("/api/schedules")).status == 401
            r = await c.get("/api/schedules", headers=AUTH)
            assert r.status == 200 and (await r.json())["ok"] is True
            r = await c.post("/api/schedule", headers=AUTH, json={"text": "x", "when": 1})
            data = await r.json()
            assert data["ok"] is False and "past" in data["error"].lower()
            r = await c.post("/api/schedule", headers=AUTH, json={"text": "x"})
            assert (await r.json())["ok"] is False  # missing 'when'
    _run(go())


def test_ccmetrics_endpoint_and_collect():
    """ccmetrics.collect never raises (missing files → {}); endpoint needs auth."""
    from utils import ccmetrics
    m = ccmetrics.collect()
    assert isinstance(m, dict)

    async def go():
        async with await _client() as c:
            r = await c.get("/api/ccmetrics")
            assert r.status == 401  # auth required
            r = await c.get("/api/ccmetrics", headers=AUTH)
            assert r.status == 200
            data = await r.json()
            assert data["ok"] is True and isinstance(data["metrics"], dict)
    _run(go())


def test_index_served():
    async def go():
        async with await _client() as c:
            r = await c.get("/")
            assert r.status == 200
            body = await r.text()
            assert "<!DOCTYPE html>" in body
            assert len(body) > 5000
    _run(go())


def test_api_frame_binary_webp_and_304_style_204():
    """The live-view transport: raw bytes (no base64), WebP on request, and a
    bodyless 204 when the frame is unchanged."""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/frame", headers=AUTH,
                             json={"mode": "screen", "fmt": "webp", "max_w": 640})
            assert r.status == 200
            assert r.headers["Content-Type"] == "image/webp"
            body = await r.read()
            assert body[:4] == b"RIFF" and body[8:12] == b"WEBP"   # real WebP, not JSON
            digest = r.headers["X-Hash"]
            assert len(r.headers["X-Rect"].split(",")) == 4

            # Same hash back → 204, no body, headers still carry rect/hash
            r2 = await c.post("/api/frame", headers=AUTH,
                              json={"mode": "screen", "fmt": "webp", "max_w": 640,
                                    "hash": digest})
            if r2.status == 204:            # screen may legitimately have changed
                assert await r2.read() == b""
                assert r2.headers["X-Hash"] == digest

            # JPEG path still available for clients without WebP
            r3 = await c.post("/api/frame", headers=AUTH,
                              json={"mode": "screen", "fmt": "jpeg", "max_w": 640})
            assert r3.headers["Content-Type"] == "image/jpeg"
            assert (await r3.read())[:2] == b"\xff\xd8"
    _run(go())


def test_focus_reports_gone_for_missing_window():
    """The client drops a recents chip only when the window is really gone —
    'found but activation blocked' must NOT set the flag."""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/focus", headers=AUTH,
                             json={"title": "no such window exists 12345"})
            data = await r.json()
            assert data["ok"] is False
            assert data["gone"] is True, data
    _run(go())


def test_recent_validation_mirrors_server_matching():
    """_matchesLive() in the dashboard must mirror focus_window_exact(): exact →
    containment either way → first-25-chars prefix. If one side gains a rule and
    the other doesn't, chips get hidden that would have focused fine."""
    html = _html()
    with open(os.path.join(ROOT, "utils", "window.py"), encoding="utf-8") as f:
        py = f.read()
    assert "_matchesLive" in html, "client-side live-window matcher missing"
    for side, src in (("client", html), ("server", py)):
        assert "25" in src, f"{side} lost the 25-char prefix rule"
    assert "includes(t)" in html and "t.includes(l)" in html, "client lost containment matching"
    assert "in w.title.lower() or w.title.lower() in t" in py, "server lost containment matching"
    assert "_tailKey" in html, "client lost the tail-key rule"
    assert "tail_key" in py, "server lost the tail-key rule"


def test_tail_key_identifies_a_retitling_window():
    """VS Code puts the open file first, so two titles of the SAME window share no
    prefix and neither contains the other. Prefix/containment alone declared the
    chip dead: it vanished from the recents list and never lit up green. The tail
    (project + app) is what stays put."""
    from utils.window import tail_key

    a = "config.py - Tg-IDE-bot - Visual Studio Code"
    b = "index.html - Tg-IDE-bot - Visual Studio Code"
    assert tail_key(a) == tail_key(b) == "tg-ide-bot - visual studio code"
    # ...but it must not merge different projects, or chips focus the wrong window
    assert tail_key(a) != tail_key("main.py - OtherProj - Visual Studio Code")
    assert tail_key("Explorer") == "", "single-segment titles must never match by tail"


def test_current_window_chip_is_pinned_and_highlighted():
    """Reported: the focused window is missing from the quick-pick chips and isn't
    highlighted when selected. Three causes, all guarded here."""
    html = _html()
    # 1. current window is prepended to the list, so it survives the top-6 cut and
    #    shows even when it was focused outside the dashboard
    assert "[active, ...top.filter" in html, "current window no longer pinned first"
    # 2. highlight compares with the same fuzzy matcher, not ===
    assert "same(name, active) ? 'btn-ok-soft'" in html, "highlight back to exact-title compare"
    # 3. ties break by recency, or a fresh entry (n=1) loses to eight older n=1s
    assert "_recentOrder" in html and "b[1].t" in html, "recents ordering lost its recency tiebreak"
    assert "_sameWinId(k, name)" in html, "bumpRecent no longer merges retitled entries"
    # identity is stricter than focus matching — containment must not merge chips
    assert "_sameWinId" in html and "_tailKey(a)" in html, "strict identity matcher gone"


def test_lightbox_survives_pan_gestures():
    """The viewer closed itself while the user panned a zoomed screenshot.

    Two causes, both guarded here:
    1. Telegram closes the Mini App on a vertical drag — panning IS that gesture,
       so disableVerticalSwipes() must be called at startup.
    2. setPointerCapture retargets every pointerup to #lightbox, so pointerup's
       own target can't tell a backdrop tap from a tap on the image. The
       backdrop-close decision must come from pointerdown (_lb.onBackdrop)."""
    html = _html()
    assert "disableVerticalSwipes" in html, "TG vertical-swipe close not disabled"
    assert "_lb.onBackdrop" in html, "backdrop-close no longer decided at pointerdown"
    up = html.split("addEventListener('pointerup'")[1].split("addEventListener(")[0]
    assert "e.target.id === 'lightbox'" not in up, \
        "pointerup reads a pointer-capture-retargeted target again"
    assert "_lb.moved || _lb.multi" in html, "pinch tail can still close the viewer"
    assert "addEventListener('pointercancel'" in html, "stolen gesture leaves a stale pointer"


def test_frame_swap_waits_for_decode():
    """A white flash appeared on every screen refresh.

    img 'load' fires when the bytes are in, not when the bitmap is decoded.
    capture() replaced #screen-area's child with that still-undecoded <img>, so
    the browser painted one frame with the old image gone and the new one not
    ready — the panel background showed through. The swap must happen after
    decode(), and that background must be a theme var, not a hardcoded white."""
    html = _html()
    body = html.split("im.onload = async")[1].split("im.onerror")[0]
    assert "await im.decode()" in body, "frame swapped in before the bitmap is decodable"
    assert body.index("await im.decode()") < body.index("area.replaceChildren(im)"),         "decode must be awaited BEFORE the swap, or the flash is back"
    assert "im.onload = async ()" in html, "onload handler cannot await decode"
    css = html.split("#screen-area{")[1].split("}")[0]
    assert "background:var(" in css, "screen area paints a hardcoded color behind the frame"


def test_scroll_requires_auth_and_clamps():
    """/api/scroll drives a real mouse wheel — it must never answer unauthenticated,
    and a stuck 'hold' must not be able to fling a page by 10000 notches."""
    async def go():
        async with await _client() as c:
            r = await c.post("/api/scroll", json={"dir": "down"})
            assert r.status == 401
    _run(go())

    from utils.mouse import MAX_NOTCHES, WHEEL_DELTA
    assert WHEEL_DELTA == 120, "Windows counts raw wheel units; a notch is 120"
    assert 0 < MAX_NOTCHES <= 50


def test_scroll_moves_the_cursor_before_the_wheel(monkeypatch):
    """Two Windows facts this would silently violate: mouse_event ignores the x/y
    handed to a WHEEL event (so the cursor must really be moved first), and
    pyautogui counts raw units, so notches have to be multiplied by WHEEL_DELTA —
    pyautogui.scroll(3) is 3/120 of a notch and moves nothing."""
    import pyautogui

    from utils import mouse

    calls = []
    monkeypatch.setattr(pyautogui, "position", lambda: (7, 9))
    monkeypatch.setattr(pyautogui, "moveTo", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(pyautogui, "scroll", lambda n: calls.append(("scroll", n)))
    monkeypatch.setattr(mouse, "get_active_window_rect", lambda: (100, 200, 400, 600))

    res = mouse.scroll_at(-3)
    assert calls[0] == ("move", 300, 500), "cursor not parked over the target first"
    assert calls[1] == ("scroll", -3 * mouse.WHEEL_DELTA), "notches not converted to wheel units"
    assert calls[-1] == ("move", 7, 9), "cursor not restored to where the user left it"
    assert res["notches"] == -3 and res["at"] == [300, 500]

    calls.clear()
    mouse.scroll_at(999)                                  # clamp
    assert calls[1] == ("scroll", mouse.MAX_NOTCHES * mouse.WHEEL_DELTA)


def test_scroll_arrows_wired_in_ui():
    """Arrows sit ON the live view (right edge). They must live outside
    #screen-area — capture() replaces that element's children every frame.
    And they must be VISIBLE: rendering is not the same as being findable."""
    html = _html()
    assert 'class="screen-wrap"' in html, "scroll pad lost its stable container"
    assert html.count('data-scroll="up"') == 2, "expected arrows on the view and in the lightbox"
    assert "bindScrollPads()" in html
    assert "SCROLL_REPEAT_MS" in html and "setInterval" not in html.split("_scrollHold")[1][:400], \
        "hold-repeat must chain from completion, not fire on a fixed interval"
    # The bug that prompted this: the pad was rgba(20,19,17,.42) with no edge, and
    # :hover — the only rule that raised the contrast — never fires on a phone. Over
    # a dark editor screenshot the operator saw "nothing at all" and lost remote
    # scrolling entirely. The ring is what carries a dark pill on a dark backdrop.
    pad = re.search(r"\.scroll-pad button\{([^}]*)\}", html).group(1)
    assert "border:1px" in pad and "box-shadow" in pad, \
        "a translucent pill with no edge is invisible over a dark editor"
    # The FIRST max-width:560px block on the page is the one-liner .cc-meters rule;
    # matching that one swallows the rest of the stylesheet. The real phone block is
    # the one with a newline straight after the brace.
    phone = re.search(r"@media\(max-width:560px\)\{\n.*?\n\}", html, re.S).group(0)
    assert re.search(r"\.scroll-pad button\{[^}]*width:44px", phone), \
        "hold-to-repeat targets must be 44px on touch, not the 40px a mouse gets"
    # In night theme --accent is #ece9e4 while color stays #fff, so the held state of
    # a hold-to-scroll was white on white — no feedback at all.
    act = re.search(r"\.scroll-pad button:active[^{]*\{([^}]*)\}", html).group(1)
    assert "var(--accent)" not in act, "held state is invisible in night theme"


def test_enter_waits_for_the_paste_to_land(monkeypatch):
    """Claude Code buffers a bracketed paste; an Enter arriving inside that window
    becomes a literal newline instead of submit, so the message is stranded in the
    input box while every caller still answers "Typed: ...". Enter must therefore
    come after a real wait, and every typing path must go through one sequencer."""
    import pyautogui

    from config import TYPE_ENTER_DELAY
    from handlers import input as tg_input

    assert TYPE_ENTER_DELAY >= 0.3, "too short and Enter races the paste again"

    events = []
    monkeypatch.setattr(tg_input, "_set_clipboard", lambda t: events.append(("clip", t)))
    monkeypatch.setattr(tg_input, "_stuck_modifiers", lambda: [])
    # press_keys, not pyautogui: keys go out as virtual-key codes now, because
    # pyautogui resolves a character through the ACTIVE keyboard layout and drops
    # every latin key under Russian (see test_keys_do_not_depend_on_the_layout).
    monkeypatch.setattr(tg_input, "press_keys",
                        lambda *k: events.append(("hotkey", "+".join(k)) if len(k) > 1
                                                 else ("press", k[0])))
    monkeypatch.setattr(tg_input.time, "sleep", lambda s: events.append(("sleep", s)))
    monkeypatch.setattr(tg_input, "get_active_window_title", lambda: "win", raising=False)
    # ...and the process too, or the paste key is chosen from whatever real window
    # happens to be foreground on the machine running the tests.
    monkeypatch.setattr(tg_input, "get_active_window_process", lambda: "", raising=False)

    tg_input.type_and_enter("hello")
    assert ("hotkey", "ctrl+v") in events
    paste = events.index(("hotkey", "ctrl+v"))
    enter = events.index(("press", "enter"))
    waited = sum(s for kind, s in events[paste:enter] if kind == "sleep")
    assert waited >= TYPE_ENTER_DELAY, f"only {waited}s between paste and Enter"

    events.clear()
    tg_input.type_and_enter("hello", False)
    assert ("press", "enter") not in events, "enter=False must not submit"


def test_humanize_survives_a_retired_model():
    """Groq retired `llama-3.3-70b-versatile` mid-day and the whole Llama family
    vanished from the key: every voice message quietly returned the raw transcript
    and the AI toggle looked dead. A fallback chain plus a loud failure is the fix."""
    import pathlib

    from config import HUMANIZE_FALLBACKS, HUMANIZE_MODEL
    from utils.humanize import _strip_reasoning

    assert "llama-3.3-70b" not in HUMANIZE_MODEL, "primary model is the retired one"
    assert HUMANIZE_FALLBACKS, "no fallback: one retirement kills the feature again"
    assert HUMANIZE_MODEL not in HUMANIZE_FALLBACKS

    # Reasoning models dump their thinking into `content` — it would be pasted
    # into Claude Code verbatim (qwen3.6 returned 7196 chars for a 483-char input)
    assert _strip_reasoning("<think>plan</think>Чистый текст") == "Чистый текст"
    assert _strip_reasoning("Чистый текст\n<think>truncated") == "Чистый текст"

    src = pathlib.Path(ROOT, "utils", "humanize.py").read_text(encoding="utf-8")
    assert "raise RuntimeError(\"Humanize failed" in src, "failure must not be silent"


def test_stt_reports_a_failed_cleanup():
    """The endpoint must distinguish "cleaned" from "gave you the raw text",
    and the UI must show it — otherwise a broken model is invisible."""
    import pathlib

    api = pathlib.Path(ROOT, "handlers", "web_extra.py").read_text(encoding="utf-8")
    assert '"humanized"' in api and '"humanize_error"' in api

    html = _html()
    assert "humanize_error" in html and "AI cleanup failed" in html


def test_paste_hotkey_follows_the_target_window():
    """Claude Code owns Ctrl+V (its image-paste binding), so a text Ctrl+V into a
    terminal running it is a silent no-op: key delivered, clipboard correct, prompt
    empty. Terminal targets must get Ctrl+Shift+V; plain apps must NOT, since they
    have no such binding and would receive nothing at all."""
    from handlers.input import paste_hotkey_for

    for title in ("Findar - Visual Studio Code", "Tg-IDE-bot - Visual Studio Code",
                  "Windows PowerShell", "MINGW64:/c/Projects — git bash"):
        assert paste_hotkey_for(title) == ("ctrl", "shift", "v"), title

    for title in ("Untitled - Notepad", "Telegram", "", "Findar — Vivaldi"):
        assert paste_hotkey_for(title) == ("ctrl", "v"), title


def test_layout_is_visible_and_switchable(monkeypatch):
    """The layout of the TARGET window, shown and switchable from the phone.

    It is not cosmetic: what lands in a remote terminal is whatever that window's
    layout produces, and from a phone a Cyrillic command is invisible until the
    screenshot comes back with an error. The layout is per window, so both the
    read and the switch must target the foreground window, never the bot's own
    thread — ActivateKeyboardLayout would change nothing the operator can see.
    """
    import utils.layout as lay

    state = {"lang": 0x419}
    monkeypatch.setattr(lay, "list_layouts",
                        lambda: [{"lang": 0x419, "name": "RU", "hkl": 1},
                                 {"lang": 0x409, "name": "EN", "hkl": 2}])
    monkeypatch.setattr(lay, "current",
                        lambda: {"lang": state["lang"],
                                 "name": "RU" if state["lang"] == 0x419 else "EN",
                                 "window": "✳ Claude Code",
                                 "layouts": lay.list_layouts()})

    def _switch(lang=None):
        langs = [0x419, 0x409]
        state["lang"] = lang if lang else langs[(langs.index(state["lang"]) + 1) % 2]
        return True, "EN" if state["lang"] == 0x409 else "RU"

    monkeypatch.setattr(lay, "switch", _switch)

    async def go():
        async with await _client() as c:
            assert (await c.get("/api/layout")).status == 401, "layout leaks the window title"
            r = await (await c.get("/api/layout", headers=AUTH)).json()
            assert r["name"] == "RU" and r["window"] == "✳ Claude Code"
            # No lang = cycle, which is the one-tap case on a phone.
            r = await (await c.post("/api/layout", json={}, headers=AUTH)).json()
            assert r["ok"] and r["name"] == "EN"
            # The new state ships WITH the verdict: a second request to read it
            # back could already show a third value.
            r = await (await c.post("/api/layout", json={"lang": 0x419},
                                    headers=AUTH)).json()
            assert r["name"] == "RU"

    _run(go())

    # A real switch must be verified, not assumed — PostMessage cannot fail loudly
    # and a window that ignores it would leave the pill lying about what is active.
    import pathlib
    src = pathlib.Path(ROOT, "utils", "layout.py").read_text(encoding="utf-8")
    assert "WM_INPUTLANGCHANGEREQUEST" in src, "faking Alt+Shift depends on user settings"
    assert "GetForegroundWindow" in src, "layout must be read from the target window"
    assert "did not switch" in src, "an ignored request must be reported, not assumed"

    html = _html()
    assert "doLayout()" in html and 'id="lay-btn"' in html
    assert "loadLayout()" in html.split("visibilitychange")[1][:400],         "layout goes stale while the tab is hidden"
    assert "setInterval" not in html.split("async function loadLayout")[1][:600],         "no background poll — that traffic is what v0.16.3 was about"


def test_keys_do_not_depend_on_the_keyboard_layout():
    """Every keystroke must go out as a virtual-key code, never as a character.

    pyautogui maps a character to a key with VkKeyScanW, which asks the ACTIVE
    layout. Under Russian (0x419) VkKeyScanW('v') is -1 and pyautogui sends
    nothing at all: ctrl+shift+v delivers Ctrl and Shift with no V, so no paste
    ever happens; ctrl+shift+p never opens the command palette; and write() drops
    every latin letter. Measured 2026-08-31 against a live console — "echo
    TGBOT-MARKER-42" arrived as "--42": digits and '-' exist in the Russian
    layout, the letters do not. The bot went mute the moment the operator
    switched layout, on every surface at once, which is why it read as "the last
    change broke sending".
    """
    import pathlib
    from handlers.input import _VK, press_keys

    # The keys this bot actually sends must all be in the table — a miss silently
    # falls back to the layout-dependent path that caused the outage.
    for k in ("ctrl", "shift", "alt", "v", "p", "enter", "tab", "esc", "backspace",
              "up", "down", "left", "right", "1", "2", "3"):
        assert k in _VK, k
    assert _VK["v"] == 0x56 and _VK["p"] == 0x50, "VK codes are layout-invariant constants"

    sent = []
    import handlers.input as hin
    real = hin._u32.keybd_event
    try:
        hin._u32.keybd_event = lambda vk, sc, fl, ex: sent.append((vk, fl))
        assert press_keys("ctrl", "shift", "v") is True
    finally:
        hin._u32.keybd_event = real
    # down in order, up in reverse — a modifier released early turns the paste
    # into a bare V typed into whatever has focus.
    assert [vk for vk, fl in sent] == [0x11, 0x10, 0x56, 0x56, 0x10, 0x11], sent
    assert [fl & 0x2 for vk, fl in sent] == [0, 0, 0, 2, 2, 2], sent

    # No caller may go back to the character path.
    for mod in ("handlers/input.py", "handlers/web.py", "handlers/panel.py",
                "utils/vscode.py"):
        src = pathlib.Path(ROOT, mod).read_text(encoding="utf-8")
        body = chr(10).join(l for l in src.splitlines()
                         if not l.strip().startswith("#") and "fallback" not in l)
        assert "pyautogui.hotkey(" not in body or mod == "handlers/input.py", mod
        assert "pyautogui.press(" not in body or mod == "handlers/input.py", mod


def test_terminal_is_decided_by_process_not_title():
    """A terminal wears the name of whatever runs inside it.

    Claude Code retitles Windows Terminal to '✳ Claude Code', which matches no
    title hint, so the title-only rule sent Ctrl+V — the exact key Claude Code
    swallows as "paste image". Messages typed from the browser vanished with a
    cheerful "Typed:". The owning executable never changes, so it decides; the
    title stays a fallback for when the process cannot be read.
    """
    from handlers.input import paste_hotkey_for
    from utils.window import get_active_window_process

    # The window that broke it — no hint in the title, terminal by process.
    assert paste_hotkey_for("✳ Claude Code", "WindowsTerminal.exe") == ("ctrl", "shift", "v")
    assert paste_hotkey_for("claude", "pwsh.exe") == ("ctrl", "shift", "v")

    # A GUI app named like the CLI must NOT be treated as a terminal: Ctrl+Shift+V
    # means nothing to Claude Desktop and the paste would land nowhere.
    assert paste_hotkey_for("Claude", "claude.exe") == ("ctrl", "v")
    assert paste_hotkey_for("Untitled - Notepad", "notepad.exe") == ("ctrl", "v")

    # No process name available -> old title behaviour, unchanged.
    assert paste_hotkey_for("Tg-IDE-bot - Visual Studio Code", "") == ("ctrl", "shift", "v")
    assert paste_hotkey_for("Telegram", "") == ("ctrl", "v")

    # ...and the real key must actually be read from the live window, or the whole
    # table above is decoration.
    import pathlib
    src = pathlib.Path(ROOT, "handlers", "input.py").read_text(encoding="utf-8")
    assert "paste_hotkey_for(title, proc)" in src, "_type_text ignores the process"
    assert callable(get_active_window_process)


def test_every_typing_path_uses_the_sequencer():
    """A caller that pairs _type_text with its own pyautogui.press('enter') skips
    the wait and reintroduces the race — the reason this bug hit TG chat, the Mini
    App, panel presets and voice messages all at once."""
    import pathlib

    for name in ("handlers/web.py", "handlers/panel.py", "handlers/audio.py",
                 "utils/scheduler.py"):
        src = pathlib.Path(ROOT, name).read_text(encoding="utf-8")
        assert "_type_text" not in src or name == "handlers/web_extra.py", \
            f"{name} types without the sequencer"
        assert 'press("enter")' not in src and "press, \"enter\"" not in src, \
            f"{name} presses Enter itself instead of using type_and_enter()"


def test_api_frame_requires_auth():
    async def go():
        async with await _client() as c:
            r = await c.post("/api/frame", json={"mode": "screen"})
            assert r.status == 401
    _run(go())


def test_webp_smaller_than_jpeg():
    """The reason /api/frame exists — if this stops holding, drop the WebP path."""
    from handlers.screen import _grab_frame
    jpeg = _grab_frame(None, 1280, 70, "JPEG")
    webp = _grab_frame(None, 1280, 70, "WEBP")
    assert len(webp) < len(jpeg) * 0.85, f"webp {len(webp)} vs jpeg {len(jpeg)}"


def test_frame_opts_zero_max_w_means_native():
    """max_w=0 is the 'Full' setting, not a missing value — `or` defaulting here
    silently caps native captures back to WEB_SCREEN_MAX_W."""
    from config import WEB_SCREEN_MAX_W
    from handlers.web import _frame_opts

    class FakeReq:
        def __init__(self, data):
            self._data = data

        async def json(self):
            return self._data

    assert _run(_frame_opts(FakeReq({"max_w": 0})))[0] == 0
    assert _run(_frame_opts(FakeReq({})))[0] == WEB_SCREEN_MAX_W
    assert _run(_frame_opts(FakeReq({"max_w": 99999})))[0] == 3840
    assert _run(_frame_opts(FakeReq({"quality": 999})))[1] == 95


def test_miniapp_url_is_version_stamped():
    """Telegram caches the Mini App per URL — a version stamp forces a fresh load."""
    from handlers.web import miniapp_url
    assert miniapp_url("https://x.example/", "1.2.3") == "https://x.example/?v=1.2.3"
    assert miniapp_url("https://x.example/?a=1", "1.2.3") == "https://x.example/?a=1&v=1.2.3"


def test_client_version_matches_config():
    """Stale-UI detection compares these two — they must be bumped together."""
    from config import VERSION
    m = re.search(r"CLIENT_VERSION\s*=\s*'([\d.]+)'", _html())
    assert m, "CLIENT_VERSION missing from index.html"
    assert m.group(1) == VERSION, f"UI {m.group(1)} != config {VERSION}"


def test_api_calls_bound_long_jobs_explicitly():
    """Every api() call must either take the default deadline or pass its own —
    an unbounded fetch through the tunnel wedges the single-flight queue."""
    html = _html()
    for path in ["/api/sh", "/api/claude", "/api/build", "/api/key"]:
        for call in re.findall(r"api\('POST', '" + re.escape(path) + r"'[^;]*?\);", html):
            assert re.search(r",\s*(0|\d{4,})\s*\)", call), f"{path} call has no explicit timeout: {call}"


def test_frame_reply_same_hash_skips_image():
    """Unchanged frame must reply {'same': True} with no image — the whole point
    of the hash round trip is that an idle screen costs ~80 bytes, not ~80KB."""
    import io
    import json as _json
    from handlers.web import _frame_reply

    buf = io.BytesIO(b"fake-jpeg-bytes")
    first = _json.loads(_frame_reply(buf, [0, 0, 100, 100], "").body)
    assert first["ok"] and first["image"] and first["hash"]

    same = _json.loads(_frame_reply(buf, [0, 0, 100, 100], first["hash"]).body)
    assert same["same"] is True and "image" not in same
    assert same["rect"] == [0, 0, 100, 100]      # rect still refreshed

    stale = _json.loads(_frame_reply(buf, [0, 0, 100, 100], "deadbeef").body)
    assert "same" not in stale and stale["image"]


def test_grab_to_jpeg_downscales():
    """max_w must shrink the frame — short auto-refresh intervals depend on it."""
    from PIL import Image
    from handlers.screen import _grab_to_jpeg

    big = _grab_to_jpeg(None, 0, 70)
    small = _grab_to_jpeg(None, 640, 55)
    assert Image.open(small).width <= 640
    assert len(small.getvalue()) < len(big.getvalue())


# --- HTML/JS consistency (catches broken buttons without a browser) ---

def _html():
    """index.html + the shared script it loads — the page as the browser sees it.

    The regex invariants below must see both halves: once code moved into
    common.js, reading index.html alone would let them pass by looking at less,
    which is worse than failing (v0.19.0 extraction).
    """
    with open(INDEX, encoding="utf-8") as f, open(COMMON, encoding="utf-8") as g:
        return f.read() + "\n" + g.read()


def test_onclick_handlers_defined():
    """Every onclick="fn(...)" in HTML must have a function fn defined in the script."""
    html = _html()
    called = set(re.findall(r'onclick="(\w+)\(', html))
    defined = set(re.findall(r'(?:async\s+)?function\s+(\w+)\s*\(', html))
    missing = called - defined
    assert not missing, f"onclick references undefined functions: {missing}"


def test_js_element_ids_exist():
    """Every getElementById('x') in JS must have id="x" in the HTML."""
    html = _html()
    used = set(re.findall(r"getElementById\(['\"]([\w-]+)['\"]\)", html))
    declared = set(re.findall(r'id="([\w-]+)"', html))
    missing = used - declared
    assert not missing, f"JS uses missing element ids: {missing}"


def test_api_paths_in_js_are_registered():
    """Every '/api/...' string in the frontend must be a registered route."""
    html = _html()
    js_paths = set(re.findall(r"['\"](/api/[\w-]+)['\"]", html))
    app = create_web_app()
    routes = {r.resource.canonical for r in app.router.routes() if r.resource}
    missing = js_paths - routes
    assert not missing, f"frontend calls unregistered API paths: {missing}"


def test_mobile_order_and_accordion():
    """Mobile column must start Screen -> Windows -> Projects (windows used constantly,
    screen is what you look at), and Windows/Projects fold as accordions."""
    html = _html()
    # order in the <=920px media block: screen above windows above projects
    orders = dict(re.findall(r"#([\w-]+)\{order:(-\d+)\}", html))
    assert int(orders["screen-panel"]) < int(orders["win-panel"]) < int(orders["proj-panel"]), \
        f"mobile panel order broken: {orders}"
    # both context panels are accordions with a toggle on the title
    for pid in ("win-panel", "proj-panel"):
        assert re.search(rf'class="panel tight acc" id="{pid}"', html), f"{pid} lost .acc"
        assert f"togglePanel('{pid}')" in html, f"{pid} title toggle missing"
    # collapsed state hides the body and persists
    assert ".panel.acc.collapsed>:not(h3){display:none}" in html
    assert "localStorage.setItem('acc_' + id" in html
    # The bottom bar folds with the SAME idiom, not a second one invented for it:
    # same acc_ namespace, and a caret from a pseudo-element rather than markup.
    assert "localStorage.setItem('acc_quick-keys'" in html, "bar collapse invented its own key"
    assert "body.qk-hidden #quick-keys>:not(#qk-toggle){display:none}" in html
    assert "#qk-toggle::after{content:'▾'}" in html and \
           "body.qk-hidden #qk-toggle::after{content:'▴'}" in html, \
        "the caret must be a pseudo-element, like .panel.acc"


def test_quick_keys_bar_at_bottom():
    """Fixed bottom bar with the Claude-question keys (←/→/Enter/Sh+Tab/Tab plus
    the freeform field), a recently-tapped trail with an empty state, and body
    clearance so the bar never covers the last panel."""
    html = _html()
    # Anchor on the column-0 </div> that really closes the bar. The old
    # `</div>\s*</div>` pair stopped being the bar's own close once #qk-type moved
    # out of .qk-btns — it matched the bar's close plus #main's, so the test kept
    # passing while measuring a span seven characters too long.
    bar = re.search(r'<div id="quick-keys">.*?^</div>', html, re.S | re.M)
    assert bar, "quick-keys bar missing"
    bar = bar.group(0)
    # same key set must exist inside the lightbox viewer too (#lb-keys)
    lb = re.search(r'<div id="lb-keys">.*?</div>', html, re.S)
    assert lb, "lightbox quick-keys row missing"
    for where, chunk in (("bottom bar", bar), ("lightbox", lb.group(0))):
        for onclick in ("doKey('left')", "doKey('right')", "doKey('enter')",
                        "doKey('shift+tab')", "doKey('tab')"):
            assert onclick in chunk, f"{where} lacks {onclick}"
        # Tab must not be the same button as Sh+Tab, and must not have replaced it
        assert chunk.count("doKey('tab')") == 1 and "doKey('shift+tab')" in chunk
    # lightbox row must render above the z-200 overlay
    assert re.search(r"#lb-keys\{[^}]*z-index:201", html)
    # pinned to the viewport bottom, under lightbox/auth overlays
    assert re.search(r"#quick-keys\{position:fixed;left:0;right:0;bottom:0;z-index:90", html)
    # empty state + trail fed centrally from doKey (rail presses show up too)
    assert "no keys tapped yet" in bar
    m = re.search(r"async function doKey\(.*?\n\}", html, re.S)
    assert "_qkPush(" in m.group(0), "doKey must feed the trail"
    # body keeps clearance for the bar at every breakpoint
    assert "body{padding-bottom:62px}" in html
    assert "body{padding:10px 10px 62px}" in html
    # ...and the clearance FOLLOWS the bar when it folds, or a collapsed bar leaves a
    # dead band of padding nobody can see. Both 62px literals above stay byte-for-byte
    # (they are the expanded height); the collapsed value overrides by specificity.
    assert 'id="qk-toggle"' in bar, "the bottom bar has no way to hide itself"
    assert "body.qk-hidden{padding-bottom:26px}" in html
    assert "body.qk-hidden #toast{bottom:28px}" in html, "toast floats over a collapsed bar"
    # Collapsed is opt-in: the only route into it on load is an explicit stored '1'.
    # A bar hidden on first load is a bar nobody finds — the very bug this release fixes.
    assert "localStorage.getItem('acc_quick-keys') === '1'" in html


def test_tab_and_freeform_field_replace_the_digit_buttons():
    """Tab-then-Enter needs its own key: Sh+Tab cycles Claude Code's mode, Tab
    accepts/advances, and a bar that carries only Sh+Tab cannot do the workflow.
    The two fixed digit buttons are gone in favour of one field that types any
    answer + Enter — but the Keys rail keeps 1/2/3 for one-tap replies."""
    html = _html()
    assert "qkDigit(" not in html, "dead digit helper left behind"
    for fid in ("qk-type", "lb-type"):
        assert f'id="{fid}" class="qk-input"' in html, f"{fid} freeform field missing"
        assert f"bindSendKeys('{fid}', () => qkSend('{fid}'))" in html,             f"{fid} does not send on Enter"
    # Tab is untinted in both bars; Sh+Tab keeps its green — that is the whole
    # visual distinction between two keys one keystroke apart.
    assert re.search(r"""<button class="btn btn-sm" onclick="doKey\('tab'\)""", html)
    assert re.search(r"""<button class="btn btn-sm btn-ok-soft" onclick="doKey\('shift\+tab'\)""", html)
    assert re.search(r"""<button class="lb-ok" onclick="doKey\('shift\+tab'\)""", html)
    assert re.search(r"""<button onclick="doKey\('tab'\)""", html)
    assert "#lb-keys button.lb-ok{" in html, "viewer has no green pill style"
    # rail keeps the numbered answers
    assert "doTypePreset('1')" in html and "doTypePreset('2')" in html


def test_claude_launcher_is_orange_in_both_surfaces():
    """One orange button starts a session; it sits in Actions and in the viewer,
    and it must not read as another git/build action, hence the brand colour."""
    html = _html()
    assert "['Claude','btn-claude',()=>doClaudeCode()]" in html, "Actions lost the launcher"
    assert 'id="lb-claude" onclick="doClaudeCode()"' in html, "viewer lost the launcher"
    # brand orange defined in BOTH palettes, and the class actually uses it
    assert re.search(r"^:root\{.*?--claude:#d97757", html, re.S | re.M)
    assert re.search(r'^:root\[data-theme="dark"\]\{.*?--claude:', html, re.S | re.M)
    assert ".btn-claude{background:var(--claude)" in html
    assert "#lb-claude,#lb-proj-row button.lb-claude{background:var(--claude)}" in html
    # and it asks for the terminal focus, or it would type into the editor
    fn = html.split("async function doClaudeCode()")[1].split("\nasync function")[0]
    assert "terminal: true" in fn and "text: 'claude'" in fn
    # A reused terminal may already run Claude Code, where `claude` is just a chat
    # message to that session — the launcher must always get a fresh shell.
    assert "new_terminal: true" in fn
    assert "r.terminal" in fn and "toast(" in fn, "a missed terminal focus must be loud"


def test_lightbox_project_row_opens_and_focuses():
    """Pick a project, focus or open its VS Code window, start Claude — without
    leaving the zoomed screenshot, and without typing anything."""
    html = _html()
    row = re.search(r'<div id="lb-proj-row">.*?</div>', html, re.S)
    assert row, "viewer project row missing"
    row = row.group(0)
    assert 'id="lb-proj"' in row
    # the left zone picks a WINDOW first (focus) and a PROJECT second (open/claude)
    assert 'id="lb-win"' in row and "doFocusWin('lb-win')" in row
    assert "_fillSelect('lb-win'" in html, "viewer window select is never filled"
    assert "doCodeSel('lb-proj')" in row
    assert "_fillSelect('lb-proj'" in html, "viewer select is never filled"
    # focus targets the VS Code window of that project (containment match server-side)
    assert "_focusTitle(folder + ' - Visual Studio Code')" in html
    # form controls in the overlay must be exempt from pan/pinch/backdrop-close
    assert "const _lbCtl = el => ['BUTTON', 'INPUT', 'SELECT', 'OPTION']" in html
    assert "e.target.tagName === 'BUTTON'" not in html, "gesture guard still button-only"


def test_auto_loop_survives_a_failed_frame():
    """The Auto chain is self-scheduling: one exception out of requestCapture used
    to end it for good — the button stayed green and nothing refreshed again, which
    is what 'Auto sometimes stops working' was. Rescheduling must be in a finally."""
    html = _html()
    body = html.split("function _autoSchedule()", 1)[1].split("document.addEventListener", 1)[0]
    assert "finally { _autoSchedule(); }" in body, "a failed frame still kills the Auto chain"
    # a skipped tick must say why; a silent stop reads as a broken Auto
    assert "Auto paused" in body, "hidden-tab skip is silent"


def test_explicit_resolution_is_not_overridden_by_the_viewer():
    """Only 'Fit' is promoted to 1920 inside the lightbox (a panel-sized thumbnail
    is useless to zoom into). An explicit 1280/1920/Full is an instruction — silently
    raising it is why the resolution selector looked dead with the viewer open."""
    html = _html()
    fn = html.split("function _frameOpts()", 1)[1].split("function resChanged()", 1)[0]
    assert "w = lbOpen ? 1920" in fn, "'Fit' no longer gets a sharp frame in the viewer"
    assert "w < 1920" not in fn, "an explicit resolution choice is still overridden"


def test_window_selects_keep_the_operators_pick():
    """loadWindows() re-runs after every focus. Without `sticky` the refill re-selected
    the ACTIVE window, so the pick vanished under the finger and the next Focus tap
    re-focused the window already in front — a button that looks dead."""
    html = _html()
    assert "function _fillSelect(selId, items, placeholder, selected, sticky)" in html
    assert "if (sticky && keep && items.includes(keep)) selected = keep;" in html
    for sel in ("win-select", "lb-win"):
        assert re.search(r"_fillSelect\('%s'[^)]*, true\)" % sel, html), f"{sel} is not sticky"
    # ...and projects must NOT be sticky: there the server's current project is state
    assert re.search(r"_fillSelect\('proj-select', r\.folders, '[^']*', r\.current\)", html)
    # the viewer refreshes the list on open — windows change constantly
    open_fn = html.split("function openLightbox(", 1)[1].split("function closeLightbox", 1)[0]
    assert "loadWindows();" in open_fn, "viewer opens against a stale window list"


def test_escape_closes_the_viewer():
    """Esc is the first key anyone tries. Unhandled it goes to the browser/webview
    (leaving fullscreen, closing a picker) while the overlay just sits there."""
    html = _html()
    h = html.split("document.addEventListener('keydown'", 1)[1].split("});", 1)[0]
    assert "'Escape'" in h
    assert "style.display !== 'block'" in h, "Esc is not scoped to an open viewer"
    assert "e.preventDefault()" in h, "Esc still reaches the browser"
    assert "closeLightbox()" in h


def test_zoom_pad_mirrors_the_scroll_pad():
    """Zoom column on the LEFT edge of the viewer, same pills as the scroll column
    on the right. Local transform only — no server round trip — and the hold timer
    must die with the viewer, or a back-button close leaves it zooming a hidden img."""
    html = _html()
    pad = re.search(r'<div class="scroll-pad" id="lb-zoom">(.*?)</div>', html, re.S)
    assert pad, "no zoom pad in the viewer"
    assert 'data-zoom="in"' in pad.group(1) and 'data-zoom="out"' in pad.group(1)
    # inside #lightbox, or it shows while the viewer is closed
    lb = html.split('<div id="lightbox">', 1)[1].split('<img id="lb-img"', 1)[0]
    assert 'id="lb-zoom"' in lb
    # opposite edge from #lb-scroll, same pill styling (.scroll-pad class)
    assert re.search(r"#lb-zoom\{[^}]*left:14px", html), "zoom pad is not on the left edge"
    assert re.search(r"#lb-scroll\{[^}]*right:14px", html), "scroll pad moved off the right edge"
    # zoom is client-side: it must not call the scroll/click endpoints
    js = html.split("const ZOOM_STEP", 1)[1].split("bindZoomPad();", 1)[0]
    assert "_lbZoomAt" in js and "/api/" not in js, "zoom pad talks to the server"
    # pan handler must never see the press, or a zoom hold drags the picture
    assert "e.preventDefault(); e.stopPropagation();" in js
    assert "clearInterval(_zoomHeld)" in html.split("function closeLightbox()", 1)[1][:400],         "hold timer survives a close"


def test_viewer_controls_sit_in_three_zones():
    """Zoomed viewer bottom bar is three zones — project flow left, keys centred,
    view controls (layout / auto) right — and Close is the ONLY
    thing left pinned to the top-right corner, so it never moves as rows reflow."""
    html = _html()
    ctl = re.search(r'<div id="lb-controls">(.*?)</div>', html, re.S).group(1)
    assert "lb-close" in ctl
    for stray in ("lb-lay", "lb-auto", "lb-int", "lb-click"):
        assert stray not in ctl, f"{stray} still shares the corner with Close"
    view = re.search(r'<div id="lb-view-row">(.*?)</div>', html, re.S).group(1)
    for moved in ("lb-lay", "lb-auto"):
        assert moved in view, f"{moved} lost its home"
    # Click arms taps on the picture and is reached mid-gesture, so it leads the
    # CENTRE key row (immediately left of the arrows), not the view pills.
    keys = re.search(r'<div id="lb-keys">(.*?)</div>', html, re.S).group(1)
    assert "lb-click" in keys and "lb-click" not in view
    assert keys.index("lb-click") < keys.index("doKey('left')"), "Click is not left of the arrows"
    # the seconds pill rides with the left zone's flow instead
    proj = re.search(r'<div id="lb-proj-row">(.*?)</div>', html, re.S).group(1)
    assert "lb-int" in proj and "lb-int" not in view
    # ...and it must stay VISIBLE there: #lightbox is overflow:hidden, so a nowrap
    # left zone (2 selects + 4 pills) pushes Click off-screen on a phone
    css = html.split("@media(max-width:620px),(max-height:520px){", 1)[1].split(chr(10) + "}", 1)[0]
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    for zone in ("#lb-proj-row", "#lb-keys"):
        assert any(zone in sel.split("/*")[-1] and "flex-wrap:wrap" in b for sel, b in rules),             f"compact {zone} still nowrap — its last pill is clipped, not wrapped"
    # the three zones live in the bottom bar in left -> centre -> right order
    bottom = html.split('<div id="lb-bottom">', 1)[1].split('<img id="lb-img"', 1)[0]
    pos = [bottom.find('id="%s"' % i) for i in ("lb-proj-row", "lb-keys", "lb-view-row")]
    assert all(p >= 0 for p in pos), pos
    assert pos == sorted(pos), "zones are not in left -> centre -> right DOM order"
    assert re.search(r"#lb-bottom\{[^}]*justify-content:space-between", html)
    for sel, just in (("#lb-proj-row", "flex-start"),
                      ("#lb-keys", "center"),
                      ("#lb-view-row", "flex-end")):
        body = re.search(re.escape(sel) + r"\{([^}]*)\}", html).group(1)
        assert f"justify-content:{just}" in body, sel
    # the moved buttons must still be styled — they used to inherit from #lb-controls
    assert "#lb-view-row button{" in html or "#lb-view-row button," in html


def test_viewer_controls_stay_compact_on_a_phone():
    """The viewer rows float over the picture. At the desktop 38px/8px sizing they
    wrapped into four rows on a phone and covered half the screenshot, so the small
    screen gets 32px pills, one row per group, and shrinkable select/field."""
    html = _html()
    head = "@media(max-width:620px),(max-height:520px){"
    assert head in html, "no compact rule for the zoomed viewer"
    css = html.split(head, 1)[1].split("\n}", 1)[0]
    assert "height:32px" in css, "controls still desktop-height inside the viewer"
    assert "flex-wrap:nowrap" in css, "rows may still wrap into a wall of buttons"
    # a flex item without min-width:0 refuses to shrink and overflows the viewport
    for sel in ("#lb-proj-row select", "#lb-keys .qk-input"):
        # the selector appears twice (shared sizing + the shrink rule) — one of the
        # bodies must carry both, or that control refuses to give up width.
        # The basis differs (the two selects share a row, the field takes what is
        # left), so only "grows and shrinks" is pinned, not the number.
        bodies = re.findall(re.escape(sel) + r"\{([^}]*)\}", css)
        assert any("min-width:0" in b and "flex:1 1 " in b for b in bodies), sel
    assert "#lb-proj-row .lb-lbl{display:none}" in css, "Focus keeps its label on a phone"
    # ...which only saves width if the label is really wrapped in the markup
    assert '<span class="lb-lbl"> Focus</span>' in html


def test_type_focuses_the_terminal_before_typing(monkeypatch):
    """`terminal: true` must move the caret into the VS Code integrated terminal
    BEFORE the paste. Order is the whole point: focus after typing is no focus at
    all, and a fresh `code -n` leaves the caret in the editor, where ctrl+shift+v
    is an editor binding and the text disappears while the bot answers 'Typed:'."""
    import handlers.input as hin
    import utils.vscode as vsc

    calls = []
    def _fake_type(t, e=True):
        calls.append(("type", t, e))
        return ("✳ Claude Code", "windowsterminal.exe")   # real target, echoed back

    monkeypatch.setattr(hin, "type_and_enter", _fake_type)
    monkeypatch.setattr(vsc, "focus_vscode_terminal", lambda: calls.append(("focus",)))

    async def go(active, terminal):
        calls.clear()
        monkeypatch.setattr(vsc, "get_active_window_title", lambda: active)
        async with await _client() as c:
            r = await c.post("/api/type", json={"text": "claude", "terminal": terminal},
                             headers=AUTH)
            assert r.status == 200
            return await r.json()

    data = _run(go("Tg-IDE-bot - Visual Studio Code", True))
    assert calls == [("focus",), ("type", "claude", True)], calls
    assert data["terminal"] is True

    # Not VS Code: still types (the user may be aiming at a plain terminal), but
    # says so instead of pretending the text reached Claude Code.
    data = _run(go("Untitled - Notepad", True))
    assert calls == [("type", "claude", True)], calls
    assert data["terminal"] is False and "not VS Code" in data["terminal_msg"]

    # Default path is unchanged — no flag, no palette detour.
    data = _run(go("Tg-IDE-bot - Visual Studio Code", False))
    assert calls == [("type", "claude", True)] and "terminal" not in data

    # The window that really got the text is always reported. Nothing in this path
    # picks a target — the foreground window does — so a message swallowed by an
    # app that grabbed focus must be tellable from one that arrived.
    assert data["window"] == "✳ Claude Code" and data["proc"] == "windowsterminal.exe"


def test_vscode_editor_never_eats_the_message(monkeypatch):
    """Raising a VS Code window is not delivery.

    Measured 2026-08-31: two browser messages logged as `Typing 17 chars into
    'Tg-IDE-bot - Visual Studio Code' [code.exe] via ctrl+shift+v`, 200 OK, and
    neither arrived — the caret was in the editor, where ctrl+shift+v is
    `markdown.showPreview`, not paste. So the terminal hop is ON unless a caller
    explicitly opts out, and the dashboard asks for it whenever it aims at VS Code.
    """
    import handlers.input as hin
    import utils.vscode as vsc

    calls = []
    monkeypatch.setattr(hin, "type_and_enter",
                        lambda t, e=True: (calls.append(("type", t)), ("w", "p"))[1])
    monkeypatch.setattr(vsc, "focus_vscode_terminal", lambda: calls.append(("focus",)))

    async def go(payload, active="Tg-IDE-bot - Visual Studio Code"):
        calls.clear()
        monkeypatch.setattr(vsc, "get_active_window_title", lambda: active)
        async with await _client() as c:
            r = await c.post("/api/type", json=payload, headers=AUTH)
            assert r.status == 200
            return await r.json()

    # No flag at all — the old default typed blind into the editor. Now it does not.
    data = _run(go({"text": "hi"}))
    assert calls == [("focus",), ("type", "hi")], calls
    assert data["terminal"] is True

    # Not VS Code: no palette detour, nothing changes for a plain terminal or app.
    _run(go({"text": "hi"}, active="✳ Claude Code"))
    assert calls == [("type", "hi")], calls

    # An explicit false is still honoured — /api/paste-style callers opt out.
    data = _run(go({"text": "hi", "terminal": False}))
    assert calls == [("type", "hi")] and "terminal" not in data

    # ...and the dashboard has to ASK for it when it aims at a VS Code window,
    # or Target would raise the right window and still feed the editor.
    html = _html()
    body = html.split("async function doType()")[1].split("function _toLocalInput")[0]
    assert "/visual studio code/i.test(want)" in body, "target ignores the editor trap"
    assert "terminal: wantTerm" in body, "terminal hop never reaches the request"


def test_type_raises_the_target_window_first(monkeypatch):
    """`window` must be raised BEFORE the paste, in this one request.

    Nothing else in the type path picks a target: the foreground window gets the
    text. Measured 2026-08-31 on the live box — focus_window_exact('✳ Claude
    Code') returned ok=True and 700ms later the foreground was 'Claude' (Claude
    Desktop grabs it on its own). Focusing from a separate /api/focus call leaves
    exactly that gap, so the raise happens here, and a raise that did not stick is
    reported (`on_target: False`) instead of a cheerful "Typed:".
    """
    import handlers.input as hin
    import handlers.web as hw

    calls = []
    landed = {"title": "✳ Claude Code"}

    def _fake_type(t, e=True):
        calls.append(("type", t, e))
        return (landed["title"], "windowsterminal.exe")

    monkeypatch.setattr(hin, "type_and_enter", _fake_type)
    monkeypatch.setattr(hw, "TYPE_FOCUS_SETTLE", 0)   # no real sleep in a test

    async def go(payload, focus=(True, "Focused")):
        calls.clear()
        import utils.window as uw
        monkeypatch.setattr(uw, "focus_window_exact",
                            lambda t: (calls.append(("focus", t)), focus)[1])
        async with await _client() as c:
            r = await c.post("/api/type", json=payload, headers=AUTH)
            assert r.status == 200
            return await r.json()

    data = _run(go({"text": "hi", "window": "✳ Claude Code"}))
    assert calls == [("focus", "✳ Claude Code"), ("type", "hi", True)], calls
    assert data["on_target"] is True and data["focus"] is True

    # Raised, then something else took the foreground: the text went elsewhere and
    # the answer has to say so — this is the whole failure being fixed.
    landed["title"] = "Claude"
    data = _run(go({"text": "hi", "window": "✳ Claude Code"}))
    assert data["on_target"] is False and data["window"] == "Claude"

    # A window that no longer exists must not silently type into the wrong one.
    landed["title"] = "Claude"
    data = _run(go({"text": "hi", "window": "gone"}, focus=(False, "Window gone")))
    assert data["focus"] is False and data["on_target"] is False

    # No window asked for -> no focus call at all, old behaviour untouched.
    data = _run(go({"text": "hi"}))
    assert calls == [("type", "hi", True)] and "on_target" not in data


def test_terminal_focus_lives_in_one_place():
    """Scheduler and /api/type must share the palette sequence — a second copy
    drifts, and the drift is invisible until text lands in a source file."""
    import pathlib as _pl

    hits = [n for n in ("utils/scheduler.py", "handlers/web.py", "utils/vscode.py")
            if "Terminal: Focus on Terminal View" in _pl.Path(ROOT, n).read_text(encoding="utf-8")]
    assert hits == ["utils/vscode.py"], f"palette sequence duplicated in {hits}"
    src = _pl.Path(ROOT, "utils/scheduler.py").read_text(encoding="utf-8")
    assert "from utils.vscode import focus_vscode_terminal" in src


def test_singleton_guard_spawns_no_processes():
    """The guard must kill via in-process API calls (psutil), never taskkill or
    a powershell subprocess: when process creation hangs system-wide, subprocess
    kills time out on every restart and a zombie holds the web port through an
    endless crash loop (observed 2026-08-19, 40 min of Errno 10048)."""
    import pathlib
    src = pathlib.Path(ROOT, "utils", "singleton.py").read_text(encoding="utf-8")
    assert "import psutil" in src, "guard must use psutil API kills"
    assert "import subprocess" not in src and "subprocess.run" not in src, \
        "guard must not spawn child processes"
    assert ".wait(" in src, "must confirm death — port frees only when process is gone"
    import utils.singleton  # noqa: F401 — import must not raise


def test_favicon_assets_and_links():
    """All favicon assets exist, the ICO really carries 16+32, every <head> link
    resolves to a real file, and /favicon.ico is served without auth."""
    import pathlib
    from PIL import Image

    web_dir = pathlib.Path(ROOT, "web")
    ico = Image.open(web_dir / "favicon.ico")
    assert set(getattr(ico, "info", {}).get("sizes", {(16, 16), (32, 32)})) >= \
        {(16, 16), (32, 32)}
    assert Image.open(web_dir / "favicon-32x32.png").size == (32, 32)
    assert Image.open(web_dir / "favicon-16x16.png").size == (16, 16)
    assert Image.open(web_dir / "apple-touch-icon.png").size == (180, 180)
    assert "#229ED9" in (web_dir / "favicon.svg").read_text(encoding="utf-8")

    html = _html()
    hrefs = re.findall(r'<link rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', html)
    assert len(hrefs) == 4, f"expected 4 favicon links, got {hrefs}"
    for href in hrefs:
        name = href.rsplit("/", 1)[-1]
        assert (web_dir / name).is_file(), f"{href} points at a missing file"

    async def go():
        async with await _client() as c:
            r = await c.get("/favicon.ico")   # no auth headers on purpose
            assert r.status == 200
            body = await r.read()
            assert body[:4] == b"\x00\x00\x01\x00", "not an ICO payload"
    _run(go())


def test_md_preview_and_blocks_toggle():
    """Type field gets a rendered-markdown preview pane (Improve detailed returns
    markdown) and the auto block-chip paste behavior gets an off switch."""
    html = _html()
    # Blocks toggle gates the auto-block paste path — OFF must paste inline
    paste = re.search(r"getElementById\('type-input'\)\.addEventListener\('paste'.*?\n\}\);",
                      html, re.S)
    assert paste and "_blockPaste && text &&" in paste.group(0), \
        "block-chip paste must respect the Blocks toggle"
    # XSS guard: raw text is escaped before markdown tags are injected
    fn = re.search(r"function _mdRender\(src\) \{.*?\n\}", html, re.S)
    assert fn and "_mdEsc(src)" in fn.group(0), "must escape HTML before rendering"
    # preview is fed on input, after Improve, and after send clears the field
    assert "_mdAuto(r.improved)" in html
    assert "if (_mdOn) _mdRenderNow()" in html
    # both toggles persist
    assert "tg_md" in html and "tg_blocks" in html

def test_all_handlers_import():
    import handlers.audio  # noqa: F401
    import handlers.claude  # noqa: F401
    import handlers.files  # noqa: F401
    import handlers.general  # noqa: F401
    import handlers.git  # noqa: F401
    import handlers.input  # noqa: F401
    import handlers.panel  # noqa: F401
    import handlers.project  # noqa: F401
    import handlers.screen  # noqa: F401
    import handlers.shell  # noqa: F401
    import handlers.web_extra  # noqa: F401
    import handlers.windows  # noqa: F401
    import utils.webauth  # noqa: F401


# --- file attachments ---------------------------------------------------------

def _src(*parts):
    """Read a source file of the project (path relative to the repo root)."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_safe_name_cannot_escape_the_upload_dir():
    """The name arrives from a phone in an HTTP header — attacker-shaped input.
    It must come out a bare file name, never a path and never empty."""
    from utils.uploads import safe_name
    assert safe_name(r"..\..\autoexec.bat") == "autoexec.bat"
    assert safe_name("/etc/passwd") == "passwd"
    assert safe_name("../../../x.md") == "x.md"
    assert not re.search(r'[\/:*?"<>|]', safe_name('a:b*c?"d<e>f|g.md'))
    assert safe_name("..") and ".." not in safe_name("..")
    assert safe_name("") and safe_name(None)
    assert safe_name("  .hidden.md ") == "hidden.md"      # leading dot/space stripped
    assert safe_name("отчёт.md") == "отчёт.md"            # Cyrillic survives
    long_name = safe_name("x" * 400 + ".md")
    assert len(long_name) <= 120 and long_name.endswith(".md")


def test_save_upload_never_overwrites():
    """The same report.md twice is two files: the first may already be open in
    the session that asked for it."""
    import shutil

    import config
    from utils import uploads
    tmp = os.path.join(ROOT, "tests", "_tmp_uploads")
    old = uploads.UPLOAD_DIR
    config.UPLOAD_DIR = uploads.UPLOAD_DIR = tmp
    try:
        a = uploads.save_upload(b"first", "report.md")
        b = uploads.save_upload(b"second", "report.md")
        assert a != b
        with open(a, "rb") as f:
            assert f.read() == b"first", "first upload was clobbered"
        assert b.endswith(".md"), "collision suffix must go before the extension"
    finally:
        config.UPLOAD_DIR = uploads.UPLOAD_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_path_token_lives_in_one_place():
    """Quoting + the trailing space are one rule. A second copy is how one entry
    point silently starts typing an unquoted path that splits in two."""
    from utils.uploads import path_token
    assert path_token(r"C:\tmp\a.md") == "C:" + chr(92) + "tmp" + chr(92) + "a.md "
    quoted = path_token(r"C:\my files\a.md")
    assert quoted.startswith('"') and quoted.endswith('" ')
    src = _src("handlers", "web_extra.py")
    assert '"{path}" ' not in src, "web_extra grew its own copy of the quoting rule"
    assert src.count("path_token(path)") == 2, "paste and upload must share one helper"


def test_upload_endpoint_guards():
    async def go():
        async with await _client() as c:
            r = await c.post("/api/upload", data=b"x")
            assert r.status == 401, "upload is not behind auth"
            r = await c.post("/api/upload", headers=AUTH, data=b"")
            assert (await r.json())["ok"] is False, "empty body must be a 4xx, not a 500"
            from utils.uploads import MAX_UPLOAD
            r = await c.post("/api/upload", headers=AUTH, data=b"x" * (MAX_UPLOAD + 1))
            assert r.status == 413, r.status
    _run(go())


def test_upload_is_not_reachable_by_a_refine_token():
    """Typing a path into a focused window is remote control; /refine has none."""
    src = _src("handlers", "web_extra.py")
    body = src.split("async def api_upload(request):", 1)[1].split("\nasync def ", 1)[0]
    assert "_check_auth(request)" in body
    assert "_check_auth_refine" not in body


def test_client_attaches_files_before_text():
    """A file types a PATH with no Enter and the text write reuses the clipboard,
    so files must go first and the typed path needs time to land."""
    html = _html()
    assert 'id="file-input"' in html and 'id="attach-btn"' in html
    assert html.count('type="file"') == 1, "two pickers = two ways for the list to go stale"
    assert "pickFiles(true)" in html, "no attach button inside the viewer"
    fn = html.split("async function doType()", 1)[1].split("\n}", 1)[0]
    assert fn.index("uploadFile(files[i].file)") < fn.index("/api/paste"), \
        "files are sent after images"
    assert fn.index("/api/paste") < fn.index("/api/type"), "attachments sent after the text"
    up = html.split("async function uploadFile(", 1)[1].split("\n}", 1)[0]
    assert "encodeURIComponent(file.name)" in up, "a non-ASCII name will not survive"
    assert "e.dataTransfer.files" in html and "clipboardData.files" in html


def test_telegram_document_entry_point():
    """Sending the file straight to the chat is the shortest path from a phone."""
    bot_src = _src("bot.py")
    assert "filters.Document.ALL, document_handler" in bot_src
    assert 'pattern="^f:"' in bot_src
    src = _src("handlers", "upload.py")
    # Enter is sequenced in exactly one place — a local Enter lands inside the paste
    assert "type_and_enter" in src and "press_keys" not in src
    assert "TG_DOWNLOAD_LIMIT" in src, "20MB Bot API download limit is not handled"


def test_quick_keys_bar_has_vertical_arrows():
    """Claude Code moves its option selector UP and DOWN, so the bar you answer a
    question from needs those two keys — ←/→ alone cannot pick an option. Only the
    bottom bar: the viewer row is deliberately left as it is."""
    html = _html()
    bar = re.search(r'<div id="quick-keys">.*?</div>\s*</div>', html, re.S).group(0)
    for key in ("doKey('up')", "doKey('down')"):
        assert bar.count(key) == 1, f"bottom bar lacks exactly one {key}"
    # order is part of the agreed row: the vertical pair leads the arrow cluster
    assert bar.index("doKey('up')") < bar.index("doKey('down')") < bar.index("doKey('left')")
    # the trail is fed from doKey, so an unmapped key shows up as raw 'up'
    labels = html.split("const _QK_LABELS = ", 1)[1].split("};", 1)[0]
    assert "up: '↑'" in labels and "down: '↓'" in labels
    # the viewer row stays a decision, not a forgotten place
    lb = re.search(r'<div id="lb-keys">.*?</div>', html, re.S).group(0)
    assert "doKey('up')" not in lb
    # A 360px phone cannot fit …/4 arrows/Enter/Sh+Tab/Tab + the field, and none of
    # them is droppable — the keys scroll instead, and the row must NOT wrap: the
    # 62px clearance is fixed, so a second line would cover the last panel.
    # anchor on a rule unique to the bar block: the first 560px block on the page
    # is a one-liner, and splitting on it swallows the rest of the stylesheet.
    css = html.split(".qk-input{width:84px}", 1)[1].split(chr(10) + "}", 1)[0]
    btns = re.search(r"\.qk-btns\{([^}]*)\}", css).group(1)
    assert "overflow-x:auto" in btns, "narrow bar still overflows the viewport silently"
    assert "flex-wrap" not in btns, "a wrapped bar sits on top of the last panel"
    assert ".qk-arrow{" in css, "arrows are not compacted on a phone"
    # The answer field is a SIBLING of the scrolling key row, never its last child:
    # inside .qk-btns it scrolled off with the keys, which is the exact opposite of
    # what the comment beside that rule claimed for two versions.
    qk_btns_markup = re.search(r'<div class="qk-btns">.*?</div>', bar, re.S).group(0)
    assert 'id="qk-type"' not in qk_btns_markup, "the answer field scrolls away with the keys"
    assert 'id="qk-type"' in bar, "the answer field left the bar entirely"
    # Compaction is a RULE, not a pile of numbers: horizontal is the scarce axis, so
    # inline padding and gaps shrink while tappable height is held. Any two-value
    # padding here dropping below 6px vertical is shrinking a touch target on the one
    # device where that is unaffordable.
    for v in re.findall(r"padding:(\d+)px \d+px", css):
        assert int(v) >= 6, f"phone block shrinks a touch target vertically ({v}px)"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
