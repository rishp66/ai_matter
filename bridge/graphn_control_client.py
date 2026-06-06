import httpx
from bridge import config

_ctrl_client = httpx.Client(
    base_url=config.GRAPHN_URL,
    headers={
        "Authorization": f"Bearer {config.GRAPHN_API_KEY}",
        "X-Workspace-ID": config.GRAPHN_WORKSPACE_ID,
    },
    timeout=30.0,
)


def _kb_url(kb_id: str) -> str:
    return f"/v1/{config.GRAPHN_WORKSPACE_ID}/knowledgebases/{kb_id}/documents"


def list_documents(kb_id: str) -> list[dict]:
    resp = _ctrl_client.get(_kb_url(kb_id))
    resp.raise_for_status()
    return resp.json()


def upload_document(kb_id: str, filename: str, content: bytes, content_type: str) -> dict:
    resp = _ctrl_client.post(
        _kb_url(kb_id),
        files={"file": (filename, content, content_type)},
    )
    resp.raise_for_status()
    return resp.json()


def delete_document(kb_id: str, doc_id: str) -> None:
    resp = _ctrl_client.delete(f"{_kb_url(kb_id)}/{doc_id}")
    resp.raise_for_status()
