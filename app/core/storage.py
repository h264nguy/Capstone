import json
from typing import Any, Dict, List

from app.config import USERS_FILE, ORDERS_FILE, DRINKS_FILE


def _read_json(path) -> Any:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return json.loads(raw)


def _write_json(path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


# -------------------------
# Users
# -------------------------

def load_users() -> Dict[str, str]:
    data = _read_json(USERS_FILE)
    return data if isinstance(data, dict) else {}


def save_users(users: Dict[str, str]):
    _write_json(USERS_FILE, users)


# -------------------------
# Orders
# -------------------------

def load_orders() -> List[dict]:
    data = _read_json(ORDERS_FILE)
    return data if isinstance(data, list) else []


def save_orders(orders: List[dict]):
    _write_json(ORDERS_FILE, orders)


# -------------------------
# Drinks
# -------------------------

def load_drinks() -> List[dict]:
    data = _read_json(DRINKS_FILE)
    return data if isinstance(data, list) else []


def ensure_drinks_file():
    """Create drinks.json if missing/empty (starter list)."""
    if DRINKS_FILE.exists():
        raw = DRINKS_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return

    starter = [
        {"id": "amber_storm", "name": "Amber Storm", "calories": 104},
        {"id": "classic_fusion", "name": "Classic Fusion", "calories": 76},
        {"id": "chaos_punch", "name": "Chaos Punch", "calories": 204},
        {"id": "crystal_chill", "name": "Crystal Chill", "calories": 56},
        {"id": "cola_spark", "name": "Cola Spark", "calories": 81},
        {"id": "dark_amber", "name": "Dark Amber", "calories": 65},
        {"id": "voltage_fizz", "name": "Voltage Fizz", "calories": 117},
        {"id": "golden_breeze", "name": "Golden Breeze", "calories": 87},
        {"id": "energy_sunrise", "name": "Energy Sunrise", "calories": 180},
        {"id": "citrus_cloud", "name": "Citrus Cloud", "calories": 95},
        {"id": "citrus_shine", "name": "Citrus Shine", "calories": 90},
        {"id": "sparking_citrus", "name": "Sparking Citrus", "calories": 102},
        {"id": "sunset_fizz", "name": "Sunset Fizz", "calories": 120},
        {"id": "tropical_charge", "name": "Tropical Charge", "calories": 160},

        # Bases
        {"id": "base_water", "name": "Water", "calories": 0},
        {"id": "base_lemonade", "name": "Lemonade", "calories": 150},
        {"id": "base_coca_cola", "name": "Coca-Cola", "calories": 140},
        {"id": "base_sprite", "name": "Sprite", "calories": 140},
        {"id": "base_ginger_ale", "name": "Ginger Ale", "calories": 120},
        {"id": "base_red_bull", "name": "Red Bull", "calories": 110},
    ]

    _write_json(DRINKS_FILE, starter)
