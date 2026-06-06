import httpx
from bridge import config
from bridge.models import GraphNResult

_client = httpx.Client(
    headers={
        "Authorization": f"Bearer {config.GRAPHN_API_KEY}",
        "Content-Type": "application/json",
    },
    timeout=120.0,
)


def run_workflow(workflow_id: str, query: str) -> GraphNResult:
    url = f"{config.GRAPHN_GATEWAY_URL}/v1/{config.GRAPHN_WORKSPACE_ID}/{workflow_id}/sync"
    resp = _client.post(url, json={"input": {"query": query}})
    resp.raise_for_status()
    result = resp.json()["output"]["result"]
    return GraphNResult(
        text=result["text"],
        grounded=result["grounded"],
        confidence=result["confidence"],
        sources=result.get("sources", []),
        private_hits=result.get("private_hits", 0),
    )
