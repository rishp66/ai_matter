async def run(answer: str, search: dict, **kwargs) -> dict:
    text = (answer or "").strip()
    if not text:
        text = "I don't have enough information to answer that right now."

    return {
        "text": text,
        "grounded": bool(search.get("grounded", False)),
        "confidence": float(search.get("confidence", 0.0) or 0.0),
        "sources": list(search.get("sources", []) or []),
        "private_hits": int(search.get("private_hits", 0) or 0),
    }
