from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone

from app.config import ESP_POLL_KEY
from app.core.storage import load_esp_queue, save_esp_queue

router = APIRouter(prefix="/api/esp", tags=["esp"])


def _require_key(key: str):
    if not key or key != ESP_POLL_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/next")
async def next_order(key: str):
    """Return the oldest pending order and mark it in_progress."""
    _require_key(key)

    queue = load_esp_queue()

    # Find oldest pending
    for item in queue:
        if item.get("status") == "pending":
            item["status"] = "in_progress"
            item["claimed_at"] = _now_iso()
            save_esp_queue(queue)
            return {"ok": True, "order": item}

    return {"ok": True, "order": None}


class CompleteBody(BaseModel):
    id: str


@router.post("/complete")
async def complete_order(body: CompleteBody, key: str):
    _require_key(key)
    queue = load_esp_queue()

    for item in queue:
        if item.get("id") == body.id:
            item["status"] = "complete"
            item["completed_at"] = _now_iso()
            save_esp_queue(queue)
            return {"ok": True}

    return {"ok": False, "error": "Order not found"}
