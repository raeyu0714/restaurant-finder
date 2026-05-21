import json
import os
import threading

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "favourites.json")
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


def get_favourites(username: str) -> list[dict]:
    with _lock:
        return _load().get(username, [])


def add_favourite(username: str, restaurant: dict) -> list[dict]:
    with _lock:
        data = _load()
        favs = data.setdefault(username, [])
        if not any(f["id"] == restaurant["id"] for f in favs):
            favs.append(restaurant)
            _save(data)
        return favs


def remove_favourite(username: str, restaurant_id: str) -> list[dict]:
    with _lock:
        data = _load()
        favs = data.get(username, [])
        data[username] = [f for f in favs if f["id"] != restaurant_id]
        _save(data)
        return data[username]


def is_favourite(username: str, restaurant_id: str) -> bool:
    return any(f["id"] == restaurant_id for f in get_favourites(username))
