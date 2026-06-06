# Bridge Structural Issues — Sprint 1 (P1–P3)

> **Raised:** 2026-06-06
> **Context:** Bridge code produced during AEGIS Sprint 1 (echo loop, WebSocket parser, REST client, GraphN client, gate). These are architectural problems that should be addressed before P4 (approval card) or will compound as the bridge grows.

---

## 🔴 CRITICAL

### Issue #1 — Sync HTTP clients block asyncio event loop

**Files:** `bridge/mm_client.py`, `bridge/graphn_client.py`

**Problem:** Both files use `httpx.Client` (synchronous). They are called from `async def handle_message()` in `main.py`, which runs inside the asyncio event loop alongside the WebSocket listener. Every HTTP call to Mattermost or GraphN blocks the entire event loop. If a GraphN workflow takes 30s, the WebSocket receives zero events during that window — potentially missing messages or triggering the server heartbeat timeout.

**Fix:** Either:
- Switch to `httpx.AsyncClient` in both files and `await` all calls (preferred — keeps everything in the same event loop).
- Run blocking calls via `asyncio.to_thread()` or a `ThreadPoolExecutor`.

**Impact:** Reliability, correctness under load.

---

### Issue #2 — No error handling; upstream failure kills the bridge

**Files:** `bridge/gate.py`, `bridge/main.py`, `bridge/graphn_client.py`, `bridge/mm_client.py`

**Problem:** `gate.decide()` calls `graphn_client.run_workflow()` with no try/except. Any HTTP error (500, timeout, connection refused) propagates through `handle_message()` → `ws_client.listen()` and crashes the WebSocket connection. The bridge dies on the first upstream error. Similarly, `mm_client.post_reply` / `post_dm` errors are unhandled.

**Observed risk paths:**
1. GraphN gateway returns 5xx → bridge dead
2. GraphN workflow takes >30s → httpx timeout → bridge dead
3. Mattermost server restarts between parse and reply → bridge dead
4. Bot token revoked while bridge is running → bridge dead on next post

**Fix:** Wrap all upstream calls in `handle_message()` with try/except. Log errors with context (message ID, which stage failed). The bridge should survive individual message failures.

**Impact:** Correctness. The bridge is a single point of failure with no resilience.

---

### Issue #3 — No WebSocket reconnection logic

**File:** `bridge/ws_client.py`

**Problem:** `ws_client.listen()` opens one connection and exits on any disconnect. If Mattermost restarts, there's a network blip, or the server drops the connection (e.g., heartbeat timeout), the bridge dies permanently.

**Fix:** Add a reconnect loop with exponential backoff and a max retry cap:

```python
async def listen(on_message, max_retries=10):
    backoff = 1
    while True:
        try:
            await _connect_and_listen(on_message)
            backoff = 1  # reset on clean disconnect
        except Exception as e:
            logger.error("ws disconnected: %s, reconnecting in %ds", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
```

**Impact:** Reliability. The bridge must survive server restarts.

---

## 🟡 HIGH

### Issue #4 — No graceful shutdown

**Files:** `bridge/main.py`, `bridge/ws_client.py`

**Problem:** No SIGINT/SIGTERM handler. Ctrl+C kills the bridge mid-operation. The WebSocket doesn't send a close frame, and in-flight GraphN/workflow calls are abandoned.

**Fix:** Register signal handlers that set an `asyncio.Event`. The listen loop and any in-flight tasks should check the event and drain gracefully.

**Impact:** Operability. Dirty shutdowns leave the server unaware the bot disconnected.

---

### Issue #5 — No structured logging

**Files:** all bridge modules

**Problem:** Only `print()` statements. No timestamps, no log levels, no correlation IDs. When tracking a message through the pipeline (WebSocket → parse → gate → reply/DM), there's no way to connect log lines. Debugging a held-draft routing error requires guesswork.

**Fix:** Add `logging` module with:
- Timestamps and log levels (INFO/DEBUG/WARNING/ERROR)
- A correlation ID (message ID) threaded through every handler
- `logger.debug("message %s: public workflow %s -> grounded=%s confidence=%.2f", ...)` in gate
- `logger.error("message %s: graphn timeout after %.1fs", ...)` for failures

**Impact:** Observability. Impossible to debug end-to-end without it.

---

### Issue #6 — Config failures are cryptic

**File:** `bridge/config.py`

**Problem:** `os.environ["KEY"]` raises `KeyError` with no context. A missing `.env` file or incomplete `.env` gives `KeyError: 'GRAPHN_GATEWAY_URL'` at import time — no hint about which variable, where to set it, or how to fix it.

**Fix:**
```python
_REQUIRED = {
    "MM_BOT_TOKEN": "bot personal access token from Mattermost",
    "GRAPHN_GATEWAY_URL": "GraphN gateway base URL",
    ...
}
_MISSING = [k for k in _REQUIRED if k not in os.environ]
if _MISSING:
    raise SystemExit(f"Missing env vars: {', '.join(_MISSING)}\n"
                     f"Copy bridge/.env.example to bridge/.env and fill in values.")
```

**Impact:** Developer experience. First-run errors should be self-documenting.

---

## 🟡 MEDIUM

### Issue #7 — Empty `reply` in bot-origin draft verdict

**Files:** `bridge/gate.py`, `bridge/main.py`

**Problem:** When `gate.decide()` hits a bot-origin message, it returns `Verdict(kind=DRAFT, reason="bot origin", reply="")`. `main.py` formats this as `(held) bot origin\n\n---\n` — a DM with no body after the separator. The user gets a confusing empty message.

**Fix:** Either set a fallback reply (`"Another bot sent this message. No action taken."`) or check for empty reply in `main.py` before sending the DM.

**Impact:** UX. Confusing empty DM in testing.

---

### Issue #8 — `MM_DEMO_CHANNEL_ID` in config but unused

**Files:** `bridge/config.py`, `bridge/.env.example`

**Problem:** `MM_DEMO_CHANNEL_ID` is required in `config.py` but never referenced by any bridge code. Either it's a forward-plan item that should be documented, or it's accreted cruft. If it's for future use (P4 channel scoping?), that intent should be stated.

**Fix:** Either remove it or add a comment explaining which future phase will use it.

**Impact:** Maintainability. Dead config misleads future developers.

---

## 🔵 FORWARD-LOOKING

### Issue #9 — No FastAPI scaffold (blocker for P4)

**Files:** none yet

**Problem:** `requirements.txt` includes `fastapi` and `uvicorn` but there is no FastAPI server. P4 requires HTTP endpoints (`/aegis/approve`, `/aegis/discard`) for interactive message action buttons. The bridge currently has only a WebSocket listener — there's no HTTP server at all.

**Fix:** Add a FastAPI app in `main.py` (or a separate `bridge/server.py`) that runs alongside the WebSocket listener. The app needs:
- `POST /aegis/approve` — accepts the interaction payload, posts the stored reply to the target channel
- `POST /aegis/discard` — updates the card to "Discarded"

Both endpoints must run in the same process as the WebSocket listener (they share the config and MM client). Use `uvicorn` with `asyncio` and integrate with the existing event loop.

**Impact:** P4 cannot start without this.

---

## Issue #10 — Inconsistent test environment setup

**Files:** `bridge/tests/test_*.py`

**Problem:** Three different patterns for setting up test env vars:
- `test_ws_client.py` — `patch.dict("os.environ", {...})`
- `test_gate.py` — `os.environ.setdefault(...)`
- `test_mm_client.py` — `os.environ.setdefault(...)`

No shared `conftest.py` or test fixtures. If a new required env var is added to `config.py`, every test file must be updated independently.

**Fix:** Create `bridge/tests/conftest.py` with a session-scoped fixture that patches all required env vars:
```python
@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    for key in ("MM_BOT_TOKEN", "GRAPHN_GATEWAY_URL", ...):
        monkeypatch.setenv(key, f"test-{key.lower()}")
```

**Impact:** Test maintainability. Already diverging across 4 test files.

---

## Summary

| # | Severity | Area | Blocks |
|---|----------|------|--------|
| 1 | Critical | Sync HTTP in async loop | All subsequent phases |
| 2 | Critical | No error handling | Reliability |
| 3 | Critical | No WS reconnection | Reliability |
| 4 | High | No graceful shutdown | Operability |
| 5 | High | No structured logging | Debugging |
| 6 | High | Cryptic config errors | First-run experience |
| 7 | Medium | Empty draft reply | UX polish |
| 8 | Medium | Dead config | Maintainability |
| 9 | Info | No FastAPI scaffold | P4 |
| 10 | Info | Test setup divergence | Test maintenance |
