import os
os.environ.setdefault("MM_BOT_TOKEN", "fake-token")
os.environ.setdefault("MM_BOT_USER_ID", "fake-bot-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "fake-channel")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://fake")
os.environ.setdefault("GRAPHN_API_KEY", "fake-key")
os.environ.setdefault("GRAPHN_WORKSPACE_ID", "ws_test")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

import time
import pytest
from unittest.mock import patch, MagicMock
import bridge.mm_auth as mm_auth


def _mock_resp(status_code: int, json_data: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    monkeypatch.setattr(mm_auth, "_cache", {})


def test_200_returns_user_id():
    mock_resp = _mock_resp(200, {"id": "user-abc"})
    with patch("httpx.get", return_value=mock_resp):
        result = mm_auth.verify("tok1")
    assert result == "user-abc"


def test_401_raises_value_error():
    mock_resp = _mock_resp(401, {})
    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(ValueError):
            mm_auth.verify("bad-tok")


def test_cache_hit_skips_second_call():
    mock_resp = _mock_resp(200, {"id": "user-xyz"})
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        mm_auth.verify("tok2")
        mm_auth.verify("tok2")
    mock_get.assert_called_once()


def test_cache_miss_after_ttl():
    mock_resp = _mock_resp(200, {"id": "user-ttl"})
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        mm_auth.verify("tok3")
        # force expiry
        mm_auth._cache["tok3"] = ("user-ttl", time.monotonic() - 1)
        mm_auth.verify("tok3")
    assert mock_get.call_count == 2
