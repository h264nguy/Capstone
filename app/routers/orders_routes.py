from datetime import datetime
from typing import List

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.config import ESP_BASE_URL, ESP_ENDPOINT
from app.core.auth import current_user
from app.core.storage import load_orders, save_orders

router = APIRouter()


class OrderItem(BaseModel):
    drinkId: str
    drinkName: str
    quantity: int
    calories: int


async def send_to_esp(items: list):
    url = f"{ESP_BASE_URL}{ESP_ENDPOINT}"
    payload = {"items": items}
    timeout = httpx.Timeout(8.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


@router.post("/checkout")
async def checkout(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    body = await request.json()
    items_raw = body.get("items", [])
    if not isinstance(items_raw, list) or not items_raw:
        return JSONResponse({"ok": False, "error": "No items"}, status_code=400)

    # validate items
    items: List[dict] = []
    for it in items_raw:
        try:
            oi = OrderItem(**it)
        except Exception:
            continue
        items.append(oi.dict())

    if not items:
        return JSONResponse({"ok": False, "error": "Invalid items"}, status_code=400)

    # persist order history (one row per drink line)
    orders = load_orders()
    now = datetime.utcnow().isoformat()
    for it in items:
        orders.append({
            "username": user,
            "drinkId": it["drinkId"],
            "drinkName": it["drinkName"],
            "quantity": int(it.get("quantity", 1)),
            "calories": int(it.get("calories", 0)),
            "ts": now,
        })
    save_orders(orders)

    # optional: send to ESP (best-effort)
    esp_result = None
    try:
        esp_result = await send_to_esp(items)
    except Exception:
        esp_result = None

    return JSONResponse({"ok": True, "saved": len(items), "esp": esp_result})


@router.get("/api/history")
def api_history(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)

    orders = [o for o in load_orders() if o.get("username") == user]
    return JSONResponse({"ok": True, "username": user, "orders": orders})
