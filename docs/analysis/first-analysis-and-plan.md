### PLAN
Good analysis. Let me synthesize this into a concrete development plan.

## The Plan: Hybrid TG Remote Control Bot

Based on the analysis, I recommend **Solution 1 (Visual/Screenshot) as the primary approach** with elements of Solution 2 (tmux text capture) as a fallback. Here's why: you're on a PC with an IDE — screenshot-based control is OS-agnostic, works with any window, and handles Claude Code's TUI without parsing escape codes.

---

### Phase 1 — Core Bot Skeleton

**Goal:** Bot runs on PC, responds only to you, has basic command routing.

**Tasks:**
- Create Python project with `python-telegram-bot`, `mss`, `pyautogui`
- Set up bot token + hardcoded `ALLOWED_USER_ID` auth guard
- Command router: `/screen`, `/apk`, `/type`, plain text → keystrokes
- Error handling + logging to a local file

**Deliverable:** Bot starts, authenticates you, echoes commands back

---

### Phase 2 — Screen Capture & Input

**Goal:** See your PC, type into it remotely.

**Tasks:**
- `/screen` — full monitor screenshot → sent as compressed photo
- `/window` — capture only the active window (or a named window like "Terminal")
- Plain text messages → `pyautogui.write()` + Enter
- `/key <key>` — special keys: `/key y`, `/key ctrl+c`, `/key up`, `/key tab`
- `/click x y` — emergency mouse click if needed
- Add a short delay between typing and auto-screenshot so you see the result

**Gotcha mitigation:**
- Add a `/focus <window_title>` command that brings a specific window to front before typing (using `pygetwindow` on Windows)
- This prevents the "typing into wrong window" problem

---

### Phase 3 — APK Delivery

**Goal:** Build and receive APK on your phone.

**Tasks:**
- `/build` — runs `gradlew assembleDebug` as subprocess, streams status
- `/apk` — finds latest `.apk` in build output folder, sends as document
- Optional: file watcher (`watchdog` library) that auto-sends new APKs to TG when they appear
- Support sending any file: `/file <path>`

---

### Phase 4 — Smart Features

**Goal:** Make it comfortable for daily use.

**Tasks:**      
- **Auto-screenshot after typing** — every time you send text, bot types it, waits 2-3 seconds, sends a screenshot back automatically (no need to manually `/screen` each time)
- **Crop mode** — define a screen region for your terminal so screenshots are smaller and faster
- `/sh <command>` — run a shell command directly (bypassing the IDE), return stdout as text
- `/claude <prompt>` — shortcut that runs `claude -p --continue "<prompt>"` and returns text output (for simple queries that don't need the TUI)
- Message chunking for long text responses (split at 4096 char TG limit)

---

### Phase 5 — Reliability & Polish

**Tasks:**
- Run bot as a background service (systemd on Linux, Task Scheduler on Windows, or just `tmux`/`screen`)
- Auto-restart on crash
- `/status` — report uptime, current directory, last command
- `/help` — list all commands
- Rate limiting to prevent accidental spam

---

### Project Structure

```
tg-remote-bot/
├── bot.py              # Entry point, command routing
├── config.py           # Token, user ID, paths, screen regions
├── handlers/
│   ├── screen.py       # Screenshot capture & send
│   ├── input.py        # Keyboard/mouse simulation
│   ├── files.py        # APK finder, file sender, watcher
│   ├── shell.py        # Direct shell command execution
│   └── claude.py       # claude -p wrapper
├── utils/
│   ├── auth.py         # User ID check decorator
│   ├── chunks.py       # Message splitting for TG limits
│   └── window.py       # Window focus management
├── requirements.txt
└── README.md
```

---

### Tech Stack

| Component | Library |
|---|---|
| Telegram bot | `python-telegram-bot` v20+ |
| Screenshots | `mss` (fast, cross-platform) |
| Keyboard sim | `pyautogui` |
| Window focus | `pygetwindow` (Windows) |
| File watching | `watchdog` |
| Claude CLI | `subprocess` → `claude -p` |

---

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| Wrong window gets focus | `/focus` command + always refocus before typing |
| Long Claude responses | Send as `.txt` file if > 4000 chars |
| Bot crashes overnight | Systemd/Task Scheduler auto-restart |
| Security (someone finds bot) | `ALLOWED_USER_ID` check on every handler |
| TG rate limits | Max 1 screenshot per 2 seconds |
| pyautogui fails on lock screen | Keep PC unlocked (use caffeine tool) or wake via `/wake` command |

---

A few questions before I start building:

What's your setup — are you on Windows, Linux, or Mac? And do you want me to start coding Phase 1+2 right now so you have a working prototype today?

### BASE - this analysis

Reed this analisys to make a plan
This is a creative and complex automation challenge. You are trying to bridge an **interactive Terminal User Interface (TUI)** (Claude Code) with a **chat interface** (Telegram).

The main problem, as you correctly guessed, is interactivity. Standard Telegram shell bots wait for a command to *finish* before sending the output. Claude Code runs continuously, asks questions, and updates the screen dynamically.

Here are the three best ways to solve this, ranked from "Easiest/Dirtiest" to "Most Robust."

### Solution 1: The "Visual" Bot (Best for Windows/Mac)

This approach treats your IDE terminal like a video game. The bot takes a screenshot of the terminal, sends it to you, and types your text commands using keyboard simulation.

* **Pros:** Works with *any* application (IDE, Emulator, etc.). No complex terminal parsing.
* **Cons:** Higher data usage (sending images), slightly slower.
* **Tools:** Python, `pyautogui` (for typing), `MSS` (for fast screenshots), `python-telegram-bot`.

**How it works:**

1. **Reading:** You send command `/status`. The bot grabs a screenshot of your screen (or just the IDE window) and sends the photo to Telegram.
2. **Writing:** You send a text message. The bot uses `pyautogui.write()` to simulate typing that text into the active window on your PC.
3. **Files:** You type `/getapk`. The bot looks in your specified "Build" folder and uploads the latest `.apk` file to the chat.

### Solution 2: The "Tmux" Bridge (Best for Linux/WSL/Mac)

If you are comfortable with command lines, this is the most professional way. You run Claude Code inside a session manager called `tmux`.

* **Pros:** Text-based (faster), very reliable, keeps history.
* **Cons:** Requires `tmux` (native on Linux/Mac, requires WSL on Windows).
* **Tools:** `tmux`, Python `subprocess` module.

**The Workflow:**

1. **Start:** You open a terminal and run `tmux new -s claude`. Inside that session, you start Claude Code.
2. **The Bot Script:** A separate Python script runs in the background.
* **To Read:** It runs `tmux capture-pane -p -t claude` to get the current text on the screen and sends it to you.
* **To Write:** When you send a message, it executes `tmux send-keys -t claude "your message" Enter`.



### Solution 3: The "Telegram Shell" (Simplest, but limited)

There are existing open-source projects for this, but they struggle with *interactive* apps like Claude Code.

* **Recommendation:** Check out **"Shell2Telegram"**. It's a popular tool. However, it will likely fail when Claude asks "Do you want to proceed? (Y/N)" because it expects the process to exit to capture output.

---

### Recommended Architecture: The "Hybrid" Python Bot

I suggest building a custom Python bot using **Solution 1 (Visual/Input)** because it's the most flexible for your workflow (handling IDEs, emulators, and file transfers).

Here is a blueprint of the code structure:

```python
import os
import glob
import pyautogui
import mss
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ALLOWED_USER_ID = 123456789 # VITAL: Only allow YOUR ID to control this!
APK_FOLDER = r"C:\Users\You\Project\build\outputs\apk\debug"

async def check_auth(update: Update):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Unauthorized access.") 1
        return False
    return True

# 1. READ: Take a screenshot of the PC to see what Claude is saying
async def screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    with mss.mss() as sct:
        # Capture the primary monitor (or define specific coordinates for your IDE)
        filename = sct.shot(mon=-1, output='monitor.png') 
        await update.message.reply_photo(photo=open(filename, 'rb'))

# 2. WRITE: Send commands to the active window
async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    text_to_type = update.message.text
    # Simulate typing
    pyautogui.write(text_to_type, interval=0.01)
    pyautogui.press('enter')
    
    await update.message.reply_text(f"⌨️ Typed: {text_to_type}")

# 3. FILES: Find and send the latest APK
async def send_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    # Find the newest APK in the folder
    list_of_files = glob.glob(os.path.join(APK_FOLDER, '*.apk'))
    if not list_of_files:
        await update.message.reply_text("❌ No APK found.")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    await update.message.reply_text(f"📤 Uploading: {os.path.basename(latest_file)}...")
    
    with open(latest_file, 'rb') as f:
        await update.message.reply_document(document=f)

# --- SETUP ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("screen", screen)) # Type /screen to see PC
    app.add_handler(CommandHandler("apk", send_apk))  # Type /apk to get file
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), type_command)) # All other text is typed into PC
    
    print("Bot is running...")
    app.run_polling()

```

### Critical "Gotchas" to Watch Out For

1. **Focus:** For `pyautogui` to work, **the IDE window must be active (in focus)** on your PC. If a Windows update pop-up steals focus, you'll be typing commands into the update window.
2. **Security:** **DO NOT** skip the `ALLOWED_USER_ID` check. Without it, anyone on Telegram can find your bot and take control of your computer.
3. **Looping:** If you use the bot to send a message like "compile," wait a few seconds, then send `/screen` to check the progress. Don't expect real-time streaming text (Telegram API limits prevent streaming updates fast enough for a terminal).

Would you like me to refine the "File Finding" logic to match your specific Android project structure?