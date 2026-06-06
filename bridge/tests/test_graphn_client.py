import pytest
import httpx
from unittest.mock import patch, MagicMock
import os

os.environ.setdefault("MM_BOT_TOKEN", "test-token")
os.environ.setdefault("MM_BOT_USER_ID", "bot-user-id")
os.environ.setdefault("MM_DEMO_CHANNEL_ID", "demo-ch")
os.environ.setdefault("GRAPHN_GATEWAY_URL", "http://graphn.test")
os.environ.setdefault("GRAPHN_API_KEY", "test-key")
os.environ.setdefault("GRAPHN_WF_PUBLIC", "wf-pub")
os.environ.setdefault("GRAPHN_WF_PRIVATE", "wf-priv")

from bridge.graphn_client import run_workflow
from bridge.models import GraphNResult

_MOCK_RESPONSE = {
    "text": "Office hours are Mon/Wed 2-4pm.",
    "grounded": True,
    "confidence": 0.92,
    "sources": ["chunk_001"],
    "private_hits": 0,
}


def _mock_ok(data=None):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = data or _MOCK_RESPONSE
    return m


def test_returns_graphn_result():
    with patch("bridge.graphn_client._client") as mock_client:
        mock_client.post.return_value = _mock_ok()
        result = run_workflow(workflow_id="wf-public", query="When are office hours?")
    assert isinstance(result, GraphNResult)
    assert result.grounded is True
    assert result.confidence == 0.92
    assert result.private_hits == 0


def test_workflow_id_appears_in_url():
    with patch("bridge.graphn_client._client") as mock_client:
        mock_client.post.return_value = _mock_ok()
        run_workflow(workflow_id="wf-abc", query="test")
        url = mock_client.post.call_args[0][0]
        assert "wf-abc" in url


def test_query_sent_in_body():
    with patch("bridge.graphn_client._client") as mock_client:
        mock_client.post.return_value = _mock_ok()
        run_workflow(workflow_id="wf-pub", query="What is my salary?")
        payload = mock_client.post.call_args[1]["json"]
        assert payload["query"] == "What is my salary?"


def test_raises_on_gateway_error():
    with patch("bridge.graphn_client._client") as mock_client:
        err_resp = MagicMock(status_code=500)
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        mock_client.post.return_value = err_resp
        with pytest.raises(httpx.HTTPStatusError):
            run_workflow(workflow_id="wf-pub", query="test")
