# Remote Desktop Streaming — Research & Two-Mode Architecture

**Date:** 2026-07-26
**Scope:** How TeamViewer / AnyDesk / RustDesk actually move pixels + input, and how to apply it to this bot.
**Question asked:** *do they stream video, or send pictures like we do?* — and what a "flexible mode" (right-click, drag, scroll) would take.

---

## 0. TL;DR

| | Answer |
|---|---|
| Do they send pictures? | **No.** All three run a **continuous encoded video stream** (inter-frame, delta-coded), not independent full images. |
| Is it plain H.264/video? | Mostly, but **screen-tuned**. AnyDesk = own codec (DeskRT). RustDesk = VP8/VP9/AV1/H264/H265 with HW encode. TeamViewer = proprietary bitmap-delta protocol + mixed-mode codecs. |
| Do we need video for right-click? | **No.** Right-click / drag / scroll is an **input-layer** problem, totally independent of transport. Cheap to add to what we have today. |
| So what does video buy us? | Latency (16–60 ms vs our 1–10 s), fps (30–60 vs 0.1–1), and **10–20× less bandwidth** for the same visual quality. |
| Recommendation | **Mode A (Snapshot)** stays default + gains full input. **Mode B (Live)** = MJPEG/WebSocket delta-tile stream, opt-in. **Mode C (WebRTC)** only if we accept a TURN server. |

---

## 1. How the big three work

### 1.1 Common architecture (all three)

```
[capture]  →  [dirty-region detect]  →  [encode]  →  [transport]  →  [decode]  →  [render]
   ↑                                                     ↓
[input inject] ← ─ ─ ─ ─ ─  input events (mouse/key/scroll)  ─ ─ ─ ─ ─ ┘
```

Two **separate** channels:
- **Video channel** — one-way, PC → viewer, lossy, drop-tolerant.
- **Input channel** — two-way, tiny, must be lossless + ordered (mouse move, button down/up, wheel, key down/up, modifiers).

Key insight: they are decoupled. Our bot currently has a weak video channel *and* a weak input channel, and they can be upgraded independently.

### 1.2 Capture layer

| Product | Windows capture API |
|---|---|
| RustDesk | **DXGI Desktop Duplication** (`libs/scrap`, `TraitCapturer`), Wayland/X11 on Linux, Quartz on macOS |
| AnyDesk | DXGI + mirror driver fallback |
| TeamViewer | DXGI + own mirror driver (historically) |
| **This bot** | `mss` (GDI BitBlt) — ~75 fps ceiling, no dirty-region info |

Desktop Duplication API is the important one: it returns **only the changed regions** plus a move-rect list, and hands frames as GPU textures — so the encoder never has to touch a full RGB buffer over PCIe. Python equivalent: `dxcam` / `BetterCam` (**~239 fps vs mss ~76 fps** on 1080p in the published benchmark).

### 1.3 Encoding layer — this is the real answer to "video or picture?"

**RustDesk** — negotiated codec per session, from `Encoder::update` aggregating peer capabilities:
- Software: VP8, VP9 (libvpx), AV1 (libaom)
- Hardware **HWRAM**: FFmpeg HW encoders, system-memory buffers
- Hardware **VRAM**: NVENC / AMF encoding straight from GPU texture, no CPU copy — falls back to software if frames degrade
- Frames converted to YUV before encode; **AV1 is current auto-priority**

**AnyDesk** — **DeskRT**, proprietary codec built specifically for *screen content* (text, UI edges, flat regions), not camera video. Claimed <16 ms latency on LAN, 60 fps, usable down to **~100 kbit/s**.

**TeamViewer** — proprietary protocol transmitting **bitmap updates** (delta blocks), i.e. closer to a smart VNC than to a video stream, with mixed-mode content classification: text/UI regions and photo/video regions get different codecs and different fidelity. Same idea appears in Microsoft's RDP graphics pipeline (RemoteFX / AVC444 mixed-mode encoding).

So the honest three-way distinction:

| Approach | What is sent | Examples |
|---|---|---|
| **Full-frame snapshots** | Whole screen, independently compressed, every time | **us today**, naive screenshot bots |
| **Bitmap deltas / tiles** | Only changed rectangles, per-tile codec | VNC, RDP, TeamViewer |
| **Inter-frame video** | Motion-compensated P-frames over a GOP | RustDesk (VP9/AV1/H264), AnyDesk DeskRT, RDP AVC444 |

Bandwidth for a 1080p IDE screen, rough but real:

| Mode | Per second | Notes |
|---|---|---|
| Ours: full JPEG q70 @1 fps | **~250–400 KB/s (2–3 Mbit/s)** | and it still *looks* like 1 fps |
| Ours: full JPEG q70 @3 s interval | ~100 KB/s | current default feel |
| Delta tiles, typing in an editor | **~5–30 KB/s** | only the caret line changes |
| H.264/VP9 @30 fps desktop content | **~40–200 KB/s** | idle screen ≈ near zero |

**Punchline:** a real video/delta stream is not only smoother, it is *cheaper* than what we send now. Full-frame JPEG is the worst point on the curve — we pay a full-screen price for every frame even when 200 px of text changed.

### 1.4 Flow control (the part people forget)

RustDesk's `VideoFrameController` is **ack-based**: send frame → record connection ids → block in `try_wait_next` until the client signals `notify_video_frame_fetched` → capture next. Plus `VideoQoS` dynamically retunes seconds-per-frame and calls `set_quality` to change bitrate mid-session.

Without this you get the classic aiortc failure mode: producer outruns consumer, latency grows monotonically **4 s → 30 s** over a session. Any live mode we build **must** be pull/ack-driven, never a free-running push loop. Our current polling design accidentally already has this property (client asks, server answers) — keep it.

### 1.5 Input layer & mobile gestures

What they actually inject (and we don't):

- mouse **move** (absolute + relative), left/right/middle **down**/**up** as separate events
- **wheel** vertical + horizontal, with delta
- **drag** = down → move* → up (needs button state held across events)
- key **down**/**up** separately + modifier state (so Ctrl+drag, Shift+click work)
- multi-monitor coordinate mapping

Mobile gesture mapping, as shipped:

| Gesture | AnyDesk | RustDesk |
|---|---|---|
| tap | left click | left click |
| **long press** | **right click** | right click |
| two-finger tap | — | right click (touchpad mode) |
| double-tap-hold-and-move | drag | drag |
| two/three-finger swipe | scroll | scroll (3-finger conflicts with Android system gestures — known bug) |
| pinch | zoom viewport (local, not remote) | zoom viewport |

RustDesk offers two mobile modes: **Touch mode** (tap = click at that point) and **Mouse/touchpad mode** (finger moves a virtual cursor). 1.4.3 added a virtual joystick + virtual scroll buttons because gestures alone are unreliable. Lesson: **give explicit UI buttons as an escape hatch**, don't bet everything on gestures.

---

## 2. Where our bot stands

| Layer | Current implementation | File |
|---|---|---|
| Capture | `mss` full monitor or window rect → PIL → **JPEG q70** | `handlers/screen.py:17` `_grab_to_jpeg` |
| Transport | base64 JPEG inside JSON, HTTP POST `/api/screen`, client polls at 1–10 s | `handlers/web.py:49` |
| Input — click | `pyautogui.click` / `doubleClick`, x/y only | `handlers/web.py:135` `api_click` |
| Input — keys | `pyautogui.press` / `hotkey`, +repeat +interval | `handlers/web.py:83` `api_key` |
| Input — text | clipboard paste via Win32 | `handlers/input.py` `_type_text` |
| Missing | right/middle click, drag, wheel, mouse move, key down/up, modifier hold | — |
| Network path | reverse SSH `-R 18080:127.0.0.1:8080` to VPS, **TCP only** | `start_tunnel_vps.ps1` |

**The right-click complaint is not a video problem.** `pyautogui.rightClick(x, y)` is one line. We simply never exposed it. Same for `scroll`, `mouseDown`/`mouseUp`, `dragTo`.

---

## 3. Transport options, scored for *our* constraints

Constraints that actually bind us: Python/aiohttp server, phone browser or Telegram Mini App webview client, **TCP-only reverse-SSH tunnel**, single user, "minimalistic and compact" design rule.

| Option | Latency | Bandwidth | Browser support | Works over our SSH tunnel | Python effort |
|---|---|---|---|---|---|
| **A. Poll JPEG (today)** | 1–10 s | worst | universal | ✅ | 0 — done |
| **B1. MJPEG** `multipart/x-mixed-replace` | 0.2–1 s | poor-ish (still full frames, no base64 +33%) | `<img src>` — universal, zero JS | ✅ | **~1 day** |
| **B2. WebSocket + JPEG delta tiles** | 0.1–0.5 s | **good** (5–30 KB/s typing) | universal (WS) | ✅ | ~3–5 days |
| **C. WebRTC** (`aiortc`, VP8/H264) | **0.05–0.2 s** | best | universal-ish; iOS webview quirks | ❌ **needs TURN/UDP** | ~1–2 weeks + coturn on VPS |
| **D. noVNC + TightVNC/UltraVNC** | 0.1–0.3 s | good | universal | ✅ (websockify over the same tunnel) | ~2 days *integration*, but 3rd-party service on the PC |
| **E. Embed RustDesk** | best | best | needs their client/relay | ✗ own infra | out of scope |

Notes:
- **B1 MJPEG** is the biggest quality jump per unit of work. `<img src="/api/stream">` and the browser does the rest — no decoder, no JS state machine, survives the tunnel, works in the Telegram webview. It also drops the base64 +33% overhead we pay today.
- **B2 delta tiles** is where the real bandwidth win lives, and it's the same idea TeamViewer/VNC use. Split the frame into a grid (e.g. 128×128), hash each tile, send only changed tiles as small JPEGs over one WebSocket. For an IDE screen this is *dramatically* cheaper than full frames. This is the sweet spot for "flexible but still ours".
- **C WebRTC** is technically the right answer and practically the expensive one: our media would have to traverse ICE, and the reverse-SSH tunnel carries TCP only. That means running **coturn on the VPS with TURN-over-TCP/TLS**, so all media relays through the VPS anyway — losing WebRTC's main advantage while keeping its complexity. Also `aiortc` needs the ack/backpressure discipline from §1.4 or latency creeps to 30 s.
- **D noVNC** gets us a *complete* remote-desktop experience (right-click, drag, scroll, clipboard, multi-monitor) for almost no code — but violates the project's self-contained spirit and adds a VNC server + password surface on the PC. Worth keeping as a documented "power user" escape hatch, not as the product.

---

## 4. Proposed architecture: two modes

### Mode A — **Snapshot** (default, keep + fix)

Philosophy: *one screenshot, deliberate actions, works anywhere, costs nothing when idle.*

Stays exactly as-is for transport. What it gains:

1. **Full mouse verb set** — extend `POST /api/click`:
   ```json
   { "x": 900, "y": 400, "button": "right|left|middle",
     "action": "click|double|down|up|move",
     "modifiers": ["ctrl","shift"] }
   ```
   plus `POST /api/scroll {"x","y","dy","dx"}` and `POST /api/drag {"x1","y1","x2","y2","button"}`.
2. **Click-mode selector in the web UI** — small segmented control next to the existing Click toggle: `L · R · M · 2× · Drag · Scroll`. Tap on the screenshot performs the selected verb. Drag = two taps (start, end). Scroll = tap + ▲▼ buttons.
3. **Key down/up** endpoints so Ctrl/Shift/Alt can be *held* across a click.
4. **Auto-refresh after every input** (already partially there) — so the snapshot reflects the result.

Cost: ~1 day. Removes 90% of the "I can't do anything" pain **without touching the transport at all**.

### Mode B — **Live** (opt-in, new)

Philosophy: *continuous view + continuous input, for when you actually need to drive the machine.*

Staged so each stage ships value on its own:

**B1 — MJPEG stream** (ship first)
- `GET /api/stream?fps=&quality=&mode=screen|window` → `multipart/x-mixed-replace; boundary=frame`
- Server loop: `dxcam` (fallback `mss`) → JPEG → yield. Adaptive: if the client's TCP buffer backs up, drop fps (the ack discipline of §1.4, TCP-flavoured).
- Client: `<img id="live">` swapped in over the existing screenshot `<img>`; the whole existing click-mapping code (`rect` scaling) keeps working unchanged.
- Auto-stop after N minutes idle, hard cap on concurrent streams (single-user bot).

**B2 — delta tiles over WebSocket** (upgrade, same UI)
- `WS /api/live` — server sends `{seq, tiles:[{x,y,w,h,jpeg_b64}]}`, client blits onto a `<canvas>`.
- Tile hash (xxhash of raw bytes) per 128×128 cell; skip unchanged. Periodic keyframe (all tiles) every N seconds or on client request for resync.
- Same socket carries **input events upstream** — mouse move/down/up/wheel, key down/up — so drag and hover become real and continuous, and every input already has a socket to travel on.
- Client-side gesture map (from §1.5): tap = left, **long-press = right**, two-finger tap = right, double-tap-hold-move = drag, two-finger swipe = wheel, pinch = local zoom only. Plus explicit on-screen buttons as escape hatch.

**B3 — WebRTC** (only if B2 proves insufficient)
- `aiortc` + VP8/H.264, signalling over the existing HTTPS endpoints, **coturn on the VPS** with TURN/TCP:443.
- Strict ack/backpressure or latency drifts.
- Honest verdict: **do not start here.** B2 gets ~80% of the benefit at ~25% of the cost and zero new infrastructure.

### Mode switch

One control in the Screen panel: `Snapshot · Live`. Snapshot stays the default (cheap, tunnel-friendly, mobile-data-friendly). Live is explicit, shows a bandwidth/fps readout, and auto-drops back to Snapshot on error or idle timeout.

---

## 5. Recommended sequence

| Step | Work | Why first |
|---|---|---|
| 1 | **Mode A input verbs** — right/middle click, drag, scroll, key down/up + UI verb selector | Solves the stated pain. ~1 day. No transport risk. |
| 2 | **`dxcam` capture backend** behind a config flag, `mss` fallback | 3× faster capture, prerequisite for any live mode, invisible to everything else |
| 3 | **B1 MJPEG** + Snapshot/Live toggle | Huge perceived win, tiny code, works in Telegram webview and over the SSH tunnel |
| 4 | **B2 WebSocket delta tiles + upstream input events + mobile gestures** | Real bandwidth win + continuous drag/hover; this is our "TeamViewer-lite" |
| 5 | *(optional)* document **noVNC** as a power-user escape hatch | Full fidelity when someone really needs it, zero maintenance from us |
| 6 | *(only if needed)* **WebRTC + coturn** | Highest cost, needs VPS infra, marginal gain over B2 for an IDE screen |

## 6. Risks

| Risk | Mitigation |
|---|---|
| Live stream saturates mobile data | fps/quality caps, bandwidth readout, idle auto-stop, Snapshot default |
| Latency creep (aiortc-style 4 s → 30 s) | pull/ack driven loop, never free-running push; drop frames not queue them |
| SSH tunnel is TCP-only | B1/B2 are TCP-native by design; WebRTC deferred precisely for this |
| `dxcam` on RDP sessions / no-GPU / locked screen | keep `mss` fallback, feature-detect at startup |
| Continuous capture CPU burn | dirty-tile skip means idle screen ≈ idle CPU; hard fps ceiling |
| Right-click injected into wrong window | reuse existing focus chain (`utils/winfocus.py`) before injection |
| Security: continuous screen stream over tunnel | same `WEB_TOKEN` auth on stream + WS endpoints, no exceptions (project rule) |

---

## Sources

- [RustDesk — Video Capture and Encoding (DeepWiki)](https://deepwiki.com/rustdesk/rustdesk/5.1-video-capture-and-encoding)
- [rustdesk/libs/scrap/src/common/codec.rs](https://github.com/rustdesk/rustdesk/blob/master/libs/scrap/src/common/codec.rs)
- [rustdesk-org/hwcodec — Getting Started](https://deepwiki.com/rustdesk-org/hwcodec/2-getting-started)
- [RustDesk — Mobile UI Adaptations](https://deepwiki.com/rustdesk/rustdesk/4.1.9-mobile-ui-adaptations)
- [RustDesk 1.4.3 — virtual mouse / joystick](https://ubuntuhandbook.org/index.php/2025/10/rustdesk-released-1-4-3-with-multi-monitor-for-wayland-virtual-mouse/)
- [RustDesk issue #3744 — touchpad gestures, zoom, scrolling](https://github.com/rustdesk/rustdesk/issues/3744)
- [AnyDesk — Performance / DeskRT](https://anydesk.com/en/performance)
- [How to Right Click in AnyDesk on PC or Mobile](https://www.alphr.com/anydesk-right-click/)
- [Microsoft — Graphics encoding over RDP (mixed-mode, AVC444)](https://learn.microsoft.com/en-us/azure/virtual-desktop/graphics-encoding)
- [MS-RDPNSC — RDP NSCodec specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpnsc/a2e57e6f-879f-4084-91a6-56dfac4fa2ea)
- [Wikipedia — DirectX Graphics Infrastructure / Desktop Duplication](https://en.wikipedia.org/wiki/DirectX_Graphics_Infrastructure)
- [DXcam — high-performance Windows screen capture](https://github.com/ra1nty/DXcam)
- [Python fast screen capture benchmark (DXcam 238 fps vs mss 76 fps)](https://kylefu.me/2023/02/18/python-fast-screen-capture.html)
- [aiortc issue #1192 — WebRTC delay building up over time](https://github.com/aiortc/aiortc/issues/1192)
- [aiortc discussion #1238 — backpressure / frame queue handling](https://github.com/aiortc/aiortc/discussions/1238)
- [WebRTC vs WebSocket comparison](https://ably.com/topic/webrtc-vs-websocket)
- [noVNC browser-based VNC guide](https://ecmiss.co.uk/novnc-the-ultimate-guide-to-browser-based-vnc-remote-access/)
