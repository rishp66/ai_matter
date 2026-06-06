import httpx
from bridge import config
from bridge.drafts import Draft

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


def post_card(user_id: str, draft: Draft) -> dict:
    dm = _client.post("/api/v4/channels/direct", json=[config.MM_BOT_USER_ID, user_id])
    dm.raise_for_status()
    dm_channel_id = dm.json()["id"]
    resp = _client.post("/api/v4/posts", json={
        "channel_id": dm_channel_id,
        "message": "",
        "props": {
            "attachments": [
                {
                    "title": f"Held · {draft.reason}",
                    "text": draft.reply,
                    "actions": [
                        {
                            "name": "Approve",
                            "integration": {
                                "url": f"{config.BRIDGE_BASE_URL}/aegis/approve",
                                "context": {"draft_id": draft.id},
                            },
                        },
                        {
                            "name": "Discard",
                            "integration": {
                                "url": f"{config.BRIDGE_BASE_URL}/aegis/discard",
                                "context": {"draft_id": draft.id},
                            },
                        },
                    ],
                }
            ]
        },
    })
    resp.raise_for_status()
    return resp.json()


def post_ephemeral_draft(user_id: str, channel_id: str, draft_id: str) -> dict:
    """Post a custom_aegis_draft ephemeral into the channel, visible only to user_id."""
    resp = _client.post("/api/v4/posts/ephemeral", json={
        "user_id": user_id,
        "post": {
            "channel_id": channel_id,
            "message": "",
            "type": "custom_aegis_draft",
            "props": {"draft_id": draft_id},
        },
    })
    resp.raise_for_status()
    return resp.json()


def post_thread_notice(channel_id: str, root_id: str, text: str) -> dict:
    resp = _client.post("/api/v4/posts", json={
        "channel_id": channel_id,
        "root_id": root_id,
        "message": text,
    })
    resp.raise_for_status()
    return resp.json()
