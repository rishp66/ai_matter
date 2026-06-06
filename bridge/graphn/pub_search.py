from foundry_helpers import kb

RERANKER_MODEL = "bge-reranker-v2-m3"
KB_PUBLIC = "kb_9477dfac3a3a"
CONF_MIN = 0.65


def _format_context(results: list) -> tuple[str, list[str]]:
    parts: list[str] = []
    sources: list[str] = []
    for result in results[:5]:
        source = result.get("source", result.get("document_id", ""))
        text = result.get("text", result.get("content", "")).strip()
        if not text:
            continue
        sources.append(source)
        parts.append(f"[{source}]\n{text}")
    return "\n\n".join(parts), sources


async def run(query: str, **kwargs) -> dict:
    results = await kb.search(KB_PUBLIC, query, top_k=5, reranker_model=RERANKER_MODEL)
    if not results:
        return {
            "context": "",
            "grounded": False,
            "confidence": 0.0,
            "sources": [],
            "private_hits": 0,
        }

    top = results[0]
    confidence = round(float(top.get("score", 0.0)), 3)
    grounded = confidence >= CONF_MIN
    context, sources = _format_context(results)

    return {
        "context": context,
        "grounded": grounded,
        "confidence": confidence,
        "sources": sources,
        "private_hits": 0,
    }
