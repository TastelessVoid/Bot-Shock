"""
Application-wide constants for Bot Shock.
"""

from pathlib import Path

from botshock import __version__

APP_NAME = "Bot Shock"
LOGGER_NAMESPACE = "BotShock"
APP_VERSION = __version__

# Database configuration
DEFAULT_DB_PATH = "botshock.db"
DEFAULT_POOL_SIZE = 5

# Logging configuration
LOG_DIR = Path("logs")
CURRENT_LOG_FILENAME = "bot.log"
MAX_OLD_LOGS = 10
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL_WIDTH = 8
LOG_COMPONENT_WIDTH = 20

# API configuration
OPENSHOCK_API_BASE_URL = "https://api.openshock.app"
OPENSHOCK_API_CONTROL_URL = f"{OPENSHOCK_API_BASE_URL}/2/shockers/control"
API_TIMEOUT_SECONDS = 10
API_MAX_CONNECTIONS = 100
API_REQUESTS_PER_MINUTE = 60

# Discord configuration
DEFAULT_ACTIVITY = "with shocks!"

# Encryption configuration
# Note: Do NOT change the salt value to preserve compatibility with existing encrypted data
ENCRYPTION_SALT = b"botshock_salt_v2_"

# Rate limiting
DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds

# Discord limits
DISCORD_MAX_SELECT_OPTIONS = 25
DISCORD_EMBED_FIELD_LIMIT = 25
DISCORD_EMBED_DESCRIPTION_LIMIT = 4096
DISCORD_BUTTON_LABEL_LIMIT = 100
DISCORD_DEFAULT_TIMEOUT = 180

# Timeouts in seconds
SHOCKER_SELECT_TIMEOUT = 180
MODAL_TIMEOUT = 300  # seconds
BUTTON_CONFIRM_TIMEOUT = 30
COOLDOWN_CHECK_TIMEOUT = 60

# Cooldown defaults (seconds)
DEFAULT_SHOCKER_COOLDOWN = 60
DEFAULT_TRIGGER_COOLDOWN = 60
SCHEDULER_CHECK_INTERVAL = 30

# Shock parameter defaults
DEFAULT_SHOCK_INTENSITY = 30
DEFAULT_SHOCK_DURATION = 1000
DEFAULT_SHOCK_TYPE = "Shock"

# UI defaults
DEFAULT_PAGE_SIZE = 5
REMINDER_LIST_MAX_INLINE_BUTTONS = 5
