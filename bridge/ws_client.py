import asyncio
import json
import websockets
from bridge import config
from bridge.models import Message

_WS_URL = (
    config.MM_URL.replace("http://", "ws://").replace("https://", "wss://")
    + "/api/v4/websocket"
)


def parse_posted_event(event: dict) -> Message | None:
    if event.get("event") != "posted":
        return None
    post = json.loads(event["data"]["post"])
    if post.get("type", "") != "":
        return None
    props = post.get("props", {})
    return Message(
        id=post["id"],
        channel_id=post["channel_id"],
        root_id=post.get("root_id", ""),
        user_id=post["user_id"],
        text=post["message"],
        is_from_bot=props.get("from_bot") == "true",
    )


async def listen(on_message):
    async with websockets.connect(_WS_URL) as ws:
        await ws.send(json.dumps({
            "seq": 1,
            "action": "authentication_challenge",
            "data": {"token": config.MM_BOT_TOKEN},
        }))
        async for raw in ws:
            event = json.loads(raw)
            msg = parse_posted_event(event)
            if msg is None or msg.user_id == config.MM_BOT_USER_ID:
                continue
            await on_message(msg)
