import uuid
from dataclasses import dataclass, field


@dataclass
class Draft:
    id: str
    reply: str
    target_channel_id: str
    root_id: str
    reason: str
    provenance: list[str]
    trigger_text: str


_store: dict[str, "Draft"] = {}


def put(draft: Draft) -> None:
    _store[draft.id] = draft


def claim(draft_id: str) -> Draft | None:
    """Atomic pop-to-claim: removes and returns the draft, or None if already gone."""
    return _store.pop(draft_id, None)


def new_id() -> str:
    return uuid.uuid4().hex
