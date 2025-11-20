from pathlib import Path

# Paths (not user-configurable)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DOWNLOAD_PATH = PROJECT_ROOT / "download"
INCOMPLETE_PATH = PROJECT_ROOT / "download" / "incomplete"
QUEUE_STORAGE = PROJECT_ROOT / "config" / "queue.json"
LOG_PATH = PROJECT_ROOT / "logs"
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
CACHE_PATH = PROJECT_ROOT / "cache"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "files" / "config.yaml"
WWW_ROOT = PROJECT_ROOT / "web"

# URLs
FAST_DOWNLOAD_API_URL = "https://annas-archive.org/dyn/api/fast_download.json"

# Logging
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default credentials
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "stacks"

# Rate limiting settings
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 10
LOGIN_ATTEMPT_WINDOW_MINUTES = 10