import os
os.environ.setdefault("MM_BOT_TOKEN", "fake-token")
os.environ.setdefault("MM_BOT_USER_ID", "fake-bot-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "fake-channel")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://fake")
os.environ.setdefault("GRAPHN_API_KEY", "fake-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

import pytest
from pathlib import Path

from bridge import drafts, persistence
from bridge.drafts import Draft


def _make_draft(draft_id: str = "persist-1") -> Draft:
    return Draft(
        id=draft_id,
        reply="Persisted answer.",
        target_channel_id="ch-p",
        root_id="root-p",
        reason="test persistence",
        provenance=["doc-x"],
        trigger_text="Persist this?",
        owner_user_id="user-42",
        contexts=[{"key": "val"}],
    )


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect _STATE_FILE to a temp path and clear the in-memory store."""
    state_file = tmp_path / "drafts.json"
    monkeypatch.setattr(drafts, "_STATE_FILE", state_file)
    drafts._store.clear()
    yield state_file
    drafts._store.clear()


def test_put_persists_to_disk(isolated_state):
    d = _make_draft("p1")
    drafts.put(d)

    on_disk = persistence.load(isolated_state, {})
    assert "p1" in on_disk
    assert on_disk["p1"]["reply"] == "Persisted answer."
    assert on_disk["p1"]["owner_user_id"] == "user-42"
    assert on_disk["p1"]["contexts"] == [{"key": "val"}]


def test_claim_removes_from_disk(isolated_state):
    d = _make_draft("p2")
    drafts.put(d)

    claimed = drafts.claim("p2")
    assert claimed is not None

    on_disk = persistence.load(isolated_state, {})
    assert "p2" not in on_disk


def test_claim_nonexistent_leaves_disk_unchanged(isolated_state):
    d = _make_draft("p3")
    drafts.put(d)

    result = drafts.claim("nonexistent")
    assert result is None

    on_disk = persistence.load(isolated_state, {})
    assert "p3" in on_disk


def test_corrupt_json_falls_back_gracefully(isolated_state):
    isolated_state.write_text("{ this is not valid json }")
    data = persistence.load(isolated_state, {})
    assert data == {}


def test_list_for_owner_returns_only_matching_drafts(isolated_state):
    drafts._store.clear()
    d1 = _make_draft("o1")
    d2 = Draft(
        id="o2",
        reply="other",
        target_channel_id="ch",
        root_id="r",
        reason="r",
        provenance=[],
        trigger_text="t",
        owner_user_id="user-99",
        contexts=[],
    )
    drafts.put(d1)
    drafts.put(d2)

    results = drafts.list_for_owner("user-42")
    assert len(results) == 1
    assert results[0].id == "o1"


def test_list_for_owner_empty_when_no_match(isolated_state):
    drafts._store.clear()
    drafts.put(_make_draft("q1"))
    assert drafts.list_for_owner("nobody") == []
