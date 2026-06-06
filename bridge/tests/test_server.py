import os
os.environ.setdefault("MM_BOT_TOKEN", "fake-token")
os.environ.setdefault("MM_BOT_USER_ID", "fake-bot-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "fake-channel")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://fake")
os.environ.setdefault("GRAPHN_API_KEY", "fake-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from bridge import drafts, mm_client
from bridge.drafts import Draft
from bridge.server import app

client = TestClient(app)


def _seed_draft(draft_id: str = "draft-abc") -> Draft:
    drafts._store.clear()
    d = Draft(
        id=draft_id,
        reply="The answer is 42.",
        target_channel_id="ch-target",
        root_id="root-post",
        reason="referenced 1 private source",
        provenance=["doc-1"],
        trigger_text="What is the answer?",
        owner_user_id="user-1",
        contexts=[],
    )
    drafts.put(d)
    return d


def test_approve_posts_reply_and_returns_sent():
    d = _seed_draft("d1")
    with patch.object(mm_client, "post_reply", return_value={}) as mock_reply:
        resp = client.post("/aegis/approve", json={
            "context": {"draft_id": "d1"},
            "user_id": "u1", "post_id": "p1",
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "Sent" in body["update"]["message"]
    mock_reply.assert_called_once_with(
        channel_id="ch-target", root_id="root-post", text="The answer is 42."
    )


def test_approve_draft_no_longer_claimable_after_approve():
    _seed_draft("d2")
    with patch.object(mm_client, "post_reply", return_value={}):
        client.post("/aegis/approve", json={"context": {"draft_id": "d2"}})
    assert drafts.claim("d2") is None  # draft consumed


def test_approve_unknown_draft_returns_already_handled():
    drafts._store.clear()
    with patch.object(mm_client, "post_reply", return_value={}) as mock_reply:
        resp = client.post("/aegis/approve", json={"context": {"draft_id": "gone"}})
    assert resp.status_code == 200
    assert "Already handled" in resp.json()["update"]["message"]
    mock_reply.assert_not_called()


def test_discard_returns_discarded_and_does_not_post():
    _seed_draft("d3")
    with patch.object(mm_client, "post_reply", return_value={}) as mock_reply:
        resp = client.post("/aegis/discard", json={"context": {"draft_id": "d3"}})
    assert resp.status_code == 200
    assert "Discarded" in resp.json()["update"]["message"]
    mock_reply.assert_not_called()


def test_discard_removes_draft():
    _seed_draft("d4")
    with patch.object(mm_client, "post_reply", return_value={}):
        client.post("/aegis/discard", json={"context": {"draft_id": "d4"}})
    assert drafts.claim("d4") is None


def test_approve_restores_draft_if_post_reply_fails():
    """If post_reply raises, draft is restored so the user can retry."""
    from fastapi.testclient import TestClient as _TC
    _client = _TC(app, raise_server_exceptions=False)
    _seed_draft("d5")
    with patch.object(mm_client, "post_reply", side_effect=Exception("MM down")):
        resp = _client.post("/aegis/approve", json={"context": {"draft_id": "d5"}})
    assert resp.status_code == 500
    # draft must be back in the store so user can retry
    assert drafts.claim("d5") is not None
