from pathlib import Path
import os


# =========================
# APP CONFIG
# =========================

# Canva link (optional)
CANVA_URL = "https://smartbartender.my.canva.site/dag-sgpflmm"

# ESP8266 / ESP32 (optional, local network)
ESP_BASE_URL = "http://172.20.10.3"  # change to your ESP IP
ESP_ENDPOINT = "/make-drink"         # must match ESP route

# Session secret (change this before deploying)
SESSION_SECRET = "CHANGE_THIS_TO_ANY_RANDOM_SECRET_123"

# Project paths
BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent

STATIC_DIR = REPO_DIR / "static"
DATA_DIR = BASE_DIR / "data"

USERS_FILE = DATA_DIR / "users.json"
ORDERS_FILE = DATA_DIR / "orders.json"
DRINKS_FILE = DATA_DIR / "drinks.json"

# =========================
# ESP POLLING (for published / online deployments)
# =========================
# Put this in Render Environment Variables as ESP_POLL_KEY.
# Your ESP8266 uses the SAME value in its ESP_KEY.
ESP_POLL_KEY = os.getenv("ESP_POLL_KEY", "win12345key")

# Where queued orders are stored for the ESP to pick up.
ESP_QUEUE_FILE = DATA_DIR / "esp_queue.json"
