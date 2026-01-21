from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import current_user

router = APIRouter()

# ---- Shared data folder (repo_root/data) ----
REPO_ROOT = Path(__file__).resolve().parents[2]  # app/routers -> app -> repo_root
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ORDERS_FILE = DATA_DIR / "orders.json"
ESP_QUEUE_FILE = DATA_DIR / "esp_queue.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _username_from_session(request: Request) -> Optional[str]:
    """
    Unify username extraction so History + Checkout always match.
    """
    u = current_user(request)
    if not u:
        return None

    # if current_user returns dict sometimes
    if isinstance(u, dict):
        u = u.get("username") or u.get("user") or u.get("name")

    sess = getattr(request, "session", {}) or {}
    u2 = sess.get("user") or sess.get("username") or u

    if not u2:
        return None
    return str(u2)


@router.post("/checkout")
async def checkout(request: Request) -> JSONResponse:
    """
    Accepts JSON: { "items": [ {drinkId, drinkName, quantity, calories}, ... ] }
    Returns JSON always.
    Also enqueues ONE order into esp_queue.json for ESP polling.
    """
    username = _username_from_session(request)
    if not username:
        # IMPORTANT: do NOT redirect to /login for fetch() calls.
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return JSONResponse({"ok": False, "error": "No items"}, status_code=400)

    # Normalize + validate
    norm_items: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        drink_id = str(it.get("drinkId", "")).strip()
        drink_name = str(it.get("drinkName", "")).strip()

        try:
            qty = int(it.get("quantity", 1))
        except Exception:
            qty = 1

        try:
            cal = int(it.get("calories", 0))
        except Exception:
            cal = 0

        if not drink_id or not drink_name or qty <= 0:
            continue

        norm_items.append(
            {
                "drinkId": drink_id,
                "drinkName": drink_name,
                "quantity": qty,
                "calories": cal,
            }
        )

    if not norm_items:
        return JSONResponse({"ok": False, "error": "Items invalid"}, status_code=400)

    now = datetime.now(timezone.utc).isoformat()

    # ---- Save history rows ----
    orders = _load_json(ORDERS_FILE, [])
    if not isinstance(orders, list):
        orders = []

    for it in norm_items:
        orders.append(
            {
                "username": username,
                "drinkId": it["drinkId"],
                "drinkName": it["drinkName"],   # ✅ drink name saved
                "quantity": it["quantity"],
                "calories": it["calories"],
                "ts": now,
            }
        )

    _save_json(ORDERS_FILE, orders)

    # ---- Enqueue for ESP (stores ALL items) ----
    queue = _load_json(ESP_QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []

    order_id = str(uuid4())
    queue.append(
        {
            "id": order_id,
            "username": username,
            "ts": now,
            "items": norm_items,  # multiple drinks preserved here
        }
    )
    _save_json(ESP_QUEUE_FILE, queue)

    # Safe JSON return (no syntax error)
    return JSONResponse(
        {
            "ok": True,
            "saved": True,
            "count": len(norm_items),
            "queued": True,
            "orderId": order_id,
            "esp": True,
        },
        status_code=200,
    )


@router.get("/api/history")
def api_history(request: Request) -> JSONResponse:
    username = _username_from_session(request)
    if not username:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    orders = _load_json(ORDERS_FILE, [])
    if not isinstance(orders, list):
        orders = []

    mine = [o for o in orders if str(o.get("username")) == username]
    return JSONResponse({"ok": True, "username": username, "orders": mine})
