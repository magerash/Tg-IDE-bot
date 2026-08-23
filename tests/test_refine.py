"""Tests for the split-view refinement surface (/refine).

Same style as test_web.py: the aiohttp app booted in-process for routes, plain
regex over the client files for UI invariants. The load-bearing ones here are
the isolation tests — they are what turns "the refine view can't type to your
PC" from a UI promise into something CI refuses to let regress.
"""
import asyncio
import os
import re
import sys

import pytest
from aiohttp.test_utils import TestClient, TestServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import VERSION, WEB_TOKEN          # noqa: E402
from handlers.web import create_web_app        # noqa: E402

AUTH = {"Authorization": f"Bearer {WEB_TOKEN}"}
INDEX = os.path.join(ROOT, "web", "index.html")
REFINE = os.path.join(ROOT, "web", "refine.html")
COMMON = os.path.join(ROOT, "web", "common.js")

# Everything the refine surface must not be able to reach. /api/status,
# /api/stt, /api/improve and /api/scope are the whole allow-list.
SYSTEM_PATHS = [
    "/api/type", "/api/sh", "/api/key", "/api/click", "/api/scroll", "/api/git",
    "/api/build", "/api/apks", "/api/restart", "/api/frame", "/api/screen",
    "/api/window", "/api/paste", "/api/claude", "/api/focus", "/api/windows",
    "/api/folders", "/api/project", "/api/code", "/api/schedule", "/api/schedules",
    "/api/unschedule", "/api/ccmetrics",
]


def _run(coro):
    return asyncio.run(coro)


async def _client():
    return TestClient(TestServer(create_web_app()))


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _refine():
    """refine.html + the shared script it loads — the page as the browser sees it."""
    return _read(REFINE) + "\n" + _read(COMMON)


async def _mint(c):
    r = await c.post("/api/scope", headers=AUTH, json={"scope": "refine"})
    return (await r.json())["token"]


# --- the page ----------------------------------------------------------------

def test_refine_page_served():
    """/refine is a real route with the same no-cache contract as /, not just a
    file that happens to sit in the static dir."""
    async def go():
        async with await _client() as c:
            r = await c.get("/refine")
            assert r.status == 200
            assert "no-store" in r.headers.get("Cache-Control", "")
            body = await r.text()
            assert "<!DOCTYPE html>" in body
            assert len(body) > 2000
    _run(go())


def test_refine_page_has_no_system_endpoints():
    """The isolation test. Neither the refine page nor the shared script may
    even NAME a system endpoint — that is what stops someone moving doType or
    doTypePreset into common.js 'for reuse' and quietly handing the refine view
    a keyboard again."""
    for name, blob in (("refine.html", _read(REFINE)), ("common.js", _read(COMMON))):
        hits = [p for p in SYSTEM_PATHS if p in blob]
        assert not hits, f"{name} reaches system endpoints: {hits}"


def test_common_js_has_no_dashboard_only_code():
    """Dashboard-only helpers carry no /api/ string, so the endpoint scan above
    cannot catch them — and alignRails() does
    .observe(document.querySelector('.center')), which throws on a page with no
    .center and kills every statement after it in the same script."""
    common = _read(COMMON)
    for fn in ("alignRails", "renderTools", "bindScrollPads", "requestCapture",
               "openLightbox", "doType", "doTypePreset", "_tgBack"):
        assert fn not in common, f"{fn} belongs in index.html, not common.js"


def test_refine_page_element_ids_exist():
    """Blind spot of the shared-script split: test_web.py validates common.js's
    getElementById calls against index.html only, so an id that exists there and
    not here would ship green and null-deref on load."""
    src = _refine()
    used = set(re.findall(r"getElementById\('([\w-]+)'\)", src))
    declared = set(re.findall(r'id="([\w-]+)"', _read(REFINE)))
    assert used <= declared, f"refine.html missing ids: {sorted(used - declared)}"


def test_refine_onclick_handlers_defined():
    """Every onclick in refine.html resolves in refine.html or common.js."""
    src = _refine()
    called = set(re.findall(r'onclick="(\w+)\(', _read(REFINE)))
    defined = set(re.findall(r"(?:async\s+)?function\s+(\w+)", src))
    assert called <= defined, f"undefined handlers: {sorted(called - defined)}"


def test_refine_has_no_type_button():
    """Copy-only was a deliberate product decision: text leaves this view via
    the clipboard, never via the PC's keyboard."""
    refine = _read(REFINE)
    assert 'onclick="doType()"' not in refine
    assert "function doType" not in _read(COMMON)
    assert 'id="copy-btn"' in refine


def test_the_two_views_link_to_each_other():
    """Without this the refine view is only reachable from /panel — invisible in
    a browser, and invisible in Telegram to anyone who opens the Mini App with
    the menu button. Discoverability, reported the day it shipped."""
    assert 'href="/refine"' in _read(INDEX), "dashboard has no way into the refine view"
    assert 'href="/"' in _read(REFINE), "refine view is a dead end"
    for page in (INDEX, REFINE):
        assert "view-link" in _read(page)


def test_refine_and_index_share_theme_tokens():
    """Both palettes must be character-identical or the two surfaces read as
    different apps in dark mode."""
    for pattern in (r"^:root\{.*?^\}", r'^:root\[data-theme="dark"\]\{.*?^\}'):
        a = re.search(pattern, _read(INDEX), re.S | re.M)
        b = re.search(pattern, _read(REFINE), re.S | re.M)
        assert a and b, f"missing theme block: {pattern}"
        assert a.group(0) == b.group(0), "theme tokens drifted between the pages"


def test_static_script_stamps_match_version():
    """A stale HTML pins an old ?v= and loads the matching old common.js — a
    consistent pair, which _checkStaleClient can then reload past. Drop the
    stamp and you get fresh HTML against cached JS: silent, per-device, and
    invisible on desktop."""
    for page in (INDEX, REFINE):
        stamps = re.findall(r'<script src="/static/[\w.]+\.js\?v=([\d.]+)"', _read(page))
        assert stamps, f"{os.path.basename(page)} loads no version-stamped script"
        for s in stamps:
            assert s == VERSION, f"{os.path.basename(page)}: ?v={s} != config {VERSION}"


def test_copy_button_exists_with_fallback():
    """Telegram's Android webview rejects the async clipboard API, and any await
    before the write drops transient user activation — the classic 'works on
    desktop, does nothing on my phone'."""
    refine = _read(REFINE)
    body = re.search(r"async function doCopy\(\) \{.*?\n\}", refine, re.S)
    assert body, "doCopy not defined"
    body = body.group(0)
    assert "navigator.clipboard" in body and "writeText" in body
    assert "execCommand('copy')" in refine, "no fallback for webviews that refuse"
    # empty field is handled before anything touches the clipboard
    empty = body.index("Nothing to copy")
    assert empty < body.index("writeText"), "empty guard must precede the clipboard"
    # nothing may be awaited before the write, or the gesture is spent
    before = body[:body.index("await navigator.clipboard.writeText")]
    assert "await " not in before, f"await before the clipboard write:\n{before}"


def test_markdown_preview_cannot_execute_script():
    """The preview is the one place user text becomes HTML, and it is default-ON
    here. A javascript: link or an href-breaking quote would run script with this
    origin's credentials — walking straight past the scoped token, since
    localStorage and Telegram.WebApp are same-origin state no token can fence."""
    common = _read(COMMON)
    esc = re.search(r"function _mdEsc\(s\) \{[\s\S]*?^\}", common, re.M).group(0)
    for ch in ("&", "<", ">", '"', "'"):
        assert ch in esc, f"_mdEsc no longer escapes {ch!r}"
    assert "function _mdSafeUrl" in common, "link scheme is unchecked"
    safe = re.search(r"function _mdSafeUrl\(u\) \{[\s\S]*?^\}", common, re.M).group(0)
    assert "https?" in safe and "mailto" in safe
    link = re.search(r"_mdSafeUrl\(url\);.*?\}\);", common, re.S).group(0)
    assert "safe ?" in link, "unsafe URLs must fall back to plain text, not an href"


def test_refine_refuses_the_ambient_credential():
    """common.js builds `const TG` from Telegram.WebApp.initData for the lifetime
    of the page. On refine that would hand any later code a full credential, so
    the page opts out before common.js runs."""
    refine, common = _read(REFINE), _read(COMMON)
    assert "window.NO_AMBIENT_AUTH = true;" in refine
    assert refine.index("NO_AMBIENT_AUTH") < refine.index("/static/common.js"),         "the flag must be set before common.js reads it"
    assert "!window.NO_AMBIENT_AUTH" in common, "common.js ignores the opt-out"


def test_stt_upload_never_uploads_unauthenticated():
    """sttUpload bypasses api(), so it needs its own guard: a failed mint must
    not send the recording with empty auth headers (which reads as 'the mic
    button does nothing'), and a stale token gets one retry."""
    refine = _read(REFINE)
    body = re.search(r"sttUpload = async function \(blob\) \{[\s\S]*?^\};", refine, re.M)
    assert body, "sttUpload is not wrapped on the refine page"
    body = body.group(0)
    assert "if (!await _ensureScope()) return" in body, "uploads without a scope"
    assert "_isAuthErr(r)" in body and "_mintScope()" in body, "no retry on a stale token"
    assert body.count("_rawStt(blob)") == 2, "exactly one retry, never a loop"


def test_split_preview_selector_matches_the_toggled_class():
    """The class is toggled ON the .split element, so a `.md-on .split` descendant
    selector would silently never match and the side-by-side layout would be dead
    CSS."""
    refine = _read(REFINE)
    assert ".split.md-on{" in refine, "split layout uses a descendant selector"
    assert "classList.toggle('md-on'" in refine
    toggle = re.search(r"function _syncSplit\(\) \{[\s\S]*?^\}", refine, re.M).group(0)
    assert "type-split" in toggle


def test_refine_uses_its_own_md_key_and_shared_history():
    """Separate markdown key (this field is a document, the dashboard's is
    terminal input); shared history on purpose, which needs every kind routed to
    the one field that exists here."""
    refine = _read(REFINE)
    assert "tg_md_refine" in refine and "MD_DEFAULT_ON = true" in refine
    assert "HISTORY_TARGETS" in refine
    assert "sh-input" not in refine and "claude-input" not in refine
    common = _read(COMMON)
    assert "window.HISTORY_TARGETS ||" in common, "override hook lost"
    assert "if (!el) return;" in common, "history click can throw on a one-field page"


def test_refine_never_sends_the_full_credential():
    """common.js prefers initData when present, so without the AUTH_HEADERS hook
    the scoped token would be silently bypassed inside Telegram and the whole
    isolation story would be fiction."""
    common, refine = _read(COMMON), _read(REFINE)
    assert "function _authHeaders()" in common
    hook = re.search(r"function _authHeaders\(\) \{.*?\n\}", common, re.S).group(0)
    assert "window.AUTH_HEADERS" in hook, "hook must be read inside _authHeaders"
    api = re.search(r"async function api\(method.*?\n\}", common, re.S).group(0)
    assert "_authHeaders()" in api and "TG.initData" not in api
    stt = re.search(r"async function sttUpload\(blob\).*?\n\}", common, re.S).group(0)
    assert "_authHeaders()" in stt and "TG.initData" not in stt
    assert "window.AUTH_HEADERS = () =>" in refine
    # initData is read through one accessor and never kept: index.html holds it
    # in `const TG` for the page's lifetime, which is what this view must not do
    assert not re.search(r"^\s*(?:const|let)\s+TG\s*=", refine, re.M),         "refine must not hold a full credential in a module global"
    assert refine.count("Telegram.WebApp.initData") == 2,         "initData should appear once in _fullCred() and once in its comment"
    assert "sessionStorage" in refine and "localStorage.setItem(SCOPE_KEY" not in refine


# --- scoped auth -------------------------------------------------------------

def test_scope_endpoint_requires_full_auth():
    """A scoped token must not mint another, or its 12h life is unbounded."""
    async def go():
        async with await _client() as c:
            assert (await c.post("/api/scope", json={"scope": "refine"})).status == 401
            r = await c.post("/api/scope", headers=AUTH, json={"scope": "refine"})
            d = await r.json()
            assert d["ok"] and d["token"].startswith("refine.")
            assert d["ttl"] > 0
            bad = await c.post("/api/scope", headers=AUTH, json={"scope": "admin"})
            assert (await bad.json())["ok"] is False
            scoped = {"Authorization": "Bearer " + d["token"]}
            assert (await c.post("/api/scope", headers=scoped,
                                 json={"scope": "refine"})).status == 401
    _run(go())


def test_scoped_token_rejected_by_system_routes():
    """The invariant the product promise rests on: server-side, not UI-side."""
    async def go():
        async with await _client() as c:
            scoped = {"Authorization": "Bearer " + await _mint(c)}
            # Every forbidden path, driven off SYSTEM_PATHS — a hand-picked subset
            # would let a newly added route slip through untested.
            GETS = {"/api/windows", "/api/folders", "/api/apks", "/api/ccmetrics",
                    "/api/schedules", "/api/project"}
            for path in SYSTEM_PATHS:
                r = (await c.get(path, headers=scoped) if path in GETS
                     else await c.post(path, headers=scoped, json={}))
                assert r.status == 401, f"{path} accepted a refine-scoped token"
    _run(go())


def test_scoped_token_accepted_by_refine_routes():
    """400 not 401 on empty text proves the request got PAST auth."""
    async def go():
        async with await _client() as c:
            scoped = {"Authorization": "Bearer " + await _mint(c)}
            assert (await c.get("/api/status", headers=scoped)).status == 200
            r = await c.post("/api/improve", headers=scoped, json={"text": "   "})
            assert r.status == 400 and (await r.json())["ok"] is False
            assert (await c.post("/api/stt", headers=scoped, data=b"x")).status != 401
    _run(go())


def test_scoped_token_expiry_and_tampering():
    """Unit-level: the scope is inside the MAC (else the prefix is editable),
    and an unset secret validates nothing — BOT_TOKEN is None in CI."""
    from utils import webauth as wa
    tok = wa.make_scoped_token("s3cret", "refine")
    assert wa.verify_scoped_token(tok, "s3cret", "refine")
    assert not wa.verify_scoped_token(tok, "s3cret", "admin")
    assert not wa.verify_scoped_token(tok, "other", "refine")
    assert not wa.verify_scoped_token(wa.make_scoped_token("s3cret", "refine", -1),
                                      "s3cret", "refine")
    flipped = tok[:-1] + ("0" if tok[-1] != "0" else "1")
    assert not wa.verify_scoped_token(flipped, "s3cret", "refine")
    # rewriting the prefix must not promote the token
    assert not wa.verify_scoped_token("admin." + tok.split(".", 1)[1], "s3cret", "admin")
    assert not wa.verify_scoped_token("garbage", "s3cret", "refine")
    assert not wa.verify_scoped_token("refine.notanint.ab", "s3cret", "refine")
    assert wa.make_scoped_token("", "refine") == ""
    assert not wa.verify_scoped_token(tok, "", "refine")
    assert wa.SCOPE_TTL < wa.INIT_DATA_MAX_AGE, "a scope must not outlive its minter"


def test_every_api_handler_checks_auth():
    """No middleware guards these routes — the check is copy-pasted into all 27
    handlers, so a forgotten one is an open shell. And exactly three may take
    the refine-scoped variant."""
    refine_users = []
    for mod in ("web.py", "web_extra.py"):
        src = _read(os.path.join(ROOT, "handlers", mod))
        for m in re.finditer(r"async def (api_\w+)\(request\):(.*?)(?=\nasync def |\ndef |\Z)",
                             src, re.S):
            name, body = m.group(1), m.group(2)
            assert "_check_auth" in body, f"{mod}:{name} has no auth check"
            if "_check_auth_refine(request)" in body:
                refine_users.append(name)
    assert sorted(refine_users) == ["api_improve", "api_status", "api_stt"], refine_users


# --- entry points ------------------------------------------------------------

def test_refine_url_is_version_stamped():
    from handlers.web import refine_url
    assert refine_url("https://x.example/", "1.2.3") == "https://x.example/refine?v=1.2.3"
    assert refine_url("https://x.example", "1.2.3") == "https://x.example/refine?v=1.2.3"
    assert refine_url("https://x.example/?a=1", "1.2.3") == \
        "https://x.example/refine?a=1&v=1.2.3"


def test_panel_web_app_buttons_private_only(monkeypatch):
    """web_app inline buttons are private-chat only — Telegram answers
    BUTTON_TYPE_INVALID and fails the WHOLE message elsewhere, so an unguarded
    row would take /panel down in any group the bot is in."""
    from handlers import panel

    monkeypatch.setattr(panel, "WEBAPP_URL", "https://bot.example.com/")
    private = panel.build_keyboard("private").inline_keyboard
    assert len(private[0]) == 2 and all(b.web_app for b in private[0])
    assert private[0][1].web_app.url.endswith("/refine?v=" + VERSION)
    # python-telegram-bot normalises rows to tuples — compare structurally
    assert [list(r) for r in private[1:]] == [list(r) for r in panel._BASE_ROWS]

    for chat_type, url in (("group", "https://bot.example.com/"),
                           ("private", ""),
                           ("private", "http://insecure.example/")):
        monkeypatch.setattr(panel, "WEBAPP_URL", url)
        rows = panel.build_keyboard(chat_type).inline_keyboard
        assert not any(getattr(b, "web_app", None) for row in rows for b in row), \
            f"web_app button leaked into chat_type={chat_type} url={url!r}"
        assert len(rows) == len(panel._BASE_ROWS), "base rows must survive"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
