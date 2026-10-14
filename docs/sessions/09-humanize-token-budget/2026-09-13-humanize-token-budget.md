# 2026-09-13 — Humanize token budget: the 429 that never reached the model

## What was done

Row 22. **✨ Improve** and the voice cleanup failed on the phone with a red toast:
`qwen/qwen3.6-27b -> 429: Request too large … output tokens per minute (OTPM): Limit 1000,
Requested 2048`. Both models in the chain were failing, for two different reasons, and
the toast only had room for the first.

- `utils/humanize.py` — every request now carries `max_tokens`, sized from the input and
  capped at `HUMANIZE_MAX_TOKENS`; the reasoning effort is chosen **per model** by
  `_reasoning_for()`; a reply with `finish_reason=length` raises instead of returning.
- `config.py` — `HUMANIZE_MAX_TOKENS` (900), `HUMANIZE_REASONING` becomes a prefix map
  (`qwen=none,openai/gpt-oss=low`; a bare value still applies to every model).
- `tests/test_llm.py` — new file, three tests, five deliberate mutations all red.
  `test_web.py` is past its 1500-line cap, so the LLM caller gets its own file.

## How it works

**Groq rejects on the *expected* output, before the model runs.** The OTPM check compares
the request's `max_tokens` against a per-model, per-org cap; with `max_tokens` unset the
expectation is the model default, 2048, and this org's cap on qwen3.6-27b is 1000. So the
primary model never saw a single request — the log shows `Requested` wandering between 1082
and 2048 as the minute window filled, never below the limit.

**The fallback failed on its own bug, which is why the chain did not save it.** gpt-oss-20b
takes only `low|medium|high` and answers **400** to the `none` that qwen needs. The code then
retried without the parameter — the model's default is medium — and on the 6KB twin persona
it spent the whole budget thinking and returned an **empty content**, which the chain
reported as `empty after stripping reasoning`. Once, in the whole log, it answered; twice it
was empty; once it hit its own **8000 TPM** cap, because a twin request is ~3.4K tokens and
the operator had tapped twice in a minute.

**The budget is `len(text) + 256`, capped.** Russian tokenises at ~2.5 chars per token
(measured: 289 prompt tokens for ~600 chars), so `len(text)` tokens is ~2.5× the input — room
for the expanding `detailed` style — and the 900 cap sits under the 1000 OTPM. A reply that
hits the cap is refused (`D-030`): the phone types the result into a terminal and cannot see
that it was cut.

**Known limit, stated rather than hidden:** a dictation whose *output* needs more than ~900
tokens (roughly 2000+ chars of Russian) fails on both models with
`output truncated at 900 tokens (HUMANIZE_MAX_TOKENS)`. Before this change it failed on the
first request anyway; now it says why.

## Decisions (and why)

- `D-030` — the budget is sent, sized from the input, and a truncated reply is refused.
- `D-013` still holds: the chain and the loud failure are what made this diagnosable from
  the log alone. The toast, at 300 chars per model error, only ever showed the first.

## Verification

Live probe, `probe_groq.py` in the scratchpad, 2026-09-13 11:29, this org's key:

| Call | Result |
|---|---|
| qwen3.6-27b, twin, no `max_tokens` | `429 … Limit 1000, Requested 2048` in 0.59s |
| qwen3.6-27b, twin, `max_tokens=700` | 200 in 1.28s, `finish=stop`, 1823/79 tokens |
| gpt-oss-20b, `reasoning_effort=none` | `400 reasoning_effort must be one of low, medium, or high` |
| gpt-oss-20b, `reasoning_effort=low` | 200 in 0.49s, content 213 chars, reasoning 24 chars |

Through the real path after the fix — `improve(text, "concise", twin=True)`, 373 chars of
Russian: **200, 373 → 280 chars, served by qwen, no fallback warning logged.**

```
python -m pytest tests/ -q          # 120 passed in 5.41s
```

Mutations against `tests/test_llm.py`, each restored after: `max_tokens` not sent → RED;
truncation returned → RED; prefix match ignored → RED; gpt-oss given `none` → RED; cap
raised to 2048 → RED.

Not verified: the `length` branch against the live API (it needs a reply that actually hits
the cap, and every probe finished with `stop`); a Telegram voice message through the same
chain — same function, not run today.

## Next

- The toast truncates each model's error at 300 chars and shows the chain in order, so the
  *second* failure — the one that actually decided the outcome — is never visible on the
  phone. Worth shortening the Groq messages to their first sentence.
- `qwen/qwen3.8-27b` and `openai/gpt-oss-120b` are now listed for this key
  (`GET /openai/v1/models`, 2026-09-13); neither was probed for limits or quality.
- Row 3 (`bot.log` rotation) is now 3.35GB, and this session read it with `tail -c`.
