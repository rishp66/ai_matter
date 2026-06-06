import asyncio
from bridge import ws_client, mm_client
from bridge.models import Message


async def handle_message(msg: Message) -> None:
    root = msg.root_id or msg.id
    mm_client.post_reply(
        channel_id=msg.channel_id,
        root_id=root,
        text=f"[echo] {msg.text}",
    )


async def main() -> None:
    print("AEGIS bridge starting — echo mode")
    await ws_client.listen(handle_message)


if __name__ == "__main__":
    asyncio.run(main())
