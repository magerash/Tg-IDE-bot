# 2026-09-07 — Mobile: four controls stay out, the rest folds

## What was done

Row 15, asked for straight after row 11 shipped: group the phone controls so the field, the
layout pill and the attach clip are always reachable and everything else hides behind one
caret. Both surfaces, one rule.

| Surface | Always out | Folds |
|---|---|---|
| Zoomed viewer (`#lb-bottom`) | Click · layout · 📎 · the field | windows, projects, Claude, interval, **Auto**, and the key row (1 2 ↑ ↓ ← → Enter Sh+Tab Tab) |
| Bottom bar (`#quick-keys`) | layout · **📎 (new)** · the field | the key strip and the recently-tapped trail |

Scroll and zoom pads keep their place and their contrast; only their corner radius changed
(50% → 12px). Close stays alone in the corner.

## How it works

**The viewer lost a row rather than gaining one.** `#lb-view-row` held exactly two pills — the
layout and Auto — across a full width, while the row above it wrapped for want of space. Auto
moved in beside `#lb-int`, the interval it sets; the layout pill moved out to the always-on
row. That zone is gone, and with it the "one button, whole row" shape the operator pointed at.

The markup is now three groups instead of three zones: `#lb-more` (the two folding rows,
stacked in a column), `#lb-quick` (Click · layout · 📎) and `#lb-entry` (the field and the
caret). DOM order is visual order — what folds sits above what stays.

**The bar's fold changed meaning** (`D-021`). It used to hide *everything* and leave a ~24px
sliver. On a phone the key strip already scrolls horizontally, so it never cost height — it
cost the **width** that left `.qk-input` at **84px**. Folding now hides the strip and the trail
only, and the field takes the whole bar. A consequence worth stating because a test now guards
it: clearance no longer depends on the state, `body.qk-hidden{padding-bottom:26px}` is gone,
and the two `62px` literals are again the whole story.

**The clip is new on both surfaces.** `pickFiles(true)` existed only inside the viewer's key
row and in the dashboard's Type panel — neither reachable while looking at a screenshot.

**One fold idiom, three users.** A class on the container, a caret from a `::after`
pseudo-element, one key in the `acc_` namespace — the same as `.panel.acc` and the quick-keys
bar. The viewer's *default* is the only new part: folded where the compact breakpoint matches,
open on a desktop viewer with room, and a stored choice beats both.

### Added in the same pass, after the first look on the phone

- **`1` and `2` on both bars** (`D-022`) — partially reversing v0.20.0, which removed them in
  favour of the freeform field. The field stays and still answers anything; what the original
  argument missed is that typing one character raises a keyboard **over the screenshot you are
  answering about**.
- **`↑ ↓` in the viewer's key row.** They were bottom-bar-only because four arrows cost width
  over the picture — an argument that expired when that row moved inside the fold. Until now a
  phone answering a numbered prompt from the zoomed view could not move the selector at all.
- **The floating pads are rounded squares**, `border-radius:50%` → `12px`. Contrast untouched:
  the ring and the dark fill are `D-016`'s and still tested.

## Decisions (and why)

- `D-021` — which four controls never fold and why Click is one of them; why the bar's sliver
  became an essentials row; the rejected alternative (a second always-on strip above the
  sliver, i.e. two bars where the phone has room for one).
- `D-022` — the digits return beside the field rather than instead of it, and the vertical
  arrows reach the viewer once its key row folds.

## Verification

```
python -m pytest tests/ -q
102 passed in 4.50s
```

Four existing tests pinned the old layout and were **rewritten, not deleted** — the three-zone
test became `test_viewer_controls_split_into_folding_and_always_on`, which pins the new
grouping with the same rigour: what folds, what cannot, that Click and the field are outside
the folding group, that Auto rides with its interval, that `lb-view-row` does not come back,
and that the default fold is conditional on the screen.

Eighteen mutations, all red. The grouping: Click folded away, the clip removed from either surface, nothing
hidden when folded, the fold default made unconditional, Auto alone in a row again, the layout
pill back inside the folding strip, the bar folding everything again, the state-dependent
clearance restored, the field folded away with the keys. Then the keys: the viewer losing its
vertical arrows again, digits dropped from either surface, digits replacing the field instead
of joining it, and three nesting mutations — the key row, the project row and the always-on
row each moved to the wrong side of the fold.

One of those three exposed a **false assertion of my own**: `assert '<div id="lb-keys">' in
more`, where `more` was the text between two markers, claimed containment but measured
position. A single stray `</div>` closes `#lb-more` and the assertion still passes over markup
that ships the key row outside the fold — it survived the mutation that proved it. Replaced
with `_nested_in()`, which counts the div balance, and all three nesting mutations then went
red.

Two things the tests caught that a reading would not have: the compact media block still
described "three zones" that no longer exist, and broadening `#lb-keys .qk-input` to
`.qk-input` inside a page-wide media query silently restyled the **dashboard bar's** field —
a bordered light-theme input given a viewer pill's height and radius. Scoped back to
`#lb-entry .qk-input`.

### Then it was actually rendered, and three things were wrong

The first pass shipped unseen and the operator reported the desktop viewer as "two rows, half
free, offset from each other". Headless Edge settles that kind of question in a minute —
method in [environment.md](../../environment.md) — and it found more than was reported:

1. **The caret was garbage.** `#lb-toggle::after{content:'BE'}` reached the file as a raw
   `0x15` byte plus `BE`: an octal escape eaten on the way in. The rule existed, the selector
   was right, the tests were green, and the glyph was a control character. **Only the picture
   showed it.** Now a literal `▾`/`▴` like `#qk-toggle`'s, pinned by a test.
2. **`#lb-more` was a column at every width.** It was written for the phone and applied to the
   desktop, which is exactly the two stacked half-empty rows that were reported — project zone
   left-aligned, key zone centred. Row on a wide screen, column only inside the compact
   breakpoint.
3. **`Auto` still wrapped alone** after that, and the reason was measurable rather than
   guessable: at 1500px the project zone's children need **773px** while its intrinsic base
   resolved to **705**, so with zero grow it broke a line while ~276px of the row sat empty.
   `flex:1 1 auto` lets it grow into the slack; `flex-wrap:wrap` stays as the narrow-window
   fallback, because `#lightbox` is `overflow:hidden` and nowrap would clip the last pill
   rather than move it.

The line-up now measures **one line** for the folding groups at 1500px (`#lb-more` h=38, both
zones at the same y) and two at 1100px, degrading by wrapping rather than clipping.

**Verified visually at last**, five renders: desktop viewer 1500px, phone viewer folded and
open at a true 390px viewport, dashboard bar folded and open. The phone bar folded is the one
that shows the point of the change — `[RU] [📎] [ type… ]` across the full width instead of an
84px field.

## Next

Row 14 is now more overdue, not less: `web/index.html` is 2675 against a 2400 budget. The
remedy is unchanged — extract the lightbox viewer as a page-specific file.
