import json
import os
import threading
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "invitations.json")
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


def create_invitation(group_id: str, group_name: str, from_user: str, to_user: str) -> dict:
    with _lock:
        data = _load()
        # Prevent duplicate pending invitations
        for inv in data.values():
            if (
                inv["group_id"] == group_id
                and inv["to_user"] == to_user
                and inv["status"] == "pending"
            ):
                raise ValueError("已有待接受的邀請")
        inv = {
            "id": str(uuid.uuid4()),
            "group_id": group_id,
            "group_name": group_name,
            "from_user": from_user,
            "to_user": to_user,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data[inv["id"]] = inv
        _save(data)
        return inv


def get_pending_for_user(username: str) -> list[dict]:
    with _lock:
        data = _load()
        return [
            inv for inv in data.values()
            if inv["to_user"] == username and inv["status"] == "pending"
        ]


def accept_invitation(inv_id: str, username: str) -> dict:
    with _lock:
        data = _load()
        inv = data.get(inv_id)
        if not inv:
            raise ValueError("邀請不存在")
        if inv["to_user"] != username:
            raise ValueError("無權操作此邀請")
        inv["status"] = "accepted"
        _save(data)
        return inv


def decline_invitation(inv_id: str, username: str) -> dict:
    with _lock:
        data = _load()
        inv = data.get(inv_id)
        if not inv:
            raise ValueError("邀請不存在")
        if inv["to_user"] != username:
            raise ValueError("無權操作此邀請")
        inv["status"] = "declined"
        _save(data)
        return inv
