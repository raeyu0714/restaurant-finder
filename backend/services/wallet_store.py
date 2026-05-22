import json
import os
import threading
import uuid
from datetime import datetime, timezone

_WALLET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "wallets.json")
_TX_PATH     = os.path.join(os.path.dirname(__file__), "..", "..", "data", "transactions.json")
_lock = threading.Lock()


def _load_wallets() -> dict:
    try:
        with open(_WALLET_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_wallets(data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(_WALLET_PATH)), exist_ok=True)
    with open(_WALLET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_tx() -> list:
    try:
        with open(_TX_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_tx(data: list) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(_TX_PATH)), exist_ok=True)
    with open(_TX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_wallet(username: str) -> dict:
    with _lock:
        wallets = _load_wallets()
        return {"username": username, "balance": wallets.get(username, {}).get("balance", 0.0)}


def admin_adjust(username: str, amount: float, action: str, admin: str) -> dict:
    """action: 'set' | 'add'  (add can be negative to deduct)"""
    with _lock:
        wallets = _load_wallets()
        txs     = _load_tx()
        old_balance = wallets.get(username, {}).get("balance", 0.0)
        new_balance = amount if action == "set" else old_balance + amount
        if new_balance < 0:
            raise ValueError("餘額不能為負數")
        now = datetime.now(timezone.utc).isoformat()
        wallets[username] = {"balance": new_balance, "updated_at": now}
        _save_wallets(wallets)
        txs.append({
            "id":         str(uuid.uuid4()),
            "type":       "admin_adjust",
            "from_user":  admin,
            "to_user":    username,
            "amount":     new_balance - old_balance,
            "note":       f"管理員{'設定' if action == 'set' else '調整'}餘額",
            "group_id":   None,
            "created_at": now,
        })
        _save_tx(txs)
        return {"username": username, "balance": new_balance}


def transfer(from_user: str, to_user: str, amount: float, note: str, group_id: str) -> dict:
    if amount <= 0:
        raise ValueError("轉帳金額必須大於 0")
    with _lock:
        wallets = _load_wallets()
        txs     = _load_tx()
        from_bal = wallets.get(from_user, {}).get("balance", 0.0)
        if from_bal < amount:
            raise ValueError(f"餘額不足（目前 ${from_bal:.0f}）")
        to_bal = wallets.get(to_user, {}).get("balance", 0.0)
        now = datetime.now(timezone.utc).isoformat()
        wallets[from_user] = {"balance": from_bal - amount, "updated_at": now}
        wallets[to_user]   = {"balance": to_bal  + amount, "updated_at": now}
        _save_wallets(wallets)
        tx = {
            "id":         str(uuid.uuid4()),
            "type":       "transfer",
            "from_user":  from_user,
            "to_user":    to_user,
            "amount":     amount,
            "note":       note or "",
            "group_id":   group_id,
            "created_at": now,
        }
        txs.append(tx)
        _save_tx(txs)
        return tx


def get_transactions(username: str, limit: int = 50) -> list[dict]:
    with _lock:
        txs = _load_tx()
        user_txs = [t for t in txs if t.get("from_user") == username or t.get("to_user") == username]
        return sorted(user_txs, key=lambda t: t["created_at"], reverse=True)[:limit]
