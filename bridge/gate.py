from bridge import config, graphn_client
from bridge.models import Message, Verdict, VerdictKind


def decide(msg: Message) -> Verdict:
    if msg.is_from_bot:
        return Verdict(kind=VerdictKind.DRAFT, reason="bot origin")

    pub = graphn_client.run_workflow(
        workflow_id=config.GRAPHN_WF_PUBLIC,
        query=msg.text,
    )

    if pub.grounded and pub.confidence >= config.CONF_MIN:
        return Verdict(
            kind=VerdictKind.AUTO_SEND,
            reply=pub.text,
            provenance=pub.sources,
        )

    priv = graphn_client.run_workflow(
        workflow_id=config.GRAPHN_WF_PRIVATE,
        query=msg.text,
    )
    return Verdict(
        kind=VerdictKind.DRAFT,
        reply=priv.text,
        reason=f"referenced {priv.private_hits} private sources",
    )
