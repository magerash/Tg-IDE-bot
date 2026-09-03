# File attachments — send a file, type its PATH

## Quick Reference
| Thing | Where |
|-------|-------|
| Save + name sanitising + path token | `utils/uploads.py` |
| Web endpoint | `POST /api/upload` — `handlers/web_extra.py:api_upload` |
| Telegram entry | `handlers/upload.py` (`document_handler` / `document_callback`) |
| Registration | `bot.py` — `filters.Document.ALL`, `CallbackQueryHandler(pattern="^f:")` |
| Mini App | `web/index.html` — `#attach-btn`, `#file-input`, `addFileAttachment`, `uploadFile`, `doType` |
| Config | `config.py` — `UPLOAD_DIR` (default `%TEMP%\tgbot_upload`), `UPLOAD_MAX_MB` (25) |
| Tests | `tests/test_web.py` — 6 tests under "file attachments" |

## Why a path and not the text
A markdown file used to be pasted into the Type field as **text**. The client cut it
into `TEXT_BLOCK_CHARS`/`TEXT_BLOCK_LINES` block chips and the whole thing went to the
terminal through the clipboard: slow, fighting bracketed paste (v0.17.0), and a long
file risks arriving truncated.

A terminal cannot receive a pasted document — but **Claude Code reads a file whose
path appears in the prompt**. So the file is saved on the PC and only its path is
typed. Arrives whole, instantly, at any size. Exactly the trick images already use
(`/api/paste`, v0.16.0); this generalises it and the two now share one helper.

## Rules that must not be undone
- **`safe_name()` is not cosmetic.** The name comes from a phone inside an HTTP
  header — `..\..\autoexec.bat` must land as `autoexec.bat`. `basename` + strip
  `\ / : * ? " < > |` and control chars + strip leading/trailing dots and spaces
  (a leading dot hides the file, a trailing one is dropped by Windows on create)
  + cap 120 chars keeping the extension. Empty → `file_<ms>`.
- **Never overwrite.** The same `report.md` twice is two files; the first may already
  be open in the session that asked for it. The suffix goes *before* the extension.
- **`path_token()` lives in one place.** Quotes only when the path holds a space (an
  unquoted one splits into two arguments) and always ends with a space so the user's
  text does not fuse onto the file name. `api_paste` and `api_upload` both call it —
  `test_path_token_lives_in_one_place` fails if a second copy appears.
- **`/api/upload` uses plain `_check_auth`.** Typing into a focused window is remote
  control, which the refine-scoped token exists to be denied.
- **Raw body, name in a header.** `api()` speaks JSON, so a binary needs its own
  `fetch` anyway (`/api/stt` proved the shape). `X-Filename` is URL-encoded — a raw
  UTF-8 header value arrives mangled. `X-Type-Path: 0` saves without typing.
- **Order in `doType()`: files → images → text.** Both attachment kinds type a path
  with **no Enter**, and the text write reuses the clipboard, so text goes last with
  `IMG_INGEST_MS` (700ms) between writes — without the gap the next write eats the
  path that has not landed yet.
- **One `<input type="file">` for the whole page.** The panel 📎 collects chips; the
  viewer 📎 (`pickFiles(true)`) uploads immediately, because an overlay is no place
  for an attachment list. Two inputs would mean two change handlers.

## Limits
| Path | Cap | Whose |
|------|-----|-------|
| Mini App upload | `UPLOAD_MAX_MB` 25MB → HTTP 413 | ours (`create_web_app` allows 30MB of body) |
| Telegram document | 20MB | **Telegram's** Bot API download limit — not ours to raise; the handler says so and points at the Mini App |

## Entry points
1. **Mini App** — 📎 in the Type panel (chip: `📎 report.md · 12KB ×`, sends on Type),
   drag & drop onto the Type field (`#type-input.drop-on` highlight), a file copied in
   the OS file manager pasted into the field, and 📎 in the zoomed viewer's key row.
2. **Telegram** — send the document to the bot: it saves it and answers with the path
   plus **⌨ Type / ⌨ Type+Enter / 🤖 Claude**. Typing goes through `type_and_enter`,
   the single place paste and Enter are sequenced (v0.17.0) — a local Enter would land
   inside the paste as a newline.

Related: `web-dashboard.md` (image paste, Type panel), `../../documentation/`.
