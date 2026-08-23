import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
VERSION = "0.19.0"

# Web dashboard / Mini App
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WEB_TOKEN = os.getenv("WEB_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # public HTTPS URL for Telegram Mini App

# Projects
PROJECTS_ROOT = os.getenv("PROJECTS_ROOT", r"C:\Projects")

# Speech-to-text (Groq Whisper — free key at console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

# Transcript cleanup (same Groq key).
# Groq retires models without notice — `llama-3.3-70b-versatile` started answering
# 404 on 2026-08-17 mid-day and the whole Llama family vanished from the key, so
# every voice message silently fell back to the raw transcript. Hence a fallback
# chain: the first model that answers wins, and the switch is logged.
HUMANIZE_MODEL = os.getenv("HUMANIZE_MODEL", "qwen/qwen3.6-27b")
HUMANIZE_FALLBACKS = [
    m.strip() for m in os.getenv("HUMANIZE_FALLBACKS", "openai/gpt-oss-20b").split(",")
    if m.strip()
]
# Reasoning models otherwise dump their whole chain of thought into `content`
# (qwen3.6 returned 7196 chars of "<think>…" for a 483-char transcript, which then
# gets pasted straight into Claude Code). "none" for qwen, "low" for gpt-oss.
HUMANIZE_REASONING = os.getenv("HUMANIZE_REASONING", "none")
HUMANIZE_DEFAULT = os.getenv("HUMANIZE_DEFAULT", "1") == "1"
# HAE twin profile (persona.md + principles.md) — injected into "Improve text"
# prompts when the Twin toggle is on. Missing dir = twin unavailable, not an error.
HAE_PROFILE_DIR = os.getenv(
    "HAE_PROFILE_DIR",
    os.path.join(os.path.expanduser("~"), ".hae", "profile"),
)

# Claude Code metrics (live model/effort/context + 5h/weekly limits)
_CC_HOME = os.path.join(os.path.expanduser("~"), ".claude")
CC_USAGE_CACHE = os.getenv(
    "CC_USAGE_CACHE",
    os.path.join(_CC_HOME, "plugins", "oh-my-claudecode", ".usage-cache-anthropic.json"),
)
CC_PROJECTS_DIR = os.getenv("CC_PROJECTS_DIR", os.path.join(_CC_HOME, "projects"))
# Context window for % calc: 1M-context models by default; set 200000 for standard
CC_CONTEXT_WINDOW = int(os.getenv("CC_CONTEXT_WINDOW", "1000000"))

# Scheduled messages (type text into a window at a set time — e.g. after limit reset)
SCHEDULE_FILE = os.getenv("SCHEDULE_FILE", "scheduled_messages.json")
SCHEDULE_POLL = int(os.getenv("SCHEDULE_POLL", "10"))  # seconds between due-checks
# Delay after focusing the target window before typing — a non-foreground window
# comes forward asynchronously, so typing too soon pastes into the wrong window
SCHEDULE_FOCUS_SETTLE = float(os.getenv("SCHEDULE_FOCUS_SETTLE", "0.6"))

# Paths
LOG_FILE = "bot.log"

# Screen capture
SCREENSHOT_QUALITY = 70  # JPEG compression %
SCREENSHOT_COOLDOWN = 2  # seconds between screenshots
# Web live view fallback size, used only when the client sends no preference
# (the dashboard has its own Fit/1280/1920/Full selector). Full-res frames
# (~260KB base64) strain the tunnel, so short auto-refresh intervals silently
# degrade to the round-trip time; 1920 is the readable/affordable middle.
WEB_SCREEN_MAX_W = int(os.getenv("WEB_SCREEN_MAX_W", "1920"))  # 0 = no downscale
WEB_SCREEN_QUALITY = int(os.getenv("WEB_SCREEN_QUALITY", "70"))

# Input simulation
TYPING_INTERVAL = 0.02  # delay between keystrokes (seconds)
# Gap between the clipboard paste and the Enter that submits it. A TUI which
# detects bracketed paste (Claude Code) buffers the pasted block for a moment and
# treats an Enter arriving inside that window as part of the paste — a literal
# newline, not submit. The text then sits in the input box while the bot happily
# answers "Typed: ...". 0.1s lost that race often enough to look like "typing is
# broken"; raise this if messages still pile up unsent.
TYPE_ENTER_DELAY = float(os.getenv("TYPE_ENTER_DELAY", "0.45"))
# Paste hotkey. Claude Code binds Ctrl+V to "paste image from clipboard", so in a
# terminal running it a text Ctrl+V is a silent no-op — the keystroke arrives, the
# clipboard is right, and nothing appears. Ctrl+Shift+V is the terminal paste and
# works in every VS Code session tested, so terminal-ish targets get that one.
TYPE_PASTE_HOTKEY = os.getenv("TYPE_PASTE_HOTKEY", "ctrl+v")
TYPE_TERMINAL_PASTE_HOTKEY = os.getenv("TYPE_TERMINAL_PASTE_HOTKEY", "ctrl+shift+v")
# Window titles that mean "a terminal is on the other end" (lowercase substrings)
TYPE_TERMINAL_HINTS = [
    h.strip().lower()
    for h in os.getenv(
        "TYPE_TERMINAL_HINTS",
        "visual studio code,windows terminal,powershell,command prompt,cmd.exe,"
        "conemu,cmder,mintty,git bash,wsl,alacritty,wezterm,kitty,tabby",
    ).split(",")
    if h.strip()
]

# File delivery
APK_SEARCH_DIRS = [
    os.path.expanduser("~"),  # fallback: search from home
]
APK_GLOB = "**/*.apk"
BUILD_CMD = "cmd /c gradlew.bat assembleDebug"
PROJECT_DIR = r"C:\Projects\My habits"
GIT_DIR = os.getenv("GIT_DIR", PROJECT_DIR)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (Telegram limit)

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("bot")
