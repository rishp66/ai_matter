from foundry_helpers import kb

RERANKER_MODEL = "bge-reranker-v2-m3"
KB_PUBLIC = "kb_9477dfac3a3a"
KB_PRIVATE = "kb_98e21d17afdd"
CONF_MIN = 0.5


def _format_context(tagged: list) -> tuple[str, list[str], int]:
    parts: list[str] = []
    sources: list[str] = []
    private_hits = 0
    for item in tagged[:5]:
        result = item["r"]
        is_private = item["private"]
        if is_private:
            private_hits += 1
        source = result.get("source", result.get("document_id", ""))
        text = result.get("text", result.get("content", "")).strip()
        if not text:
            continue
        sources.append(source)
        label = "private" if is_private else "public"
        parts.append(f"[{label}:{source}]\n{text}")
    return "\n\n".join(parts), sources, private_hits


async def run(query: str, **kwargs) -> dict:
    pub_results = await kb.search(KB_PUBLIC, query, top_k=5, reranker_model=RERANKER_MODEL)
    priv_results = await kb.search(KB_PRIVATE, query, top_k=5, reranker_model=RERANKER_MODEL)

    tagged = [{"r": r, "private": False} for r in pub_results] + [
        {"r": r, "private": True} for r in priv_results
    ]
    tagged.sort(key=lambda x: float(x["r"].get("score", 0) or 0), reverse=True)

    top5 = tagged[:5]
    if not top5:
        return {
            "context": "",
            "grounded": False,
            "confidence": 0.0,
            "sources": [],
            "private_hits": 0,
        }

    top = top5[0]["r"]
    confidence = round(float(top.get("score", 0.0) or 0), 3)
    grounded = confidence >= CONF_MIN
    context, sources, private_hits = _format_context(top5)

    return {
        "context": context,
        "grounded": grounded,
        "confidence": confidence,
        "sources": sources,
        "private_hits": private_hits,
    }
