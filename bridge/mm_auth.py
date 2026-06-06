import time
import httpx
from bridge import config

# cache: token -> (user_id, expires_at)
_cache: dict[str, tuple[str, float]] = {}
_TTL = 60.0  # seconds


def verify(token: str) -> str:
    """Verify MM session token; return user_id. Raises ValueError on invalid token."""
    now = time.monotonic()
    if token in _cache:
        user_id, exp = _cache[token]
        if now < exp:
            return user_id
    # call /users/me
    resp = httpx.get(
        f"{config.MM_URL}/api/v4/users/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5.0,
    )
    if resp.status_code == 401:
        _cache.pop(token, None)
        raise ValueError("invalid MM token")
    resp.raise_for_status()
    user_id = resp.json()["id"]
    _cache[token] = (user_id, now + _TTL)
    return user_id
