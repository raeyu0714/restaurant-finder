import json
import os
import threading
import uuid
from datetime import datetime, timezone

from passlib.context import CryptContext

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.json")
_lock = threading.Lock()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)


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


def _trunc(password: str) -> str:
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def create_user(username: str, password: str) -> dict:
    """
    Creates a new user. Raises ValueError if username already taken.
    Returns the created user dict (without password_hash).
    """
    with _lock:
        data = _load()
        if username in data:
            raise ValueError("帳號已存在")
        user = {
            "id": str(uuid.uuid4()),
            "username": username,
            "password_hash": _pwd.hash(_trunc(password)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data[username] = user
        _save(data)
        return {"id": user["id"], "username": username}


def verify_user(username: str, password: str) -> bool:
    """Returns True if username exists and password matches."""
    with _lock:
        data = _load()
        user = data.get(username)
        if not user:
            return False
        return _pwd.verify(_trunc(password), user["password_hash"])


def list_users() -> list[dict]:
    """Returns all users without password hashes, sorted by created_at."""
    with _lock:
        data = _load()
        users = [
            {"id": u["id"], "username": u["username"], "created_at": u["created_at"]}
            for u in data.values()
        ]
        return sorted(users, key=lambda u: u["created_at"])


def get_user(username: str) -> dict | None:
    with _lock:
        data = _load()
        user = data.get(username)
        if not user:
            return None
        return {"id": user["id"], "username": username, "created_at": user["created_at"]}
