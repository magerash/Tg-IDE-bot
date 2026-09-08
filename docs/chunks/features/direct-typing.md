# Direct typing — the phone's keyboard straight through

**Shipped 2026-09-09, row 17.** Tap `Keyboard: ON`, tap where the caret should go, type. Every
character reaches the PC's focused window as you type it. No `type…` field to fill, no Enter to
press to send — the phone's own Return key is Enter on the PC.

This is the third and last typing path in the project, and the only one that is a *stream*.
The other two stay exactly as they were: `/api/type` pastes a whole message through the
clipboard (`D-005`–`D-008`), `/api/key` presses named keys and combos.

## The two paths, and why they never merge

| | characters | named keys and combos |
|---|---|---|
| Mechanism | `SendInput` + `KEYEVENTF_UNICODE` (`wVk = 0`, UTF-16 unit in `wScan`) | `keybd_event` with virtual-key codes |
| Function | `type_unicode()` | `press_keys()` |
| Route | `POST /api/chars` | `POST /api/key` |
| Layout-proof | **by construction** — `VkKeyScanW` is never consulted | by table |
| Carries Enter, Tab, Escape | **never** — refused by name | yes |

A unicode key carries no virtual-key code, so a synthetic Ctrl cannot combine with one. That is
why there is no "type this string, with modifiers" helper anywhere: it cannot work, and writing
one is how the layout bug class `D-012` fixed would return. `D-025`.

Windows delivers a `KEYEVENTF_UNICODE` event as `VK_PACKET`; `TranslateMessage` turns it into
`WM_CHAR` carrying exactly that code unit. An astral character (emoji) is a surrogate **pair**
and both units ride one `SendInput` call — split across two calls, a target can see two lone
surrogates, which is a mangled character rather than a missing one.

## The client

**The sink** is `<input type="password">` in a `<form>`, 1 px and 1 % opacity, never
`display:none`. Password defeats the Android suggestion strip and iOS autocorrect, which
rewrites *already committed* words; focusable-but-invisible is what raises the keyboard at all.
`D-027`.

**The signal is `beforeinput`, not `keydown`.** While a soft keyboard composes, UI Events
*requires* `keyCode: 229` — on Android that is nearly every letter, so `keydown` cannot carry
the character. The `inputType` switch:

| `inputType` | what happens |
|---|---|
| `insertText` | the characters queue |
| `insertFromPaste` | the pasted text queues |
| `insertLineBreak` / `insertParagraph` | Enter, as a **named key** |
| `deleteContentBackward` | Backspace, as a named key |
| `deleteWordBackward` | `ctrl+backspace` |
| `insertCompositionText` | **ignored** — see below |

**Composition is taken at the edges only.** `insertCompositionText` is not cancelable and fires
repeatedly with intermediate guesses; the committed word appears atomically at
`compositionend`, and that is what is forwarded. The honest consequence, worth knowing before
you meet it: **a predicted word arrives when you accept it, not letter by letter.**

**The queue is ordered operations, not a string.** Type `ls`, press Enter, and an Enter that
overtakes a pending `ls` submits an empty prompt. Adjacent text merges, so a burst still leaves
in one request.

**Requests chain, never overlap** (`D-011`). The next one leaves when the previous completes,
which also *is* the batching: keystrokes arriving mid-flight merge into the next request, so a
slow link produces batches and a fast one produces single characters. `TYPE_BATCH_MS` is `0`
because a measured session showed a 70 ms window never coalescing anything. `D-028`.

**Keeping the keyboard up.** A tap on the screenshot places the caret and blurs the sink on the
way, so focus is taken back rather than surrendered — and the toggle stays the only way out, so
the button never claims a state the field does not have. When the keyboard rises it covers the
bottom of the screen, which is where you just tapped, so the last aimed point is remembered **as
a fraction of the image** (the frame is replaced constantly; a pixel would be stale next
refresh) and scrolled back into what `visualViewport` says is still visible. Telegram's
`viewportHeight` is *not* used — it does not reflect the keyboard on iOS.

## The route

```
POST /api/chars   {"text": "ls -la", "expect": "✳ Claude Code"}
  -> {"ok": true, "sent": 6, "window": "✳ Claude Code", "proc": "windowsterminal.exe"}
```

| Field | |
|---|---|
| `text` | required. Control characters are a `400` naming the code point; over `TYPE_CHARS_MAX` (512) is a `400` naming the cap |
| `expect` | optional **guard**. If the foreground is not that window, nothing is typed and the reply is `{"ok": false, "refused": "foreground", "window": "<the real one>", "sent": 0}` |
| `sent` | characters actually delivered. Fewer than asked means `SendInput` was refused mid-string and the rest was **not** pushed on top |

`expect` guards; it never focuses. A verified focus does not stay verified — measured going
stale 800 ms after the check — and focusing per batch would re-run that race at typing speed.
`D-026`.

The client sends no `expect` on its **first** batch, takes the `window` from the reply, and
guards every batch after it. So the target is whatever you tapped, and the moment something
else takes the foreground the stream stops with a toast instead of typing into it.

## Where it is

| | |
|---|---|
| Injector, refusals, the `INPUT` structs | `handlers/input.py` — `type_unicode()`, `_send_char()` |
| Route and the guard | `handlers/web.py` — `api_chars()` |
| Window identity | `utils/window.py` — `same_window_id()` |
| Cap | `config.py` — `TYPE_CHARS_MAX` |
| Client mode, sink, queue, pump | `web/index.html` — `toggleKbMode()`, `bindKbSink()`, `_kbPump()` |
| Toggle | `Keyboard: ON/OFF` on the live view, `⌨` in the zoomed viewer |

## What it cost to get right

- **`sizeof(INPUT)` must be 40 on x64.** A union of `KEYBDINPUT` alone is 32 and Windows
  rejects *every* call with error 87, silently sending nothing.
- **The first guard was inert against the only target that matters.** It compared `tail_key()`,
  which returns `''` for a single-segment title like `✳ Claude Code`, so two empties matched
  and everything passed.
- **The batch window never fired.** 70 ms of latency per character, buying nothing, until a
  device session was actually measured.

## Not done

- **A predicted Cyrillic word through composition has not been tested on the phone** (E6's
  second half). The desktop half passed with E2.
- **`e` + `U+0301` came back precomposed** in both E2 runs. It is a normalization, not a loss,
  and the suspect is the copy-paste path used to read the line back rather than the injector —
  `tools/experiments/e2_readback.py` settles it and has not been run.
