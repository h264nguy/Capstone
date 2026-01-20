from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import json
from pathlib import Path
import uuid

from app.core.auth import current_user
from app.config import BASE_DIR, ESP_POLL_KEY  # make sure these exist in app/config.py

router = APIRouter()

# --- Files (Render disk is writable, but ephemeral) ---
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ORDERS_FILE = DATA_DIR / "orders.json"
ESP_QUEUE_FILE = DATA_DIR / "esp_queue.json"


def _read_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


# ---------- Pydantic models so /docs shows Request Body ----------
class OrderItem(BaseModel):
    drinkId: str
    drinkName: str
    quantity: int = 1
    calories: int = 0
    ratios: Dict[str, int] = {}


class CheckoutRequest(BaseModel):
    items: List[OrderItem]


@router.post("/checkout")
async def checkout(payload: CheckoutRequest, request: Request):
    # require login (because you use sessions)
    user = current_user(request)
    if not user:
        # return JSON (not redirect) so frontend can show message
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    items = payload.items
    if not items:
        return JSONResponse({"ok": False, "error": "No items"}, status_code=400)

    # Save orders history
    orders = _read_json(ORDERS_FILE, [])
    ts = datetime.utcnow().isoformat()

    # create one order per item (simple + matches your history table)
    for it in items:
        orders.append({
            "id": str(uuid.uuid4()),
            "username": user,
            "drinkId": it.drinkId,
            "drinkName": it.drinkName,
            "quantity": int(it.quantity or 1),
            "calories": int(it.calories or 0),
            "ratios": it.ratios or {},
            "ts": ts
        })

    _write_json(ORDERS_FILE, orders)

    # Enqueue for ESP polling: queue holds *pending* orders
    queue = _read_json(ESP_QUEUE_FILE, [])
    for it in items:
        queue.append({
            "id": str(uuid.uuid4()),
            "username": user,
            "drinkId": it.drinkId,
            "drinkName": it.drinkName,
            "quantity": int(it.quantity or 1),
            "calories": int(it.calories or 0),
            "ts": ts
        })
    _write_json(ESP_QUEUE_FILE, queue)

    return {"ok": True, "queued": len(items)}


# ---------- ESP Polling endpoints ----------
@router.get("/api/esp/next")
def esp_next(key: str):
    if key != ESP_POLL_KEY:
        return JSONResponse({"ok": False, "error": "bad key"}, status_code=403)

    queue = _read_json(ESP_QUEUE_FILE, [])
    if not queue:
        return {"ok": True, "order": None}

    # pop first pending
    order = queue.pop(0)
    _write_json(ESP_QUEUE_FILE, queue)

    return {"ok": True, "order": order}


class CompleteBody(BaseModel):
    id: str


@router.post("/api/esp/complete")
def esp_complete(key: str, body: CompleteBody):
    if key != ESP_POLL_KEY:
        return JSONResponse({"ok": False, "error": "bad key"}, status_code=403)
    # optional: you could log completed ids if you want
    return {"ok": True}
