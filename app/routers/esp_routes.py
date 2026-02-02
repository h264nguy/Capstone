from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import ESP_POLL_KEY
from app.core.storage import (
    get_active_order_for_esp,
    complete_and_archive_order,
    load_esp_queue,
    queue_position,
    _remaining_seconds_for_order,
)

router = APIRouter()


def _check_key(key: str):
    if key != ESP_POLL_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")


class CompleteBody(BaseModel):
    id: str


@router.get("/api/esp/next")
def esp_next(key: str):
    """ESP polls this endpoint for the current job."""
    _check_key(key)
    order = get_active_order_for_esp()
    if not order:
        return {"ok": True, "order": None}

    # Queue meta (position + ETA)
    qinfo = queue_position(order.get("id")) or {}

    # Convenience fields for simpler ESP sketches
    # (If the order contains multiple items, we expose the first one as the current display fields.)
    items = order.get("items") or []
    if isinstance(items, list) and items:
        first = items[0] if isinstance(items[0], dict) else {}
        order.setdefault("drinkId", first.get("drinkId", ""))
        order.setdefault("drinkName", first.get("drinkName", ""))
        order.setdefault("quantity", int(first.get("quantity", 1) or 1))

    # Remaining time for the active order (seconds)
    order["etaSeconds"] = int(qinfo.get("etaThisSeconds") or _remaining_seconds_for_order(order))
    order["queuePosition"] = qinfo.get("position")
    order["queueAhead"] = qinfo.get("ahead")
    order["queueEtaSeconds"] = qinfo.get("etaSeconds")

    return {"ok": True, "order": order}


@router.post("/api/esp/complete")
def esp_complete(body: CompleteBody, key: str):
    """ESP calls this after finishing the job."""
    _check_key(key)
    ok = complete_and_archive_order(body.id)
    if ok:
        return {"ok": True}
    return {"ok": False, "error": "Order not found"}


@router.get("/api/queue/status")
def queue_status(orderId: str):
    """Frontend can poll this to show queue position for a given order."""
    info = queue_position(orderId)
    if not info:
        return {"ok": False, "error": "Not in queue (maybe already completed)"}
    return {"ok": True, "orderId": orderId, **info}


@router.get("/api/queue/active")
def queue_active(limit: int = 20):
    """(Optional) Show active queue for debugging."""
    q = [o for o in load_esp_queue() if o.get("status") in ("pending", "in_progress")]
    return {"ok": True, "count": len(q), "queue": q[: max(1, min(int(limit), 100))]}
