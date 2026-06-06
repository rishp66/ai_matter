import pytest
from unittest.mock import patch, MagicMock

# Patch env before importing mm_client (which imports config)
import os
os.environ.setdefault("MM_BOT_TOKEN", "test-token")
os.environ.setdefault("MM_BOT_USER_ID", "bot-user-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "demo-ch")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://graphn.test")
os.environ.setdefault("GRAPHN_API_KEY", "test-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from bridge.mm_client import post_reply, post_dm


def _mock_response(status=201, data=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data or {"id": "post_1"}
    return m


def test_post_reply_sends_correct_payload():
    with patch("bridge.mm_client._client") as mock_client:
        mock_client.post.return_value = _mock_response()
        post_reply(channel_id="c1", root_id="r1", text="hello")
        payload = mock_client.post.call_args[1]["json"]
        assert payload["channel_id"] == "c1"
        assert payload["root_id"] == "r1"
        assert payload["message"] == "hello"


def test_post_reply_calls_posts_endpoint():
    with patch("bridge.mm_client._client") as mock_client:
        mock_client.post.return_value = _mock_response()
        post_reply(channel_id="c1", root_id="r1", text="hi")
        url = mock_client.post.call_args[0][0]
        assert url == "/api/v4/posts"


def test_post_dm_creates_dm_channel_then_posts():
    with patch("bridge.mm_client._client") as mock_client:
        mock_client.post.side_effect = [
            _mock_response(data={"id": "dm_ch"}),
            _mock_response(data={"id": "dm_post"}),
        ]
        post_dm(user_id="u1", text="held")
        assert mock_client.post.call_count == 2
        first_url = mock_client.post.call_args_list[0][0][0]
        assert "direct" in first_url


def test_post_card_has_two_actions(monkeypatch):
    """post_card sends an attachment with exactly 2 actions."""
    from bridge.drafts import Draft
    from bridge import mm_client, config

    draft = Draft(
        id="d1",
        reply="The answer is 42.",
        target_channel_id="ch-x",
        root_id="root-x",
        reason="referenced 1 private source",
        provenance=[],
        trigger_text="What?",
    )

    mock_client = MagicMock()
    mock_client.post.side_effect = [
        MagicMock(status_code=201, json=lambda: {"id": "dm-chan-1"}),  # /channels/direct
        MagicMock(status_code=201, json=lambda: {"id": "post-1"}),    # /posts
    ]
    monkeypatch.setattr(mm_client, "_client", mock_client)

    mm_client.post_card(user_id="user-1", draft=draft)

    # second call is the card post
    _, kwargs = mock_client.post.call_args_list[1]
    body = kwargs["json"]
    actions = body["props"]["attachments"][0]["actions"]
    assert len(actions) == 2


def test_post_card_action_urls(monkeypatch):
    """Both actions point to the correct bridge endpoints."""
    from bridge.drafts import Draft
    from bridge import mm_client, config

    draft = Draft(
        id="d2",
        reply="...",
        target_channel_id="ch-x",
        root_id="root-x",
        reason="referenced 2 private sources",
        provenance=[],
        trigger_text="?",
    )

    mock_client = MagicMock()
    mock_client.post.side_effect = [
        MagicMock(status_code=201, json=lambda: {"id": "dm-chan-2"}),
        MagicMock(status_code=201, json=lambda: {"id": "post-2"}),
    ]
    monkeypatch.setattr(mm_client, "_client", mock_client)

    mm_client.post_card(user_id="user-2", draft=draft)

    _, kwargs = mock_client.post.call_args_list[1]
    body = kwargs["json"]
    actions = body["props"]["attachments"][0]["actions"]
    urls = [a["integration"]["url"] for a in actions]
    assert any("approve" in u for u in urls)
    assert any("discard" in u for u in urls)


def test_post_card_context_has_draft_id(monkeypatch):
    """Each action's context includes the draft_id."""
    from bridge.drafts import Draft
    from bridge import mm_client

    draft = Draft(
        id="my-draft-id",
        reply="...",
        target_channel_id="ch",
        root_id="root",
        reason="r",
        provenance=[],
        trigger_text="t",
    )

    mock_client = MagicMock()
    mock_client.post.side_effect = [
        MagicMock(status_code=201, json=lambda: {"id": "dm-chan-3"}),
        MagicMock(status_code=201, json=lambda: {"id": "post-3"}),
    ]
    monkeypatch.setattr(mm_client, "_client", mock_client)

    mm_client.post_card(user_id="u", draft=draft)

    _, kwargs = mock_client.post.call_args_list[1]
    body = kwargs["json"]
    actions = body["props"]["attachments"][0]["actions"]
    for a in actions:
        assert a["integration"]["context"]["draft_id"] == "my-draft-id"


def test_post_thread_notice_sends_to_posts(monkeypatch):
    """post_thread_notice POSTs to /api/v4/posts with root_id."""
    from bridge import mm_client

    mock_client = MagicMock()
    mock_client.post.return_value = MagicMock(
        status_code=201, json=lambda: {"id": "notice-post-1"}
    )
    monkeypatch.setattr(mm_client, "_client", mock_client)

    mm_client.post_thread_notice("ch-1", "root-1", "⏸ Paused.")

    _, kwargs = mock_client.post.call_args
    assert kwargs["json"]["root_id"] == "root-1"
    assert kwargs["json"]["channel_id"] == "ch-1"
    assert "⏸" in kwargs["json"]["message"]
