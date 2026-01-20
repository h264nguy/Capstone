from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter(prefix="/api/esp", tags=["esp"])

# Set this in Render Environment Variables:
# ESP_POLL_KEY=win12345key
ESP_POLL_KEY = os.getenv("ESP_POLL_KEY", "win12345key")

# Simple in-memory queue (works for demo; for production use persistent storage)
ESP_QUEUE = []


def _check_key(key: str):
    if key != ESP_POLL_KEY:
        raise HTTPException(status_code=403, detail="Invalid key")


@router.get("/next")
def esp_next(key: str):
    _check_key(key)

    if not ESP_QUEUE:
        return {"ok": True, "order": None}

    # return the first pending order
    return {"ok": True, "order": ESP_QUEUE[0]}


class CompleteBody(BaseModel):
    id: str


@router.post("/complete")
def esp_complete(body: CompleteBody, key: str):
    _check_key(key)

    global ESP_QUEUE
    ESP_QUEUE = [o for o in ESP_QUEUE if o.get("id") != body.id]

    return {"ok": True}
