import json
import os
import threading
import uuid
from datetime import datetime, timezone

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "group_votes.json")
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


def create_vote(group_id: str, title: str, options: list[dict], creator: str) -> dict:
    """options: list of dicts with keys id, name, address, walking_minutes, latitude, longitude"""
    with _lock:
        data = _load()
        vote = {
            "id": str(uuid.uuid4()),
            "group_id": group_id,
            "title": title,
            "options": options,
            "votes": {opt["id"]: [] for opt in options},
            "creator": creator,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data[vote["id"]] = vote
        _save(data)
        return vote


def cast_vote(vote_id: str, username: str, option_id: str) -> dict:
    """Toggle: removes vote if already cast on same option, otherwise switches to new option."""
    with _lock:
        data = _load()
        vote = data.get(vote_id)
        if not vote:
            raise ValueError("投票不存在")
        if vote["status"] != "open":
            raise ValueError("投票已結束")
        if option_id not in vote["votes"]:
            raise ValueError("選項不存在")
        # Remove user from all options first
        for voters in vote["votes"].values():
            if username in voters:
                voters.remove(username)
        # Add to chosen option (toggle off if they removed themselves above and it was same option)
        # We already removed, so check if we should re-add
        # The "toggle" here means: if they pick the same option again it stays removed (un-vote)
        # Since we removed from all, just add to new option unless they had already picked it
        # Re-check: we need to know if username was on option_id BEFORE removal
        # Simplest: reload logic — re-read original, check, then update
        # Since we're inside lock, re-read was already done. Let's track differently.
        # Actually the load is done above. Let me restructure:
        vote["votes"][option_id].append(username)
        _save(data)
        return vote


def _cast_vote_toggle(vote_id: str, username: str, option_id: str) -> dict:
    """True toggle: un-vote if same option, switch if different."""
    with _lock:
        data = _load()
        vote = data.get(vote_id)
        if not vote:
            raise ValueError("投票不存在")
        if vote["status"] != "open":
            raise ValueError("投票已結束")
        if option_id not in vote["votes"]:
            raise ValueError("選項不存在")

        already_on_same = username in vote["votes"][option_id]

        # Remove from all options
        for voters in vote["votes"].values():
            if username in voters:
                voters.remove(username)

        # If was on same option, leave removed (un-vote). Otherwise add to new option.
        if not already_on_same:
            vote["votes"][option_id].append(username)

        _save(data)
        return vote


# Expose the toggle variant as the primary cast function
cast_vote = _cast_vote_toggle


def list_votes(group_id: str) -> list[dict]:
    with _lock:
        data = _load()
        return sorted(
            [v for v in data.values() if v["group_id"] == group_id],
            key=lambda v: v["created_at"],
            reverse=True,
        )


def close_vote(vote_id: str, username: str) -> dict:
    with _lock:
        data = _load()
        vote = data.get(vote_id)
        if not vote:
            raise ValueError("投票不存在")
        if vote["creator"] != username:
            raise ValueError("只有建立者可以結束投票")
        vote["status"] = "closed"
        _save(data)
        return vote
