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
    #screen-area — capture() replaces that element's children every frame."""
    html = _html()
    assert 'class="screen-wrap"' in html, "scroll pad lost its stable container"
    assert html.count('data-scroll="up"') == 2, "expected arrows on the view and in the lightbox"
    assert "bindScrollPads()" in html
    assert "SCROLL_REPEAT_MS" in html and "setInterval" not in html.split("_scrollHold")[1][:400], \
        "hold-repeat must chain from completion, not fire on a fixed interval"


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
    monkeypatch.setattr(pyautogui, "hotkey", lambda *k: events.append(("hotkey", "+".join(k))))
    monkeypatch.setattr(pyautogui, "press", lambda k: events.append(("press", k)))
    monkeypatch.setattr(tg_input.time, "sleep", lambda s: events.append(("sleep", s)))
    monkeypatch.setattr(tg_input, "get_active_window_title", lambda: "win", raising=False)

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
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


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


# --- Python side sanity ---

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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
