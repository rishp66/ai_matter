import httpx
from bridge import config

_client = httpx.Client(
    base_url=config.MM_URL,
    headers={"Authorization": f"Bearer {config.MM_BOT_TOKEN}"},
    timeout=10.0,
)


def post_reply(channel_id: str, root_id: str, text: str) -> dict:
    resp = _client.post("/api/v4/posts", json={
        "channel_id": channel_id,
        "root_id": root_id,
        "message": text,
    })
    resp.raise_for_status()
    return resp.json()


def post_dm(user_id: str, text: str) -> dict:
    dm = _client.post("/api/v4/channels/direct", json=[config.MM_BOT_USER_ID, user_id])
    dm.raise_for_status()
    dm_channel_id = dm.json()["id"]
    resp = _client.post("/api/v4/posts", json={"channel_id": dm_channel_id, "message": text})
    resp.raise_for_status()
    return resp.json()
