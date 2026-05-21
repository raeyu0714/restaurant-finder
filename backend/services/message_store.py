import json
import os
import threading
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "group_messages.json")
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(_STORE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(_STORE_PATH)), exist_ok=True)
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_message(group_id: str, username: str, text: str) -> dict:
    with _lock:
        data = _load()
        msg = {
            "id": str(uuid.uuid4()),
            "user": username,
            "text": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if group_id not in data:
            data[group_id] = []
        data[group_id].append(msg)
        _save(data)
        return msg


def get_messages(group_id: str, limit: int = 100) -> list[dict]:
    with _lock:
        data = _load()
        msgs = data.get(group_id, [])
        return msgs[-limit:]
