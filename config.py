import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
VERSION = "0.10.0"

# Web dashboard / Mini App
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WEB_TOKEN = os.getenv("WEB_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # public HTTPS URL for Telegram Mini App

# Projects
PROJECTS_ROOT = os.getenv("PROJECTS_ROOT", r"C:\Projects")

# Paths
LOG_FILE = "bot.log"

# Screen capture
SCREENSHOT_QUALITY = 70  # JPEG compression %
SCREENSHOT_COOLDOWN = 2  # seconds between screenshots

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
