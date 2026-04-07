import os
from dotenv import load_dotenv

_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_DIR, ".env"))

# Telegram credentials
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
SESSION_NAME = "crawler_session"

# Target bot
BOT_USERNAME = "Vape_Rivne_Bot"

# Crawling limits
MAX_DEPTH = 6
DELAY_BETWEEN_ACTIONS = 1.5        # seconds
RESPONSE_TIMEOUT = 10               # seconds
MULTI_MESSAGE_WAIT = 2              # seconds
MAX_RETRIES = 2

# Unsafe button patterns (case-insensitive substring match)
# These buttons are recorded but NOT clicked
UNSAFE_PATTERNS = [
    "замовлен", "оформ", "підтверд",
    "оплат", "сплат", "liqpay", "pay",
    "видалити все", "очистити",
]

# Navigation button patterns (case-insensitive)
# Exact match for short words, substring for longer phrases
# These buttons are recorded but NOT clicked
NAV_PATTERNS_EXACT = ["назад", "back", "◀️", "⬅️", "↩️"]
NAV_PATTERNS_SUBSTRING = ["головне меню", "на початок", "main menu", "меню"]

# Reset commands to try when returning to initial state (for reply keyboards)
RESET_COMMANDS = ["/start", "/menu", "Меню"]

# Output paths (relative to project root, i.e. parent of crawler/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "bot_structure.json")
OUTPUT_MD = os.path.join(OUTPUT_DIR, "bot_structure.md")
