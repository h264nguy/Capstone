from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import os
import json
from pathlib import Path

router = APIRouter()

# ---- Config ----
ESP_POLL_KEY = os.getenv("ESP_POLL_KEY", "win12345key")  # set this in Render env
BASE_DIR = Path(__file__).resolve().parents[1]           # app/
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

QUEUE_FILE = DATA_DIR / "esp_queue.json"
DONE_FILE  = DATA_DIR / "esp_done.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2))


def _check_key(key: str):
    if key != ESP_POLL_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")


class CompleteBody(BaseModel):
    id: str


@router.get("/api/esp/next")
def esp_next(key: str):
    _check_key(key)
    queue = _load_json(QUEUE_FILE, [])
    if not queue:
        return {"ok": True, "order": None}
    return {"ok": True, "order": queue[0]}


@router.post("/api/esp/complete")
def esp_complete(body: CompleteBody, key: str):
    _check_key(key)
    queue = _load_json(QUEUE_FILE, [])
    done = _load_json(DONE_FILE, [])

    if queue and queue[0].get("id") == body.id:
        done.append(queue.pop(0))
        _save_json(QUEUE_FILE, queue)
        _save_json(DONE_FILE, done)
        return {"ok": True}

    return {"ok": False, "error": "Order not found or not first in queue"}
