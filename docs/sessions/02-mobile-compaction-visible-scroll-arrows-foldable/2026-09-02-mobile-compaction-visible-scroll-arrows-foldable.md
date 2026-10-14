# 2026-09-02 — the arrows were never missing, they were invisible

Row 8. Three things reported in one sentence — *"make buttons more compact fit in mobile
view. i don't see arrows up and down there. It will be nice to be able to hide all of them
like in bottom accordeon"* — which turned out to be one styling bug, one sizing pass and one
new control.

## What was done

**The ▲▼ scroll arrows.** The interesting part is what this was *not*. The operator said
"nothing at all" at the right edge of the screenshot, which reads like a layout or a caching
failure, and both were ruled out with evidence rather than by inspection:

- no `@media` block touches `.scroll-pad` / `.screen-wrap` / `#screen-area`; nothing in JS
  sets `display` on the pad; it is not clipped, because the `overflow:hidden` is on
  `#screen-area` and the pad is deliberately its **sibling** (so `capture()`'s
  `replaceChildren` cannot wipe it — the reason for that split, paying off again);
- the phone was **not** running a stale page. The access log shows that device
  (`Vivo V2419A`, `Telegram-Android/12.10.0`) calling `GET /api/layout` — an endpoint that
  exists only in the current, uncommitted client — with frames flowing normally (63KB bodies,
  `204` on unchanged).

So the markup was in its DOM the whole time. What was left was `rgba(20,19,17,.42)` with no
border, no shadow, a 15px glyph in a 40px circle, and `:hover` — which never fires on
touch — as the **only** rule that raised the contrast. A dark pill on a dark VS Code
screenshot. Fixed with a light hairline ring rather than a theme-aware fill (`D-016`), a
`.78` fill, a shadow, a 17px/600 glyph, and 44px targets on a phone.

Two bugs found inside the six lines being edited, neither reported:

- `:active`/`.on` was `var(--accent)`, which in night theme is `#ece9e4` against `color:#fff`
  — **the held state of a hold-to-scroll was white on white.** The one control whose entire
  interaction is "press and keep pressing" had no feedback at all in dark mode. Now `var(--ok)`.
- `#qk-type` was the last child of `.qk-btns`, the row that scrolls at ≤560px, so the answer
  field **scrolled away with the keys** — the exact opposite of what the comment beside that
  rule had claimed for two versions. Moved out to be a sibling.

**Compaction** at ≤560px, under one rule: *horizontal is the scarce axis*, so inline padding
and gaps shrink and tappable height is held. `.panel` 14→11, `.tight` 12→9, `.btn` inline
14→10, `.btn-sm` 11→8, chips 12→9, gaps 6→5; no vertical padding below 6px, `#mic-btn` keeps
46px, and the scroll pads *grow* while everything else shrinks.

**The fold.** `#qk-toggle`, a caret at the far left of the bar — the one slot the phone block
already empties. Reuses `.panel.acc` wholesale: pseudo-element caret, the `acc_` localStorage
namespace, expanded by default.

## How it works

The fold's only real design decision is that the class goes on `<body>`, not on the bar. The
two things that must follow it — the body's bottom clearance and `#toast` — are not
descendants of `#quick-keys`, so a class on the bar could not reach them. And it is a class
rather than a `--qk-h` custom property because the clearance appears as the literal `62px` in
two places that a test pins byte-for-byte; `body.qk-hidden` is `(0,1,1)` against `body`'s
`(0,0,1)`, and media queries add no specificity, so **one rule overrides both breakpoints**
without rewriting either literal.

Frame size is unaffected, which was checked rather than assumed: `_fitBaseW()` rounds
`clientWidth × dpr` up to a 160px bucket, and 360px/dpr2 lands in 640 both before and after
the panel-padding change — no extra bytes over the tunnel.

## Decisions (and why)

- `D-016` — the scroll pads are styled against the **screenshot**, not the page theme, and
  the ring is what does the work. Supersedes nothing; it makes explicit a rule that had never
  been written down, which is why the pads were styled as decoration.

## Verification

```bash
python -m pytest tests/ -q          # 94 passed, 3.75s — 12 new assertions, no new test files
python tools/wiki/check-links.py    # 0 broken
python tools/wiki/wiki-doctor.py    # clean
node --check <inline scripts>       # OK
```

The new assertions were **mutation-tested**, because an assertion that cannot fail is worse
than none. Eight reverts, eight failures: drop the ring/shadow, drop the 44px, restore
`var(--accent)`, remove `body.qk-hidden{padding-bottom:26px}`, remove the toast offset, put
`#qk-type` back inside the scrolling row, shrink a `.btn-sm` vertical to 4px, replace the
caret pseudo-element. Each one fails the test that owns it.

One test was **passing while measuring the wrong thing**: `test_quick_keys_bar_at_bottom`
matched the bar with `</div>\s*</div>`, which after `#qk-type` moved out captured the bar's
close plus `#main`'s — seven characters too long, still containing everything asserted.
Re-anchored on the column-0 close. A second trap was hit while writing the new assertions:
the *first* `@media(max-width:560px)` on the page is the one-liner `.cc-meters` rule, so a
naive regex for the phone block swallows the rest of the stylesheet — the same trap the
neighbouring test already documents, now documented in this one too.

Also verified statically: `#quick-keys` has exactly four children in order
(`#qk-toggle`, `.qk-trail`, `.qk-btns`, `#qk-type`), `.qk-btns` contains only `<button>`s (so
the test's first-`</div>` assumption holds), one `#qk-type`, one `#qk-toggle`, and the served
page carries every new rule (111,313 → 116,730 bytes).

**Not verified, and it needs the operator:** the visual result at 360px on the actual phone,
in both themes. `/api/status` returns 401 without `WEB_TOKEN`, and `.env` is denied to agents
by `.claude/settings.json` — correctly — so no authenticated browser check was possible here.
The tests pin the CSS *text*; only a device confirms the arrows are now findable at a glance
over a live screenshot.

## Next

Look at the phone: the arrows over a dark VS Code screenshot, the fold releasing its 36px,
and a flick of the bottom key row proving `#qk-type` no longer travels with it.

Then **row 2** — this belongs to v0.21.0 and ships with the attachment/layout work already in
the tree; it needs "Let's finish" for the version bump, the changelog and the commit.

Do **not** start row 5 (splitting the web handlers) in the same session — `web.py` is where
the v0.21.0 routes live, and a split on top of uncommitted feature work makes both
unreviewable. Row 9 (the welded-shut stale-client reload) is one line and unrelated to any of
this; it can go any time.
