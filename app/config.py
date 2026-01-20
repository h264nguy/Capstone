from pathlib import Path

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
