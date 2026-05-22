import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.json")
_lock = threading.Lock()


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """PBKDF2-HMAC-SHA256 password hashing. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(32)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000,
    )
    return key.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    key, _ = _hash_password(password, salt)
    return hmac.compare_digest(key, stored_hash)


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


def create_user(username: str, password: str) -> dict:
    """Creates a new user. Raises ValueError if username already taken."""
    with _lock:
        data = _load()
        if username in data:
            raise ValueError("帳號已存在")
        pw_hash, salt = _hash_password(password)
        user = {
            "id": str(uuid.uuid4()),
            "username": username,
            "password_hash": pw_hash,
            "salt": salt,
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
        return _verify_password(password, user["password_hash"], user["salt"])


def list_users(include_hash: bool = False) -> list[dict]:
    """Returns all users sorted by created_at. Optionally includes password hash."""
    with _lock:
        data = _load()
        users = []
        for u in data.values():
            entry = {"id": u["id"], "username": u["username"], "created_at": u["created_at"]}
            if include_hash:
                entry["password_hash"] = u["password_hash"]
            users.append(entry)
        return sorted(users, key=lambda u: u["created_at"])


def reset_password(username: str, new_password: str) -> None:
    """Resets a user's password. Raises ValueError if user not found."""
    with _lock:
        data = _load()
        if username not in data:
            raise ValueError(f"找不到用戶：{username}")
        pw_hash, salt = _hash_password(new_password)
        data[username]["password_hash"] = pw_hash
        data[username]["salt"] = salt
        _save(data)


def get_user(username: str) -> dict | None:
    # Demo admin is env-var only — synthesise a minimal record so callers
    # like invite don't need to special-case it.
    demo = os.environ.get("DEMO_USERNAME", "demo")
    if username == demo:
        return {"id": "demo", "username": username, "created_at": "2000-01-01T00:00:00+00:00"}
    with _lock:
        data = _load()
        user = data.get(username)
        if not user:
            return None
        return {"id": user["id"], "username": username, "created_at": user["created_at"]}
