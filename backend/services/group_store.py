import json
import os
import threading
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "groups.json")
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


def create_group(name: str, creator: str) -> dict:
    with _lock:
        data = _load()
        group = {
            "id": str(uuid.uuid4()),
            "name": name,
            "creator": creator,
            "members": [creator],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data[group["id"]] = group
        _save(data)
        return group


def get_group(group_id: str) -> dict | None:
    with _lock:
        return _load().get(group_id)


def list_groups_for_user(username: str) -> list[dict]:
    with _lock:
        data = _load()
        return [g for g in data.values() if username in g["members"]]


def add_member(group_id: str, username: str) -> None:
    with _lock:
        data = _load()
        group = data.get(group_id)
        if not group:
            raise ValueError("群組不存在")
        if username not in group["members"]:
            group["members"].append(username)
            _save(data)


def remove_member(group_id: str, username: str) -> None:
    with _lock:
        data = _load()
        group = data.get(group_id)
        if not group:
            raise ValueError("群組不存在")
        if username in group["members"]:
            group["members"].remove(username)
        if not group["members"]:
            del data[group_id]
        _save(data)


def delete_group(group_id: str) -> None:
    with _lock:
        data = _load()
        data.pop(group_id, None)
        _save(data)
