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
