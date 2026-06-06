import pytest
from unittest.mock import patch, MagicMock

# Patch env before importing mm_client (which imports config)
import os
os.environ.setdefault("MM_BOT_TOKEN", "test-token")
os.environ.setdefault("MM_BOT_USER_ID", "bot-user-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "demo-ch")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://graphn.test")
os.environ.setdefault("GRAPHN_API_KEY", "test-key")
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
