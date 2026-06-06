import httpx
from bridge import config
from bridge.models import GraphNResult

_client = httpx.Client(
    headers={
        "Authorization": f"Bearer {config.GRAPHN_API_KEY}",
        "Content-Type": "application/json",
    },
    timeout=30.0,
)


def run_workflow(workflow_id: str, query: str) -> GraphNResult:
    url = f"{config.GRAPHN_GATEWAY_URL}/v1/workflows/{workflow_id}/run"
    resp = _client.post(url, json={"query": query})
    resp.raise_for_status()
    data = resp.json()
    return GraphNResult(
        text=data["text"],
        grounded=data["grounded"],
        confidence=data["confidence"],
        sources=data.get("sources", []),
        private_hits=data.get("private_hits", 0),
    )
