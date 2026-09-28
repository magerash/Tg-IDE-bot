"""LLM caller contract — utils/humanize.py, shared by /api/stt and /api/improve.

Split out of test_web.py, which is past its 1500-line cap. Same style: pure helpers
tested directly, the network call tested through a fake aiohttp session so the
payload and the response handling are pinned without a key.
"""
import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Resp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def json(self, content_type=None):
        return self._body


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _Session:
    """Records the payload and answers with a scripted body."""
    def __init__(self, status=200, body=None):
        self.status, self.body, self.payloads = status, body, []

    def post(self, url, json=None, headers=None):
        self.payloads.append(json)
        return _Ctx(_Resp(self.status, self.body))


def _ok(content, finish="stop"):
    return {"choices": [{"finish_reason": finish,
                         "message": {"role": "assistant", "content": content}}]}


def test_reasoning_effort_is_per_model():
    """gpt-oss answers 400 to `none` (it takes low/medium/high only) and at its
    default effort spent the whole budget thinking about the twin persona and
    returned an empty content. qwen3 takes `none`. One value cannot serve both."""
    from utils.humanize import _reasoning_for

    spec = "qwen=none,openai/gpt-oss=low"
    assert _reasoning_for("qwen/qwen3.6-27b", spec) == "none"
    assert _reasoning_for("openai/gpt-oss-20b", spec) == "low"
    assert _reasoning_for("groq/compound", spec) is None, "unknown model: send nothing"
    assert _reasoning_for("openai/gpt-oss-20b", "none") == "none", "bare value = every model"
    assert _reasoning_for("qwen/qwen3.6-27b", "off") is None
    assert _reasoning_for("qwen/qwen3.6-27b", "qwen=off") is None

    from config import HUMANIZE_FALLBACKS, HUMANIZE_MODEL
    for model in [HUMANIZE_MODEL] + HUMANIZE_FALLBACKS:
        if model.startswith("openai/gpt-oss"):
            assert _reasoning_for(model) in ("low", "medium", "high"), model


def test_output_budget_is_bounded_and_sent():
    """Groq rejects a request whose EXPECTED output exceeds the per-model OTPM cap
    before running it, and with max_tokens unset it expects 2048 — over this org's
    1000 on qwen3.6-27b, so every call 429'd. The budget must always be sent, sized
    from the input, and never above the cap."""
    from config import HUMANIZE_MAX_TOKENS
    from utils.humanize import _call, _max_tokens

    assert HUMANIZE_MAX_TOKENS < 1000, "cap must sit under the measured OTPM limit"
    assert _max_tokens("") == 256
    assert _max_tokens("x" * 300) == 556
    assert _max_tokens("x" * 5000) == HUMANIZE_MAX_TOKENS

    s = _Session(body=_ok("чистый текст"))
    out = asyncio.run(_call(s, "qwen/qwen3.6-27b", "sys", "привет", "none"))
    assert out == "чистый текст"
    assert s.payloads[0]["max_tokens"] == _max_tokens("привет")
    assert s.payloads[0]["reasoning_effort"] == "none"

    s = _Session(body=_ok("x"))
    asyncio.run(_call(s, "openai/gpt-oss-20b", "sys", "hi", None))
    assert "reasoning_effort" not in s.payloads[0], "None must send no reasoning key"


def test_truncated_reply_is_refused_not_returned():
    """A reply cut at the budget would be typed into a terminal as if whole; the
    phone has no way to see the cut. finish_reason=length is a failure of that
    model, so the chain moves on or fails loudly — it never returns the fragment."""
    from utils.humanize import _call

    s = _Session(body=_ok("half of the ans", finish="length"))
    try:
        asyncio.run(_call(s, "qwen/qwen3.6-27b", "sys", "text", "none"))
    except RuntimeError as e:
        assert "truncated" in str(e) and "HUMANIZE_MAX_TOKENS" in str(e)
    else:
        raise AssertionError("a truncated reply was returned as a result")

    s = _Session(status=429, body={"error": {"message": "Request too large"}})
    try:
        asyncio.run(_call(s, "qwen/qwen3.6-27b", "sys", "text", "none"))
    except RuntimeError as e:
        assert str(e).startswith("429: Request too large")
    else:
        raise AssertionError("a 429 was swallowed")
