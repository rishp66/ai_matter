# AEGIS Sprint 2 (P4 + P5) — Approval Card + Loop Prevention

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make held drafts actionable (interactive Approve/Discard DM card) and add thread-level loop prevention.

**Architecture:** FastAPI HTTP server runs concurrently with the WebSocket listener on a single asyncio event loop (`asyncio.wait(FIRST_COMPLETED)` pattern). Mattermost calls back to `/aegis/approve` and `/aegis/discard` when the operator clicks a button. In-memory draft store keyed by UUID hex with atomic `pop`-to-claim prevents double-fire. Loop guard counts consecutive bot turns per thread and halts at N=3.

**Tech Stack:** Python 3.14, FastAPI 0.115, uvicorn 0.32, websockets 13.1, httpx 0.27 (sync), pydantic v2.

---

## Status: COMPLETE ✅

All 7 automated tasks implemented, reviewed, and committed. 44 tests passing.

---

## What Was Built

### New files

- **`bridge/drafts.py`** — `Draft` dataclass + `put`/`claim`/`new_id` in-memory store.
- **`bridge/loopguard.py`** — Per-thread consecutive bot-turn counter; `record_turn(root_id, is_from_bot) -> bool`; halts at `HALT_AT=3`.
- **`bridge/server.py`** — FastAPI app with `POST /aegis/approve` and `POST /aegis/discard` (sync handlers). Approve atomically claims the draft, sends to channel, returns card rewrite. Discard drops the draft. Both return Mattermost `{"update": ...}` shape. On MM failure, draft is re-put so the operator can retry.

### Modified files

- **`bridge/config.py`** — Added `BRIDGE_HOST`, `BRIDGE_PORT`, `BRIDGE_BASE_URL`.
- **`bridge/mm_client.py`** — Added `post_card(user_id, draft)` (interactive DM card with Approve/Discard buttons) and `post_thread_notice(channel_id, root_id, text)`.
- **`bridge/ws_client.py`** — Added `backoff_seconds(attempt, max_seconds=30)` helper; wrapped `listen` in `while True` reconnect loop (catches `ConnectionClosed`, `OSError`); wrapped `on_message` call to catch/log application errors without killing the listener.
- **`bridge/main.py`** — Full rewrite: concurrent uvicorn+WS via `asyncio.wait(FIRST_COMPLETED)`, `gate.decide` + all `mm_client` calls offloaded via `asyncio.to_thread`, loopguard check before gate, draft store + `post_card` on HOLD path.

---

## Commits (in order)

1. `feat(bridge): add BRIDGE_HOST/PORT/BASE_URL config vars`
2. `feat(bridge): add Draft dataclass and in-memory draft store (TDD)`
3. `feat(bridge): add post_card and post_thread_notice to mm_client (TDD)`
4. `feat(bridge): add FastAPI approve/discard endpoints (TDD)`
5. `feat(bridge): add WS reconnect/backoff to ws_client.listen`
6. `feat(bridge): add thread depth loop guard (TDD)`
7. `feat(bridge): wire P4+P5 into main — concurrent uvicorn+WS, approval card, loop guard`
8. `fix(bridge): wrap mm_client calls in to_thread, guard handle_message exceptions, restore draft on send failure`

---

## Manual Steps Remaining

### Task 8 — Confirm MM allows the callback

`AllowedUntrustedInternalConnections` was set to `"localhost 127.0.0.1"` in Sprint 1. That covers the default `BRIDGE_BASE_URL=http://localhost:8080`, so no change is expected. Confirm via:
- System Console → Environment → Developer → `AllowedUntrustedInternalConnections`, or
- `grep AllowedUntrustedInternalConnections mattermost/config/config.json`

If the bridge is moved off localhost, add the host there and restart.

### Task 9 — End-to-end demo

Start the bridge: `cd bridge && .venv/bin/python3 main.py`

**P4 — Approval loop:**
1. Post a private question in the demo channel.
2. Expect a DM **card** with Approve / Discard buttons and `Held · referenced N private sources` title.
3. Click **Approve** → reply appears in the original thread; card rewrites to `✓ Sent to channel.` (buttons gone).
4. Repeat, click **Discard** → card rewrites to `🗑 Discarded.`, nothing in channel.
5. Double-click (or re-POST same draft_id) → `_Already handled._` — never double-posts.
6. Public question → still auto-sends in-thread, no card.

**P5 — Loop guard:**
Generate 3+ consecutive bot turns in a thread. After turn 3, bridge posts `⏸ Paused — human turn needed.` and stops. A human reply resets the counter.

**Cleanup:** Ctrl-C → both HTTP and WS tasks tear down cleanly.
