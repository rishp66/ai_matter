import logging
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path

from bridge import config, persistence

logger = logging.getLogger(__name__)

_STATE_DIR = Path(config.BRIDGE_STATE_DIR)
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_STATE_FILE = _STATE_DIR / "drafts.json"


@dataclass
class Draft:
    id: str
    reply: str
    target_channel_id: str
    root_id: str
    reason: str
    provenance: list[str]
    trigger_text: str
    owner_user_id: str
    contexts: list[dict]


_store: dict[str, "Draft"] = {}


def _load_from_disk() -> None:
    raw: dict = persistence.load(_STATE_FILE, {})
    for draft_id, d in raw.items():
        try:
            _store[draft_id] = Draft(**d)
        except Exception:
            logger.warning("Skipping corrupt draft entry %s", draft_id)


def _persist() -> None:
    try:
        persistence.save(_STATE_FILE, {k: asdict(v) for k, v in _store.items()})
    except Exception:
        logger.exception("Failed to persist drafts to disk")


# Populate hot store from disk on import
_load_from_disk()


def put(draft: Draft) -> None:
    _store[draft.id] = draft
    _persist()


def claim(draft_id: str) -> Draft | None:
    """Atomic pop-to-claim: removes and returns the draft, or None if already gone."""
    draft = _store.pop(draft_id, None)
    if draft is not None:
        _persist()
    return draft


def list_for_owner(uid: str) -> list[Draft]:
    return [d for d in _store.values() if d.owner_user_id == uid]


def new_id() -> str:
    return uuid.uuid4().hex
