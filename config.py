import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
VERSION = "0.16.6"

# Web dashboard / Mini App
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WEB_TOKEN = os.getenv("WEB_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # public HTTPS URL for Telegram Mini App

# Projects
PROJECTS_ROOT = os.getenv("PROJECTS_ROOT", r"C:\Projects")

# Speech-to-text (Groq Whisper — free key at console.groq.com)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

# Transcript cleanup (same Groq key)
HUMANIZE_MODEL = os.getenv("HUMANIZE_MODEL", "llama-3.3-70b-versatile")
HUMANIZE_DEFAULT = os.getenv("HUMANIZE_DEFAULT", "1") == "1"

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
