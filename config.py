import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
VERSION = "0.2.0"

# Paths
LOG_FILE = "bot.log"

# Screen capture
SCREENSHOT_QUALITY = 70  # JPEG compression %
SCREENSHOT_COOLDOWN = 2  # seconds between screenshots

# Input simulation
TYPING_INTERVAL = 0.02  # delay between keystrokes (seconds)

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
