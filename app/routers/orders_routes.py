from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import current_user
from app.core.storage import load_orders, save_orders, enqueue_esp_order

router = APIRouter()


def _username_from_session(request: Request) -> Optional[str]:
    u = current_user(request)
    if not u:
        return None

    if isinstance(u, dict):
        u = u.get("username") or u.get("user") or u.get("name")

    sess = getattr(request, "session", {}) or {}
    u2 = sess.get("user") or sess.get("username") or u

    return str(u2) if u2 else None


@router.post("/checkout")
async def checkout(request: Request) -> JSONResponse:
    username = _username_from_session(request)
    if not username:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    items = payload.get("items")
    if not isinstance(items, list) or not items:
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
            {"drinkId": drink_id, "drinkName": drink_name, "quantity": qty, "calories": cal}
        )

    if not norm_items:
        return JSONResponse({"ok": False, "error": "Items invalid"}, status_code=400)

    now = datetime.now(timezone.utc).isoformat()

    # ---- Save history rows (SAME file used by recommender) ----
    orders = load_orders()
    for it in norm_items:
        orders.append(
            {
                "username": username,
                "drinkId": it["drinkId"],
                "drinkName": it["drinkName"],
                "quantity": it["quantity"],
                "calories": it["calories"],
                "ts": now,
            }
        )
    save_orders(orders)

    # ---- Enqueue ONE order for ESP (keeps multiple items) ----
    order_id = str(uuid4())
    enqueue_esp_order(
        {
            "id": order_id,
            "username": username,
            "ts": now,
            "status": "pending",
            "items": norm_items,
        }
    )

    return JSONResponse(
        {"ok": True, "saved": True, "count": len(norm_items), "queued": True, "orderId": order_id},
        status_code=200,
    )


@router.get("/api/history")
def api_history(request: Request) -> JSONResponse:
    username = _username_from_session(request)
    if not username:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    orders = load_orders()
    mine = [o for o in orders if str(o.get("username")) == username]
    return JSONResponse({"ok": True, "username": username, "orders": mine})
