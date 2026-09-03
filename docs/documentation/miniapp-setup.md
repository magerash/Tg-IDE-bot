# Telegram Mini App Setup

Turn the web dashboard (`web/index.html`) into a Telegram Mini App opened via the bot's menu button.

## How It Works
- Bot already serves the dashboard on `http://localhost:8080` (aiohttp, same process).
- Telegram requires a public **HTTPS** URL → expose port 8080 via Cloudflare Tunnel.
- Set `WEBAPP_URL` in `.env` → on startup the bot sets a "Panel" menu button (MenuButtonWebApp).
- Inside Telegram, auth is automatic: the page sends `Telegram.WebApp.initData`, the server
  validates its HMAC signature (`utils/webauth.py`) and checks user id == `ALLOWED_USER_ID`.
  No token entry needed. Browser access still works with `WEB_TOKEN`.

## Resource Cost
Negligible. Static HTML + JSON API in the already-running bot process.
Heaviest call = screenshot (~200-300KB JPEG). No VPS required.

## Setup Steps

### 1. Install cloudflared
```powershell
winget install Cloudflare.cloudflared
```

### 2a. Quick tunnel (fastest, URL changes each run)
```powershell
.\start_tunnel.bat
# or: cloudflared tunnel --url http://localhost:8080
```
Copy the printed `https://<random>.trycloudflare.com` URL.

### 2b. Named tunnel (stable URL, needs free Cloudflare account + domain)
```powershell
cloudflared tunnel login
cloudflared tunnel create tg-ide-bot
cloudflared tunnel route dns tg-ide-bot bot.yourdomain.com
cloudflared tunnel run --url http://localhost:8080 tg-ide-bot
```

### 3. Configure bot
`.env`:
```
WEBAPP_URL=https://<your-tunnel-url>
```
Restart bot. Log should show `Mini App menu button set: ...`.

### 4. Open in Telegram
Bot chat → menu button (bottom-left, "Panel") → dashboard opens inside Telegram.

## Notes
- Quick tunnel URL changes every restart → update `WEBAPP_URL` + restart bot each time.
  Named tunnel avoids this.
- BotFather registration not required for menu-button web apps.
- `initData` older than 24h is rejected (`INIT_DATA_MAX_AGE`).

## Related
- `handlers/web.py` — API + `setup_menu_button()`
- `utils/webauth.py` — initData validation + token check
- `docs/chunks/features/web-dashboard.md`
