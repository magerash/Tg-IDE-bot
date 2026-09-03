# Telegram Mini Apps (Web Apps) Research

## 1. What Are Telegram Mini Apps?

Mini Apps are web applications displayed inside Telegram's WebView. They are standard web pages (HTML/CSS/JS) loaded from a URL you provide. Telegram does NOT host your app -- you must host it yourself and give Telegram the URL.

Internally, a Mini App is just a set of static files (.html, .css, .js) that Telegram loads in a WebView component.

### Requirements
- **HTTPS** with valid SSL certificate (mandatory for production)
- **Publicly accessible URL**
- HTTP allowed only in Telegram's test environment for local development

## 2. Ways to Launch a Mini App

| Method | sendData? | initData? | Server needed? | Notes |
|--------|-----------|-----------|----------------|-------|
| **Keyboard Button** | Yes (once, 4KB) | No | No | Simplest approach, closes app after send |
| **Inline Button** | No | Yes | Yes | Stays open, use fetch() to backend |
| **Menu Button** | No | Yes | Yes | Same as inline, configured via BotFather |
| **Main Mini App** | No | Yes | Yes | Profile button, direct links |
| **Direct Link** | No | Yes | Yes | `t.me/botname/appname?startapp=param` |
| **Inline Mode** | No | Yes | Yes | Via InlineQueryResultsButton |
| **Attachment Menu** | No | Yes | Yes | From any chat |

## 3. Communication: Mini App <-> Bot

### Method A: sendData (Keyboard Button only)
- `Telegram.WebApp.sendData(data)` sends up to 4096 bytes as a string
- Bot receives it as a service message via `filters.StatusUpdate.WEB_APP_DATA`
- **One-time only** -- app closes after calling sendData
- **No initData** available (no user info in the WebApp UI)
- **No external server needed**

### Method B: fetch() to your own backend (recommended for interactive apps)
- Mini App sends HTTP requests to your backend server
- Backend validates `initData` for authentication
- Backend calls Telegram Bot API (sendMessage etc.) as needed
- **App stays open**, unlimited requests
- Requires a running web server

### Method C: answerWebAppQuery (inline/menu button)
- Bot calls `answerWebAppQuery` with a `query_id` from `initData`
- Closes the Mini App
- Used for inline mode results

### Summary
```
Simplest (one-shot):    KeyboardButton + sendData → bot handler
Interactive (stays open): Any launch + fetch() → your backend → Bot API
```

## 4. python-telegram-bot v20+ Integration

### Official Example (webappbot.py)

```python
import json
from telegram import (
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    Update, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# Send keyboard with WebApp button
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Open the app:",
        reply_markup=ReplyKeyboardMarkup.from_button(
            KeyboardButton(
                text="Open Mini App",
                web_app=WebAppInfo(url="https://your-app-url.com"),
            )
        ),
    )

# Handle data sent from WebApp via sendData()
async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    await update.message.reply_text(f"Received: {data}")

def main():
    app = Application.builder().token("TOKEN").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
```

### Setting Menu Button Programmatically

```python
from telegram import MenuButtonWebApp, WebAppInfo

# In post_init or any handler:
await bot.set_chat_menu_button(
    chat_id=chat_id,  # or None for all chats
    menu_button=MenuButtonWebApp(
        text="Control Panel",
        web_app=WebAppInfo(url="https://your-app-url.com")
    )
)
```

### Key Imports
- `telegram.WebAppInfo` -- wraps the URL
- `telegram.KeyboardButton` with `web_app=` parameter
- `telegram.InlineKeyboardButton` with `web_app=` parameter
- `telegram.MenuButtonWebApp` -- for menu button
- `filters.StatusUpdate.WEB_APP_DATA` -- filter for sendData messages
- `update.effective_message.web_app_data.data` -- the received string

## 5. Hosting Options

### Free Static Hosting (simplest)
- **GitHub Pages** -- enable in repo Settings > Pages, get `https://username.github.io/repo/`
- **Netlify** -- drag-and-drop deploy, automatic HTTPS
- **Vercel** -- similar to Netlify

### For Backend (if using fetch() approach)
- The bot's own machine via a small HTTP server (Flask, aiohttp)
- ngrok for local development tunneling
- Railway, Render, Fly.io for deployment

## 6. BotFather Configuration

### Set Menu Button (static for all users)
1. Open @BotFather
2. `/setmenubutton`
3. Select your bot
4. Enter the Mini App URL
5. Enter button text (e.g. "Open App")

### Configure Mini App (for direct links)
1. `/mybots` > select bot > **Bot Settings** > **Configure Mini App** > **Enable Mini App**
2. Send your app URL
3. Direct link becomes: `t.me/yourbotname/appname`

### Alternative: Programmatic (per-user customization)
Use `setChatMenuButton` in Bot API (see Python code above).

## 7. Minimal HTML Template for a Mini App

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Control</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0; padding: 16px;
            background: var(--tg-theme-bg-color, #fff);
            color: var(--tg-theme-text-color, #000);
        }
        button {
            display: block; width: 100%;
            padding: 12px; margin: 8px 0;
            border: none; border-radius: 8px;
            background: var(--tg-theme-button-color, #3390ec);
            color: var(--tg-theme-button-text-color, #fff);
            font-size: 16px; cursor: pointer;
        }
    </style>
</head>
<body>
    <h3>Remote Control</h3>
    <button onclick="send('screen')">Screenshot</button>
    <button onclick="send('status')">Status</button>

    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        function send(command) {
            // Option A: sendData (one-shot, closes app)
            tg.sendData(JSON.stringify({ cmd: command }));

            // Option B: fetch to backend (keeps app open)
            // fetch('https://your-server/api/command', {
            //     method: 'POST',
            //     headers: {'Content-Type': 'application/json'},
            //     body: JSON.stringify({ cmd: command, initData: tg.initData })
            // });
        }
    </script>
</body>
</html>
```

## 8. Theming

CSS variables auto-injected by Telegram:
- `--tg-theme-bg-color`
- `--tg-theme-text-color`
- `--tg-theme-hint-color`
- `--tg-theme-link-color`
- `--tg-theme-button-color`
- `--tg-theme-button-text-color`
- `--tg-theme-secondary-bg-color`

JS access: `Telegram.WebApp.themeParams.bg_color` etc.
Event: `Telegram.WebApp.onEvent('themeChanged', callback)`

## 9. Architecture Choices for Our Bot

### Option A: Simplest (sendData via Keyboard Button)
- Host static HTML on GitHub Pages
- User presses keyboard button -> WebApp opens
- User taps a command button -> sendData sends JSON -> app closes
- Bot handler receives web_app_data, executes command, replies in chat
- **Pros**: No server needed, no auth complexity
- **Cons**: App closes after each action (user must reopen)

### Option B: Interactive (fetch to bot's HTTP endpoint)
- Run a small HTTP server alongside the bot (e.g., aiohttp)
- WebApp stays open, sends commands via fetch()
- Server validates initData, executes commands, returns results
- **Pros**: App stays open, full interactivity
- **Cons**: Need HTTPS endpoint, more code, auth validation

### Recommendation for MVP
Start with **Option A** (sendData + keyboard button) for simplicity. It requires zero additional infrastructure -- just a static HTML file on GitHub Pages. Upgrade to Option B later if persistent UI is needed.

## Sources
- https://core.telegram.org/bots/webapps
- https://docs.telegram-mini-apps.com/platform/about
- https://docs.python-telegram-bot.org/en/stable/examples.webappbot.html
- https://github.com/telegram-mini-apps-dev/vanilla-js-boilerplate
- https://github.com/revenkroz/telegram-web-app-bot-example
