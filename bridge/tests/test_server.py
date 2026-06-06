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
from bridge import drafts, mm_client, graphn_control_client
from bridge.drafts import Draft
from bridge.server import app, get_user_id

# Override auth dependency for all tests in this module
app.dependency_overrides[get_user_id] = lambda: "test-user"

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    """Clear draft store before each test to avoid pollution."""
    drafts._store.clear()
    yield
    drafts._store.clear()


def _seed_draft(draft_id: str = "draft-abc") -> Draft:
    d = Draft(
        id=draft_id,
        reply="The answer is 42.",
        target_channel_id="ch-target",
        root_id="root-post",
        reason="referenced 1 private source",
        provenance=["doc-1"],
        trigger_text="What is the answer?",
        owner_user_id="test-user",
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


def test_cors_preflight():
    resp = client.options(
        "/aegis/approve",
        headers={
            "Origin": "http://localhost:8065",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code in (200, 204)
    assert "access-control-allow-origin" in resp.headers


# --- GET /aegis/drafts ---

def test_list_drafts_returns_only_owner_drafts():
    app.dependency_overrides[get_user_id] = lambda: "alice"
    alice_draft = Draft(id="a1", reply="r", target_channel_id="ch", root_id="rt",
                        reason="r", provenance=[], trigger_text="q",
                        owner_user_id="alice", contexts=[])
    bob_draft = Draft(id="b1", reply="r", target_channel_id="ch", root_id="rt",
                      reason="r", provenance=[], trigger_text="q",
                      owner_user_id="bob", contexts=[])
    drafts.put(alice_draft)
    drafts.put(bob_draft)
    resp = client.get("/aegis/drafts", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert "a1" in ids
    assert "b1" not in ids
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_list_drafts_returns_empty_when_no_drafts():
    app.dependency_overrides[get_user_id] = lambda: "alice"
    resp = client.get("/aegis/drafts", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    assert resp.json() == []
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_list_drafts_response_shape():
    app.dependency_overrides[get_user_id] = lambda: "alice"
    d = Draft(id="shape1", reply="hello", target_channel_id="ch1", root_id="rt1",
              reason="test reason", provenance=["src1"], trigger_text="q?",
              owner_user_id="alice", contexts=["ctx"])
    drafts.put(d)
    resp = client.get("/aegis/drafts", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["id"] == "shape1"
    assert item["reply"] == "hello"
    assert item["reason"] == "test reason"
    assert item["provenance"] == ["src1"]
    assert item["contexts"] == ["ctx"]
    assert item["trigger_text"] == "q?"
    assert item["channel_id"] == "ch1"
    app.dependency_overrides[get_user_id] = lambda: "test-user"


# --- POST /aegis/send ---

def test_send_posts_user_text(monkeypatch):
    app.dependency_overrides[get_user_id] = lambda: "alice"
    d = Draft(id="s1", reply="bot-reply", target_channel_id="ch", root_id="rt",
              reason="r", provenance=[], trigger_text="q",
              owner_user_id="alice", contexts=[])
    drafts.put(d)
    monkeypatch.setattr(mm_client, "post_reply", lambda *a, **kw: {})
    resp = client.post("/aegis/send", json={"draft_id": "s1", "text": "my reply"},
                       headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    assert drafts.claim("s1") is None  # draft gone
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_send_rejects_wrong_owner(monkeypatch):
    app.dependency_overrides[get_user_id] = lambda: "bob"
    d = Draft(id="s2", reply="bot-reply", target_channel_id="ch", root_id="rt",
              reason="r", provenance=[], trigger_text="q",
              owner_user_id="alice", contexts=[])
    drafts.put(d)
    resp = client.post("/aegis/send", json={"draft_id": "s2", "text": "hack"},
                       headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 403
    assert drafts.claim("s2") is not None  # draft restored
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_send_already_handled():
    app.dependency_overrides[get_user_id] = lambda: "alice"
    resp = client.post("/aegis/send", json={"draft_id": "nonexistent", "text": "hi"},
                       headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    assert "Already handled" in resp.json()["update"]["message"]
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_send_restores_draft_on_post_failure(monkeypatch):
    from fastapi.testclient import TestClient as _TC
    _client = _TC(app, raise_server_exceptions=False)
    app.dependency_overrides[get_user_id] = lambda: "alice"
    d = Draft(id="s3", reply="bot-reply", target_channel_id="ch", root_id="rt",
              reason="r", provenance=[], trigger_text="q",
              owner_user_id="alice", contexts=[])
    drafts.put(d)
    monkeypatch.setattr(mm_client, "post_reply", MagicMock(side_effect=Exception("MM down")))
    resp = _client.post("/aegis/send", json={"draft_id": "s3", "text": "hi"},
                        headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 500
    assert drafts.claim("s3") is not None  # draft restored
    app.dependency_overrides[get_user_id] = lambda: "test-user"


# --- Ownership enforcement on approve/discard ---

def test_approve_rejects_wrong_owner():
    app.dependency_overrides[get_user_id] = lambda: "bob"
    d = Draft(id="own1", reply="r", target_channel_id="ch", root_id="rt",
              reason="r", provenance=[], trigger_text="q",
              owner_user_id="alice", contexts=[])
    drafts.put(d)
    resp = client.post("/aegis/approve",
                       json={"context": {"draft_id": "own1"}, "user_id": "bob"},
                       headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 403
    assert drafts.claim("own1") is not None  # draft restored
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_discard_rejects_wrong_owner():
    app.dependency_overrides[get_user_id] = lambda: "bob"
    d = Draft(id="own2", reply="r", target_channel_id="ch", root_id="rt",
              reason="r", provenance=[], trigger_text="q",
              owner_user_id="alice", contexts=[])
    drafts.put(d)
    resp = client.post("/aegis/discard",
                       json={"context": {"draft_id": "own2"}, "user_id": "bob"},
                       headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 403
    assert drafts.claim("own2") is not None  # draft restored
    app.dependency_overrides[get_user_id] = lambda: "test-user"


def test_discard_unknown_draft_returns_already_handled():
    resp = client.post("/aegis/discard", json={"context": {"draft_id": "gone"}})
    assert resp.status_code == 200
    assert "Already handled" in resp.json()["update"]["message"]


# --- KB routes ---

def test_list_kb_documents_public(monkeypatch):
    monkeypatch.setattr(graphn_control_client, "list_documents", lambda kb_id: [{"id": "doc1"}])
    resp = client.get("/aegis/kb/public/documents", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": "doc1"}]


def test_list_kb_documents_unknown_scope():
    resp = client.get("/aegis/kb/unknown/documents", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 404


def test_delete_kb_document(monkeypatch):
    monkeypatch.setattr(graphn_control_client, "delete_document", lambda kb_id, doc_id: None)
    resp = client.delete("/aegis/kb/public/documents/doc123", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 204


def test_upload_kb_document(monkeypatch):
    monkeypatch.setattr(graphn_control_client, "upload_document",
                        lambda kb_id, fn, content, ct: {"id": "new-doc", "filename": fn})
    resp = client.post(
        "/aegis/kb/public/documents",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "new-doc"
