# AEGIS Sprint 1 (P0–P3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boot a local Mattermost fork, wire a Python bridge that echoes messages via WebSocket, connect GraphN knowledge bases and workflows, then implement the public-first/escalate-lock gate so public questions auto-send and private questions surface as "(held)" DMs.

**Architecture:** The bridge is a standalone Python service that subscribes to Mattermost WebSocket `posted` events, calls the GraphN gateway for retrieval, applies the gate decision (public-first → AUTO_SEND, private escalation → DRAFT), and either posts replies to the channel thread or sends a "(held)" DM. No Go server code is written in this sprint — the fork is configured via `server/config/config.json` only.

**Tech Stack:** Go 1.26.3 (Mattermost server), Node 24 (webapp), Python 3.12+ (bridge), FastAPI 0.115, websockets 13, httpx 0.27, pytest 8, pytest-asyncio 0.24, python-dotenv 1.0, GraphN CLI

---

## File Map

**Created (bridge service):**
- `bridge/__init__.py`
- `bridge/config.py`
- `bridge/models.py`
- `bridge/graphn_client.py`
- `bridge/gate.py`
- `bridge/mm_client.py`
- `bridge/ws_client.py`
- `bridge/main.py`
- `bridge/tests/__init__.py`
- `bridge/tests/test_gate.py`
- `bridge/tests/test_graphn_client.py`
- `bridge/tests/test_mm_client.py`
- `bridge/tests/test_ws_client.py`
- `bridge/requirements.txt`
- `bridge/.env.example`
- `bridge/pytest.ini`

**Modified (Mattermost fork config):**
- `server/config/config.json` — enable bots, user access tokens, allowed internal connections

---

### Task 1: Verify toolchain (P0)

**Files:** none — verification only

- [ ] **Step 1: Check Go**
  ```bash
  go version
  ```
  Expected: `go version go1.26.x`. If missing: install from https://go.dev/dl/

- [ ] **Step 2: Check Node**
  ```bash
  node --version
  ```
  Expected: `v24.x.x`. If missing: `nvm install 24 && nvm use 24`

- [ ] **Step 3: Check Docker and make**
  ```bash
  docker --version && make --version
  ```
  Expected: Docker 27+, GNU Make 3.81+

- [ ] **Step 4: Check Python**
  ```bash
  python3 --version
  ```
  Expected: `Python 3.12.x` or later. If missing: `brew install python@3.12`

---

### Task 2: Boot Mattermost server (P0)

**Files:** none

- [ ] **Step 1: Start the server (first run pulls Docker images and compiles — expect 5-10 minutes)**
  ```bash
  cd server && make run
  ```
  Expected: `Server is listening on :8065` in the terminal.

- [ ] **Step 2: Create the admin account**
  ```bash
  cd server && bin/mmctl user create --local \
    --email admin@aegis.local \
    --username admin \
    --password 'AegisAdmin1!' \
    --system-admin
  ```
  Expected: `Created user admin`

- [ ] **Step 3: Verify login in browser**
  Open http://localhost:8065. Log in as `admin / AegisAdmin1!`.
  Expected: Mattermost dashboard loads.

---

### Task 3: Create demo team and channel (P0)

**Files:** none

- [ ] **Step 1: Create demo team**
  ```bash
  cd server && bin/mmctl team create --local \
    --name aegis-demo \
    --display-name "AEGIS Demo" \
    --email admin@aegis.local
  ```
  Expected: `Created team aegis-demo`

- [ ] **Step 2: Create demo channel**
  ```bash
  cd server && bin/mmctl channel create --local \
    --team aegis-demo \
    --name demo \
    --display-name "Demo Channel" \
    --type O
  ```
  Expected: `Created channel demo`

- [ ] **Step 3: Note the channel ID — needed for bridge config later**
  ```bash
  cd server && bin/mmctl channel list --local aegis-demo
  ```
  Expected: lists `demo` with its channel ID (format: 26-char alphanumeric). Save it as `MM_DEMO_CHANNEL_ID`.

- [ ] **Step 4: Commit**
  ```bash
  git add server/config/
  git commit -m "chore: P0 — Mattermost boots; demo team + channel created"
  ```

  **P0 DONE WHEN:** You can log into http://localhost:8065, see the AEGIS Demo team, and post in Demo Channel.

---

### Task 4: Configure Mattermost for AEGIS (P1)

**Files:** Modify `server/config/config.json`

- [ ] **Step 1: Find the relevant settings**
  ```bash
  grep -n "EnableBotAccountCreation\|EnableUserAccessTokens\|AllowedUntrustedInternalConnections" server/config/config.json
  ```
  Expected: prints the current values (likely `false` / `""`)

- [ ] **Step 2: Update config.json — find the `ServiceSettings` block and set these three keys**
  ```json
  "EnableBotAccountCreation": true,
  "EnableUserAccessTokens": true,
  "AllowedUntrustedInternalConnections": "localhost 127.0.0.1"
  ```

- [ ] **Step 3: Restart the server**
  Ctrl-C in the `make run` terminal, then:
  ```bash
  cd server && make run
  ```
  Expected: server restarts cleanly at `:8065`

- [ ] **Step 4: Verify bot creation is now enabled**
  ```bash
  curl -s 'http://localhost:8065/api/v4/config/client?format=old' \
    | python3 -c "import sys,json; c=json.load(sys.stdin); print(c.get('EnableBotAccountCreation'))"
  ```
  Expected: `true`

- [ ] **Step 5: Commit**
  ```bash
  git add server/config/config.json
  git commit -m "chore: P1 — enable bot accounts, user access tokens, allowed internal connections"
  ```

---

### Task 5: Create bot account (P1)

**Files:** none — API calls; values go into `bridge/.env`

- [ ] **Step 1: Get admin auth token**
  ```bash
  TOKEN=$(curl -si http://localhost:8065/api/v4/users/login \
    -H "Content-Type: application/json" \
    -d '{"login_id":"admin","password":"AegisAdmin1!"}' \
    | grep -i "^token:" | awk '{print $2}' | tr -d '\r')
  echo "Admin token: $TOKEN"
  ```
  Expected: prints a non-empty token string

- [ ] **Step 2: Create the bot account**
  ```bash
  BOT=$(curl -s http://localhost:8065/api/v4/bots \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"username":"aegis-bot","display_name":"AEGIS","description":"AEGIS personal agent"}')
  echo $BOT | python3 -m json.tool
  ```
  Expected: JSON object with `"user_id"` and `"username": "aegis-bot"`. Copy `user_id` — this is `MM_BOT_USER_ID`.

- [ ] **Step 3: Create a personal access token for the bot**
  ```bash
  BOT_USER_ID="<paste user_id from step 2>"
  PAT=$(curl -s "http://localhost:8065/api/v4/users/$BOT_USER_ID/tokens" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"description":"aegis-bridge"}')
  echo $PAT | python3 -m json.tool
  ```
  Expected: JSON with `"token"`. Copy `token` — this is `MM_BOT_TOKEN`.

- [ ] **Step 4: Add bot to Demo Channel**
  ```bash
  CHANNEL_ID="<paste MM_DEMO_CHANNEL_ID from Task 3 Step 3>"
  curl -s "http://localhost:8065/api/v4/channels/$CHANNEL_ID/members" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$BOT_USER_ID\"}"
  ```
  Expected: `{"channel_id": "...", "user_id": "..."}`

---

### Task 6: Bridge project scaffolding (P1)

**Files:**
- Create: `bridge/requirements.txt`
- Create: `bridge/.env.example`
- Create: `bridge/pytest.ini`
- Create: `bridge/__init__.py`
- Create: `bridge/tests/__init__.py`
- Create: `bridge/config.py`

- [ ] **Step 1: Create directory structure**
  ```bash
  mkdir -p bridge/tests
  touch bridge/__init__.py bridge/tests/__init__.py
  ```

- [ ] **Step 2: Write `bridge/requirements.txt`**
  ```
  fastapi==0.115.5
  uvicorn[standard]==0.32.1
  websockets==13.1
  httpx==0.27.2
  pytest==8.3.3
  pytest-asyncio==0.24.0
  python-dotenv==1.0.1
  ```

- [ ] **Step 3: Install dependencies**
  ```bash
  cd bridge && python3 -m pip install -r requirements.txt
  ```
  Expected: all packages install, no errors

- [ ] **Step 4: Write `bridge/pytest.ini`**
  ```ini
  [pytest]
  asyncio_mode = auto
  testpaths = tests
  ```

- [ ] **Step 5: Write `bridge/.env.example`**
  ```
  MM_URL=http://localhost:8065
  MM_BOT_TOKEN=<bot personal access token from Task 5 Step 3>
  MM_BOT_USER_ID=<bot user_id from Task 5 Step 2>
  MM_DEMO_CHANNEL_ID=<demo channel id from Task 3 Step 3>
  GRAPHN_GATEWAY_URL=<graphn gateway base URL>
  GRAPHN_API_KEY=<graphn api key>
  GRAPHN_WF_PUBLIC=<public workflow id — fill after Task 12>
  GRAPHN_WF_PRIVATE=<private workflow id — fill after Task 12>
  CONF_MIN=0.7
  ```
  Copy to `bridge/.env` and fill in the values you have so far (MM_ fields).

- [ ] **Step 6: Write `bridge/config.py`**
  ```python
  import os
  from dotenv import load_dotenv

  load_dotenv()

  MM_URL: str = os.getenv("MM_URL", "http://localhost:8065")
  MM_BOT_TOKEN: str = os.environ["MM_BOT_TOKEN"]
  MM_BOT_USER_ID: str = os.environ["MM_BOT_USER_ID"]
  MM_DEMO_CHANNEL_ID: str = os.environ["MM_DEMO_CHANNEL_ID"]
  GRAPHN_GATEWAY_URL: str = os.environ["GRAPHN_GATEWAY_URL"]
  GRAPHN_API_KEY: str = os.environ["GRAPHN_API_KEY"]
  GRAPHN_WF_PUBLIC: str = os.environ["GRAPHN_WF_PUBLIC"]
  GRAPHN_WF_PRIVATE: str = os.environ["GRAPHN_WF_PRIVATE"]
  CONF_MIN: float = float(os.getenv("CONF_MIN", "0.7"))
  ```

- [ ] **Step 7: Verify pytest runs with empty suite**
  ```bash
  cd bridge && python3 -m pytest
  ```
  Expected: `no tests ran` or `0 passed`

- [ ] **Step 8: Commit**
  ```bash
  git add bridge/
  git commit -m "feat: P1 — bridge project scaffolding (deps, config, test harness)"
  ```

---

### Task 7: Message models (P1)

**Files:**
- Create: `bridge/models.py`

- [ ] **Step 1: Write `bridge/models.py`**
  ```python
  from dataclasses import dataclass, field
  from enum import Enum


  class VerdictKind(str, Enum):
      AUTO_SEND = "AUTO_SEND"
      DRAFT = "DRAFT"


  @dataclass
  class Message:
      id: str
      channel_id: str
      root_id: str
      user_id: str
      text: str
      is_from_bot: bool


  @dataclass
  class GraphNResult:
      text: str
      grounded: bool
      confidence: float
      sources: list[str]
      private_hits: int = 0


  @dataclass
  class Verdict:
      kind: VerdictKind
      reply: str = ""
      reason: str = ""
      provenance: list[str] = field(default_factory=list)
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add bridge/models.py
  git commit -m "feat: P1 — Message, GraphNResult, Verdict dataclasses"
  ```

---

### Task 8: WebSocket event parsing + tests (P1)

**Files:**
- Create: `bridge/tests/test_ws_client.py`
- Create: `bridge/ws_client.py`

- [ ] **Step 1: Write failing tests in `bridge/tests/test_ws_client.py`**
  ```python
  import json
  import pytest
  from bridge.ws_client import parse_posted_event
  from bridge.models import Message


  def make_post(**overrides) -> str:
      base = {
          "id": "p1",
          "channel_id": "c1",
          "root_id": "",
          "user_id": "u1",
          "message": "hello",
          "type": "",
          "props": {},
      }
      return json.dumps({**base, **overrides})


  def make_event(post_json: str) -> dict:
      return {"event": "posted", "data": {"post": post_json}}


  def test_parses_human_post():
      msg = parse_posted_event(make_event(make_post()))
      assert msg is not None
      assert msg.text == "hello"
      assert msg.is_from_bot is False
      assert msg.channel_id == "c1"
      assert msg.user_id == "u1"


  def test_marks_bot_post_as_from_bot():
      post_json = make_post(props={"from_bot": "true"})
      msg = parse_posted_event(make_event(post_json))
      assert msg is not None
      assert msg.is_from_bot is True


  def test_returns_none_for_non_posted_event():
      assert parse_posted_event({"event": "channel_viewed", "data": {}}) is None


  def test_returns_none_for_system_message():
      post_json = make_post(type="system_join_channel")
      assert parse_posted_event(make_event(post_json)) is None


  def test_root_id_preserved():
      post_json = make_post(root_id="r1")
      msg = parse_posted_event(make_event(post_json))
      assert msg.root_id == "r1"
  ```

- [ ] **Step 2: Run tests — must fail**
  ```bash
  cd bridge && python3 -m pytest tests/test_ws_client.py -v
  ```
  Expected: `ModuleNotFoundError: bridge.ws_client` or similar import error

- [ ] **Step 3: Write `bridge/ws_client.py`**
  ```python
  import asyncio
  import json
  import websockets
  from bridge import config
  from bridge.models import Message

  _WS_URL = (
      config.MM_URL.replace("http://", "ws://").replace("https://", "wss://")
      + "/api/v4/websocket"
  )


  def parse_posted_event(event: dict) -> Message | None:
      if event.get("event") != "posted":
          return None
      post = json.loads(event["data"]["post"])
      if post.get("type", "") != "":
          return None
      props = post.get("props", {})
      return Message(
          id=post["id"],
          channel_id=post["channel_id"],
          root_id=post.get("root_id", ""),
          user_id=post["user_id"],
          text=post["message"],
          is_from_bot=props.get("from_bot") == "true",
      )


  async def listen(on_message):
      async with websockets.connect(_WS_URL) as ws:
          await ws.send(json.dumps({
              "seq": 1,
              "action": "authentication_challenge",
              "data": {"token": config.MM_BOT_TOKEN},
          }))
          async for raw in ws:
              event = json.loads(raw)
              msg = parse_posted_event(event)
              if msg is None or msg.user_id == config.MM_BOT_USER_ID:
                  continue
              await on_message(msg)
  ```
  Note: `listen` skips posts where `user_id == MM_BOT_USER_ID` (self-echo). The gate separately handles other bots via `is_from_bot`.

- [ ] **Step 4: Run tests — must pass**
  ```bash
  cd bridge && python3 -m pytest tests/test_ws_client.py -v
  ```
  Expected: `5 passed`

- [ ] **Step 5: Commit**
  ```bash
  git add bridge/ws_client.py bridge/tests/test_ws_client.py
  git commit -m "feat: P1 — WebSocket event parser with 5 tests"
  ```

---

### Task 9: Mattermost REST client + tests (P1)

**Files:**
- Create: `bridge/tests/test_mm_client.py`
- Create: `bridge/mm_client.py`

- [ ] **Step 1: Write failing tests in `bridge/tests/test_mm_client.py`**
  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from bridge.mm_client import post_reply, post_dm


  def _mock_response(status=201, data=None):
      m = MagicMock()
      m.status_code = status
      m.json.return_value = data or {"id": "post_1"}
      return m


  def test_post_reply_sends_correct_payload():
      with patch("bridge.mm_client._client") as mock_client:
          mock_client.post.return_value = _mock_response()
          post_reply(channel_id="c1", root_id="r1", text="hello")
          payload = mock_client.post.call_args[1]["json"]
          assert payload["channel_id"] == "c1"
          assert payload["root_id"] == "r1"
          assert payload["message"] == "hello"


  def test_post_reply_calls_posts_endpoint():
      with patch("bridge.mm_client._client") as mock_client:
          mock_client.post.return_value = _mock_response()
          post_reply(channel_id="c1", root_id="r1", text="hi")
          url = mock_client.post.call_args[0][0]
          assert url == "/api/v4/posts"


  def test_post_dm_creates_dm_channel_then_posts():
      with patch("bridge.mm_client._client") as mock_client:
          mock_client.post.side_effect = [
              _mock_response(data={"id": "dm_ch"}),
              _mock_response(data={"id": "dm_post"}),
          ]
          post_dm(user_id="u1", text="held")
          assert mock_client.post.call_count == 2
          first_url = mock_client.post.call_args_list[0][0][0]
          assert "direct" in first_url
  ```

- [ ] **Step 2: Run tests — must fail**
  ```bash
  cd bridge && python3 -m pytest tests/test_mm_client.py -v
  ```
  Expected: `ModuleNotFoundError: bridge.mm_client`

- [ ] **Step 3: Write `bridge/mm_client.py`**
  ```python
  import httpx
  from bridge import config

  _client = httpx.Client(
      base_url=config.MM_URL,
      headers={"Authorization": f"Bearer {config.MM_BOT_TOKEN}"},
      timeout=10.0,
  )


  def post_reply(channel_id: str, root_id: str, text: str) -> dict:
      resp = _client.post("/api/v4/posts", json={
          "channel_id": channel_id,
          "root_id": root_id,
          "message": text,
      })
      resp.raise_for_status()
      return resp.json()


  def post_dm(user_id: str, text: str) -> dict:
      dm = _client.post("/api/v4/channels/direct", json=[config.MM_BOT_USER_ID, user_id])
      dm.raise_for_status()
      dm_channel_id = dm.json()["id"]
      resp = _client.post("/api/v4/posts", json={"channel_id": dm_channel_id, "message": text})
      resp.raise_for_status()
      return resp.json()
  ```

- [ ] **Step 4: Run tests — must pass**
  ```bash
  cd bridge && python3 -m pytest tests/test_mm_client.py -v
  ```
  Expected: `3 passed`

- [ ] **Step 5: Commit**
  ```bash
  git add bridge/mm_client.py bridge/tests/test_mm_client.py
  git commit -m "feat: P1 — Mattermost REST client (post_reply, post_dm) with 3 tests"
  ```

---

### Task 10: Echo wiring (P1)

**Files:**
- Create: `bridge/main.py`

- [ ] **Step 1: Write `bridge/main.py`**
  ```python
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
  ```

- [ ] **Step 2: Start the bridge**
  ```bash
  cd bridge && python3 main.py
  ```
  Expected: `AEGIS bridge starting — echo mode` with no errors

- [ ] **Step 3: Manual E2E verification**
  In the Mattermost browser tab, post `hello` in Demo Channel.
  Expected: within ~1 second, aegis-bot replies `[echo] hello` in the same thread.

- [ ] **Step 4: Verify no self-echo loop**
  The bot's reply must not trigger a second reply. Watch the terminal — there should be no second `handle_message` invocation after the bot posts.

- [ ] **Step 5: Commit**
  ```bash
  git add bridge/main.py
  git commit -m "feat: P1 — echo loop complete; bot replies in-thread within 1s"
  ```

  **P1 DONE WHEN:** Post in Demo Channel → bot replies in-thread within ~1 second, no self-echo loop.

---

### Task 11: GraphN workspace + KBs (P2)

**Files:** none — CLI setup only

- [ ] **Step 1: Initialize GraphN workspace**
  ```bash
  graphn init
  ```
  Enter API key when prompted. Then verify:
  ```bash
  graphn whoami
  ```
  Expected: prints workspace name and user info.

- [ ] **Step 2: Create kb-public**
  ```bash
  graphn kb create kb-public
  ```
  Expected: `Created knowledge base kb-public`

- [ ] **Step 3: Ingest public demo corpus**
  Create `/tmp/public-corpus.txt`:
  ```
  Office hours are Monday and Wednesday from 2pm to 4pm in Room 101.
  Team lunch is every Friday at noon in the main cafeteria.
  The project roadmap is available on the shared drive under /docs/roadmap.
  Onboarding guide: complete the HR checklist in your first week.
  ```
  Ingest:
  ```bash
  graphn kb ingest kb-public /tmp/public-corpus.txt
  ```
  Expected: confirms ingestion (chunk count or byte count)

- [ ] **Step 4: Create kb-private**
  ```bash
  graphn kb create kb-private
  ```
  Expected: `Created knowledge base kb-private`

- [ ] **Step 5: Ingest private demo corpus**
  Create `/tmp/private-corpus.txt`:
  ```
  My annual salary is $120,000 plus a 15% bonus target.
  The secret project codename is Nebula, launching in Q3 2026.
  Personal note: I plan to resign in December if the promotion doesn't come through.
  The unreleased acquisition target is Acme Corp.
  ```
  Ingest:
  ```bash
  graphn kb ingest kb-private /tmp/private-corpus.txt
  ```
  Expected: confirms ingestion

- [ ] **Step 6: Verify both KBs**
  ```bash
  graphn kb list
  ```
  Expected: shows both `kb-public` and `kb-private`

---

### Task 12: GraphN workflows + gateway (P2)

**Files:** `bridge/.env` — fill in workflow IDs and gateway URL after publish

- [ ] **Step 1: List available blueprints**
  ```bash
  graphn blueprint list
  ```
  Expected: lists blueprints. Identify the basic RAG blueprint name.

- [ ] **Step 2: Scaffold wf-public (kb-public only)**
  ```bash
  graphn scaffold --blueprint <rag-blueprint-name> --name wf-public
  ```
  Open the generated workflow file and set its KB list to `[kb-public]` only. Save.

- [ ] **Step 3: Dry-run wf-public against a public question**
  ```bash
  graphn workflow dry-run wf-public --input '{"query": "When are office hours?"}'
  ```
  Expected: response includes office hours text. Note the exact JSON field names for grounded, confidence, sources, and private_hits — update `graphn_client.py` in Task 13 if they differ from the assumed names.

- [ ] **Step 4: Scaffold wf-private (kb-public + kb-private)**
  ```bash
  graphn scaffold --blueprint <rag-blueprint-name> --name wf-private
  ```
  Open and set KB list to `[kb-public, kb-private]`. Save.

- [ ] **Step 5: Dry-run wf-private against a private question**
  ```bash
  graphn workflow dry-run wf-private --input '{"query": "What is my salary?"}'
  ```
  Expected: response includes salary info; sources or a `private_hits` field should indicate a kb-private chunk was used.

- [ ] **Step 6: Publish both workflows**
  ```bash
  graphn workflow publish wf-public  --message "public-only compose"
  graphn workflow publish wf-private --message "escalated compose — locks DRAFT"
  ```
  Expected: each prints a workflow ID. Copy both.

- [ ] **Step 7: Update bridge/.env**
  ```
  GRAPHN_GATEWAY_URL=<base URL printed by graphn init or graphn config show>
  GRAPHN_WF_PUBLIC=<wf-public id from step 6>
  GRAPHN_WF_PRIVATE=<wf-private id from step 6>
  ```

---

### Task 13: GraphN client + tests (P2)

**Files:**
- Create: `bridge/tests/test_graphn_client.py`
- Create: `bridge/graphn_client.py`

**Assumed:** Gateway endpoint is `POST {GRAPHN_GATEWAY_URL}/v1/workflows/{workflow_id}/run` with `Authorization: Bearer {GRAPHN_API_KEY}` and JSON body `{"query": "..."}`. Response: `{"text": "...", "grounded": true, "confidence": 0.92, "sources": [...], "private_hits": 0}`. **Verify these field names and URL path against actual GraphN docs and update if they differ.**

- [ ] **Step 1: Write failing tests in `bridge/tests/test_graphn_client.py`**
  ```python
  import pytest
  import httpx
  from unittest.mock import patch, MagicMock
  from bridge.graphn_client import run_workflow
  from bridge.models import GraphNResult

  _MOCK_RESPONSE = {
      "text": "Office hours are Mon/Wed 2-4pm.",
      "grounded": True,
      "confidence": 0.92,
      "sources": ["chunk_001"],
      "private_hits": 0,
  }


  def _mock_ok(data=None):
      m = MagicMock()
      m.status_code = 200
      m.json.return_value = data or _MOCK_RESPONSE
      return m


  def test_returns_graphn_result():
      with patch("bridge.graphn_client._client") as mock_client:
          mock_client.post.return_value = _mock_ok()
          result = run_workflow(workflow_id="wf-public", query="When are office hours?")
      assert isinstance(result, GraphNResult)
      assert result.grounded is True
      assert result.confidence == 0.92
      assert result.private_hits == 0


  def test_workflow_id_appears_in_url():
      with patch("bridge.graphn_client._client") as mock_client:
          mock_client.post.return_value = _mock_ok()
          run_workflow(workflow_id="wf-abc", query="test")
          url = mock_client.post.call_args[0][0]
          assert "wf-abc" in url


  def test_query_sent_in_body():
      with patch("bridge.graphn_client._client") as mock_client:
          mock_client.post.return_value = _mock_ok()
          run_workflow(workflow_id="wf-pub", query="What is my salary?")
          payload = mock_client.post.call_args[1]["json"]
          assert payload["query"] == "What is my salary?"


  def test_raises_on_gateway_error():
      with patch("bridge.graphn_client._client") as mock_client:
          err_resp = MagicMock(status_code=500)
          err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
              "Server error", request=MagicMock(), response=MagicMock(status_code=500)
          )
          mock_client.post.return_value = err_resp
          with pytest.raises(httpx.HTTPStatusError):
              run_workflow(workflow_id="wf-pub", query="test")
  ```

- [ ] **Step 2: Run tests — must fail**
  ```bash
  cd bridge && python3 -m pytest tests/test_graphn_client.py -v
  ```
  Expected: `ModuleNotFoundError: bridge.graphn_client`

- [ ] **Step 3: Write `bridge/graphn_client.py`**
  ```python
  import httpx
  from bridge import config
  from bridge.models import GraphNResult

  _client = httpx.Client(
      headers={
          "Authorization": f"Bearer {config.GRAPHN_API_KEY}",
          "Content-Type": "application/json",
      },
      timeout=30.0,
  )


  def run_workflow(workflow_id: str, query: str) -> GraphNResult:
      url = f"{config.GRAPHN_GATEWAY_URL}/v1/workflows/{workflow_id}/run"
      resp = _client.post(url, json={"query": query})
      resp.raise_for_status()
      data = resp.json()
      return GraphNResult(
          text=data["text"],
          grounded=data["grounded"],
          confidence=data["confidence"],
          sources=data.get("sources", []),
          private_hits=data.get("private_hits", 0),
      )
  ```
  If the dry-run in Task 12 showed different field names, update the `data["..."]` lookups to match.

- [ ] **Step 4: Run tests — must pass**
  ```bash
  cd bridge && python3 -m pytest tests/test_graphn_client.py -v
  ```
  Expected: `4 passed`

- [ ] **Step 5: Live gateway smoke test**
  ```bash
  cd bridge && python3 -c "
  from dotenv import load_dotenv; load_dotenv()
  from bridge.graphn_client import run_workflow
  import os
  r = run_workflow(os.environ['GRAPHN_WF_PUBLIC'], 'When are office hours?')
  print(r)
  "
  ```
  Expected: `GraphNResult(text='...office hours...', grounded=True, confidence=..., private_hits=0)`

- [ ] **Step 6: Commit**
  ```bash
  git add bridge/graphn_client.py bridge/tests/test_graphn_client.py
  git commit -m "feat: P2 — GraphN client with gateway integration and 4 tests"
  ```

  **P2 DONE WHEN:** A public query returns grounded from kb-public; a private query surfaces a kb-private chunk — both callable by the bridge.

---

### Task 14: Gate logic + tests (P3)

**Files:**
- Create: `bridge/tests/test_gate.py`
- Create: `bridge/gate.py`

- [ ] **Step 1: Write failing tests in `bridge/tests/test_gate.py`**
  ```python
  import pytest
  from unittest.mock import patch
  from bridge.gate import decide
  from bridge.models import Message, VerdictKind, GraphNResult


  def msg(**overrides) -> Message:
      base = dict(
          id="p1", channel_id="c1", root_id="", user_id="u1",
          text="When are office hours?", is_from_bot=False,
      )
      return Message(**{**base, **overrides})


  def pub_ok(confidence=0.9) -> GraphNResult:
      return GraphNResult(
          text="Office hours Mon/Wed 2-4pm.", grounded=True,
          confidence=confidence, sources=["chunk_001"], private_hits=0,
      )


  def pub_miss() -> GraphNResult:
      return GraphNResult(
          text="", grounded=False, confidence=0.1, sources=[], private_hits=0,
      )


  def priv_ok(private_hits=1) -> GraphNResult:
      return GraphNResult(
          text="Your salary is $120k.", grounded=True,
          confidence=0.95, sources=["pub_c", "priv_c"], private_hits=private_hits,
      )


  def test_bot_origin_forces_draft_without_calling_graphn():
      m = msg(is_from_bot=True)
      with patch("bridge.gate.graphn_client.run_workflow") as mock_run:
          verdict = decide(m)
      assert verdict.kind == VerdictKind.DRAFT
      assert verdict.reason == "bot origin"
      mock_run.assert_not_called()


  def test_auto_send_when_public_grounded_and_confident():
      with patch("bridge.gate.graphn_client.run_workflow", return_value=pub_ok()):
          verdict = decide(msg())
      assert verdict.kind == VerdictKind.AUTO_SEND
      assert verdict.reply == "Office hours Mon/Wed 2-4pm."


  def test_draft_when_public_not_grounded():
      with patch("bridge.gate.graphn_client.run_workflow",
                 side_effect=[pub_miss(), priv_ok()]):
          verdict = decide(msg(text="What is my salary?"))
      assert verdict.kind == VerdictKind.DRAFT
      assert "1 private sources" in verdict.reason


  def test_draft_when_public_confidence_below_threshold():
      with patch("bridge.gate.graphn_client.run_workflow",
                 side_effect=[pub_ok(confidence=0.3), priv_ok()]):
          verdict = decide(msg(text="What is in my notes?"))
      assert verdict.kind == VerdictKind.DRAFT


  def test_private_escalation_calls_both_workflows():
      with patch("bridge.gate.graphn_client.run_workflow",
                 side_effect=[pub_miss(), priv_ok(private_hits=2)]) as mock_run:
          decide(msg(text="Tell me my salary"))
      assert mock_run.call_count == 2


  def test_auto_send_calls_only_public_workflow():
      with patch("bridge.gate.graphn_client.run_workflow",
                 return_value=pub_ok()) as mock_run:
          decide(msg())
      assert mock_run.call_count == 1


  def test_provenance_attached_on_auto_send():
      with patch("bridge.gate.graphn_client.run_workflow", return_value=pub_ok()):
          verdict = decide(msg())
      assert verdict.provenance == ["chunk_001"]
  ```

- [ ] **Step 2: Run tests — must fail**
  ```bash
  cd bridge && python3 -m pytest tests/test_gate.py -v
  ```
  Expected: `ModuleNotFoundError: bridge.gate`

- [ ] **Step 3: Write `bridge/gate.py`**
  ```python
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
  ```

- [ ] **Step 4: Run tests — must pass**
  ```bash
  cd bridge && python3 -m pytest tests/test_gate.py -v
  ```
  Expected: `7 passed`

- [ ] **Step 5: Run full test suite**
  ```bash
  cd bridge && python3 -m pytest -v
  ```
  Expected: all tests from all four test files pass

- [ ] **Step 6: Commit**
  ```bash
  git add bridge/gate.py bridge/tests/test_gate.py
  git commit -m "feat: P3 — gate logic (public-first/escalate-lock) with 7 tests"
  ```

---

### Task 15: Wire gate into bridge (P3)

**Files:** Modify `bridge/main.py`

- [ ] **Step 1: Replace echo handler with gate routing**
  ```python
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
  ```

- [ ] **Step 2: Start the bridge**
  ```bash
  cd bridge && python3 main.py
  ```
  Expected: `AEGIS bridge starting — gate mode` with no errors

- [ ] **Step 3: Manual test — public question**
  In Demo Channel, post: `When are office hours?`
  Expected: within ~2 seconds, bot replies with the GraphN answer in the same thread. No DM.

- [ ] **Step 4: Manual test — private question**
  In Demo Channel, post: `What is my salary?`
  Expected: no reply in the channel. Bot sends a DM: `(held) referenced N private sources` followed by the draft reply.

- [ ] **Step 5: Manual test — bot message does not auto-reply**
  Send a message to the bot's user_id via API (simulating another bot posting):
  ```bash
  # With admin token from Task 5 Step 1, post as the bot user directly:
  curl -s http://localhost:8065/api/v4/posts \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"channel_id":"<MM_DEMO_CHANNEL_ID>","message":"bot to bot","props":{"from_bot":"true"}}'
  ```
  Expected: bridge logs nothing or holds as DRAFT; no auto-reply appears in the channel.

- [ ] **Step 6: Commit**
  ```bash
  git add bridge/main.py
  git commit -m "feat: P3 — gate wired; public Q auto-sends, private Q routes to (held) DM"
  ```

---

### Task 16: Threshold tuning (P3)

**Files:** `bridge/.env` — adjust `CONF_MIN`; `bridge/.env.example` — update with final value

- [ ] **Step 1: Test the full routing matrix**
  Post each of the following in Demo Channel and note whether the result is AUTO_SEND (channel reply) or DRAFT (held DM):

  | Message | Expected |
  |---------|----------|
  | `When are office hours?` | AUTO_SEND |
  | `When is team lunch?` | AUTO_SEND |
  | `Tell me about the roadmap` | AUTO_SEND |
  | `What is my salary?` | DRAFT |
  | `What is the secret project codename?` | DRAFT |
  | `Who is the acquisition target?` | DRAFT |

- [ ] **Step 2: Adjust CONF_MIN if any row routes incorrectly**
  - A public Q that's being held → lower `CONF_MIN` (e.g. `0.6`)
  - A private Q that's auto-sending → raise `CONF_MIN` (e.g. `0.8`) or verify the KB ingestion in Task 11

  Edit `bridge/.env`, then restart:
  ```bash
  cd bridge && python3 main.py
  ```
  Repeat Step 1 until all six rows route correctly.

- [ ] **Step 3: Update .env.example with the tuned value**
  In `bridge/.env.example`, change `CONF_MIN=0.7` to the value that worked.

- [ ] **Step 4: Commit**
  ```bash
  git add bridge/.env.example
  git commit -m "chore: P3 — tuned CONF_MIN; all routing matrix rows verified"
  ```

  **P3 DONE WHEN:**
  - A public question auto-posts in the channel thread within ~2 seconds
  - A private question never reaches the channel; user receives a `(held)` DM with the reason
  - A bot-originated message does not trigger an auto-reply

---

## Sprint Acceptance Criteria

| Phase | Done when |
|-------|-----------|
| **P0** | Can log into http://localhost:8065 and post in Demo Channel |
| **P1** | Post in Demo Channel → bot replies in-thread within ~1 second |
| **P2** | Public query grounded from kb-public; private query surfaces kb-private chunk — both via bridge |
| **P3** | Public Q auto-sends; private Q goes to `(held)` DM; bot messages never auto-send |
