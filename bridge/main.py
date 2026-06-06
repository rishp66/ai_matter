import asyncio
import uvicorn
from bridge import config, ws_client, mm_client, gate, drafts, loopguard
from bridge.drafts import Draft
from bridge.models import Message, VerdictKind
from bridge.server import app


async def handle_message(msg: Message) -> None:
    root = msg.root_id or msg.id
    # Layer 2: loop guard (Layer 1 is inside gate.decide)
    if loopguard.record_turn(root, msg.is_from_bot):
        mm_client.post_thread_notice(msg.channel_id, root, "⏸ Paused — human turn needed.")
        return
    # gate.decide is sync+blocking (GraphN round-trip); run it in a thread
    verdict = await asyncio.to_thread(gate.decide, msg)
    if verdict.kind == VerdictKind.AUTO_SEND:
        mm_client.post_reply(msg.channel_id, root, verdict.reply)
    else:
        draft = Draft(
            id=drafts.new_id(),
            reply=verdict.reply,
            target_channel_id=msg.channel_id,
            root_id=root,
            reason=verdict.reason,
            provenance=verdict.provenance,
            trigger_text=msg.text,
        )
        drafts.put(draft)
        mm_client.post_card(msg.user_id, draft)


async def main() -> None:
    print("AEGIS bridge starting — gate + approval card + loop guard")
    server = uvicorn.Server(uvicorn.Config(
        app,
        host=config.BRIDGE_HOST,
        port=config.BRIDGE_PORT,
        log_level="info",
        lifespan="off",
    ))
    ws_task = asyncio.create_task(ws_client.listen(handle_message), name="ws")
    http_task = asyncio.create_task(server.serve(), name="http")
    done, pending = await asyncio.wait(
        {ws_task, http_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    server.should_exit = True
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for t in done:
        if not t.cancelled() and t.exception():
            raise t.exception()


if __name__ == "__main__":
    asyncio.run(main())
