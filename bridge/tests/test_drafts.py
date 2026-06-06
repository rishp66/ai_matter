import os
os.environ.setdefault("MM_BOT_TOKEN", "fake-token")
os.environ.setdefault("MM_BOT_USER_ID", "fake-bot-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "fake-channel")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://fake")
os.environ.setdefault("GRAPHN_API_KEY", "fake-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from bridge import drafts
from bridge.drafts import Draft


def _make_draft(draft_id: str = "abc123") -> Draft:
    return Draft(
        id=draft_id,
        reply="Here is the answer.",
        target_channel_id="ch-1",
        root_id="root-1",
        reason="referenced 2 private sources",
        provenance=["doc-a", "doc-b"],
        trigger_text="What is my salary?",
    )


def test_put_then_claim_returns_draft():
    drafts._store.clear()
    d = _make_draft("id1")
    drafts.put(d)
    claimed = drafts.claim("id1")
    assert claimed == d


def test_claim_removes_from_store():
    drafts._store.clear()
    drafts.put(_make_draft("id2"))
    drafts.claim("id2")
    assert drafts.claim("id2") is None  # second claim → None (atomic pop-to-claim)


def test_claim_unknown_id_returns_none():
    drafts._store.clear()
    assert drafts.claim("nonexistent") is None


def test_new_id_returns_nonempty_string():
    nid = drafts.new_id()
    assert isinstance(nid, str) and len(nid) > 0


def test_new_id_unique():
    assert drafts.new_id() != drafts.new_id()
