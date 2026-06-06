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

from bridge import graphn_control_client
from bridge.graphn_control_client import list_documents, upload_document, delete_document, _ctrl_client


def _mock_response(status=200, data=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data if data is not None else []
    m.raise_for_status = MagicMock()
    return m


def test_list_documents():
    docs = [{"id": "doc1", "filename": "file.txt"}]
    mock_resp = _mock_response(200, docs)
    with patch.object(_ctrl_client, "get", return_value=mock_resp) as mock_get:
        result = list_documents("kb-abc")
        url = mock_get.call_args[0][0]
        assert "kb-abc" in url
        assert "ws_test" in url
        assert result == docs


def test_upload_document():
    doc_meta = {"id": "new-doc", "filename": "test.txt"}
    mock_resp = _mock_response(201, doc_meta)
    mock_resp.raise_for_status = MagicMock()
    with patch.object(_ctrl_client, "post", return_value=mock_resp) as mock_post:
        result = upload_document("kb-abc", "test.txt", b"hello", "text/plain")
        url = mock_post.call_args[0][0]
        assert "kb-abc" in url
        kwargs = mock_post.call_args[1]
        assert "files" in kwargs
        assert "file" in kwargs["files"]
        assert result == doc_meta


def test_delete_document():
    mock_resp = _mock_response(204, None)
    mock_resp.raise_for_status = MagicMock()
    with patch.object(_ctrl_client, "delete", return_value=mock_resp) as mock_delete:
        result = delete_document("kb-abc", "doc-999")
        url = mock_delete.call_args[0][0]
        assert "kb-abc" in url
        assert "doc-999" in url
        assert result is None


def test_auth_headers():
    assert "Authorization" in _ctrl_client.headers
    assert "X-Workspace-ID" in _ctrl_client.headers
    assert _ctrl_client.headers["Authorization"] == "Bearer fake-key"
    assert _ctrl_client.headers["X-Workspace-ID"] == "ws_test"
