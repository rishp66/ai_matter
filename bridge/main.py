import asyncio
from bridge import ws_client, mm_client, gate
from bridge.models import Message, VerdictKind


async def handle_message(msg: Message) -> None:
    verdict = gate.decide(msg)

    if verdict.kind == VerdictKind.AUTO_SEND:
        root = msg.root_id or msg.id
        mm_client.post_reply(
            channel_id=msg.channel_id,
            root_id=root,
            text=verdict.reply,
        )
    else:
        held_text = f"(held) {verdict.reason}\n\n---\n{verdict.reply}"
        mm_client.post_dm(user_id=msg.user_id, text=held_text)


async def main() -> None:
    print("AEGIS bridge starting — gate mode")
    await ws_client.listen(handle_message)


if __name__ == "__main__":
    asyncio.run(main())
