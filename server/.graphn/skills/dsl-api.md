# Skill: REST API Reference

## Direct API with curl

If a CLI command fails or doesn't support an operation, call the GraphN API directly.
Get the config with `graphn config show` for URL, API key, and workspace ID.

```bash
# Read config
URL=$(graphn config show | python3 -c "import sys,json;print(json.load(sys.stdin).get('url',''))")
KEY=$(graphn config show | python3 -c "import sys,json;print(json.load(sys.stdin).get('api_key',''))")
WS=$(graphn config show | python3 -c "import sys,json;print(json.load(sys.stdin).get('workspace',''))")

# GET request
curl -s "$URL/v1/$WS/agents" \
  -H "Authorization: Bearer $KEY" \
  -H "X-Workspace-ID: $WS"

# POST request
curl -s -X POST "$URL/v1/$WS/workflows/WORKFLOW_ID/publish" \
  -H "Authorization: Bearer $KEY" \
  -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json"
```

Key API patterns (all under `/v1/{workspace_id}/`):

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/agents` | List / create agents |
| GET | `/agents/{id}` | Get agent by ID |
| PATCH | `/agents/{id}` | Update agent |
| POST | `/agents/{id}/publish` | Publish version |
| GET/POST | `/functions` | List / create functions |
| POST | `/functions/{id}/test` | Test function |
| GET/POST | `/mcp-servers` | List / create MCP servers |
| GET | `/mcp-servers/{id}/tools` | List tools |
| GET/POST | `/workflows` | List / create workflows |
| PUT | `/workflows/{id}/bundle` | Link components to workflow |
| POST | `/workflows/{id}/publish` | Publish version |
| POST | `/workflows/{id}/test` | Dry-run |
| POST | `/workflows/{id}/run` | Production run |
| GET/POST | `/knowledgebases` | List / create KBs |
| POST | `/knowledgebases/{id}/search` | Semantic search |
| GET/POST | `/secrets` | List / create secrets |
| GET/POST | `/triggers` | List / create event-gateway triggers |
| GET/PATCH/DELETE | `/triggers/{id}` | Get / update / delete trigger |

## Storage service (S3-compatible, separate host)

The storage service lives at a different URL from the API — `graphn config show` exposes it as `storage_url`. Paths are S3-style: `/:bucket/:key`. Auth accepts the same bearer token as the API.

```bash
STORAGE=$(graphn config show | python3 -c "import sys,json;print(json.load(sys.stdin).get('storage_url',''))")
KEY=$(graphn config show | python3 -c "import sys,json;print(json.load(sys.stdin).get('api_key',''))")
AUTH="Authorization: Bearer $KEY"
```

| Method | Path | Description |
|--------|------|-------------|
| HEAD | `/:bucket/:key` | Probe size + `Accept-Ranges: bytes` before ranged downloads |
| GET | `/:bucket/:key` | Download. `Range: bytes=start-end` → `206 Partial Content` |
| PUT | `/:bucket/:key` | Single-shot upload (≤ 100 MiB via Cloudflare; use MPU above) |
| DELETE | `/:bucket/:key` | Delete object |
| POST | `/:bucket/:key?uploads` | Initiate multipart upload → `{ upload_id, max_part_size }` |
| PUT | `/:bucket/:key?uploadId=&partNumber=` | Upload one part (response `ETag` must be echoed at complete) |
| POST | `/:bucket/:key?uploadId=` | Complete MPU, body: `{"parts":[{"part_number":N,"etag":"..."}]}` |
| DELETE | `/:bucket/:key?uploadId=` | Abort an in-flight MPU (always run this on error to avoid orphans) |
| POST | `/:bucket/:key?type=download&expires=SEC` | Mint presigned GET URL |
| POST | `/:bucket/:key?type=upload&expires=SEC&max-size=N&content-type=MIME` | Mint presigned PUT URL |
| POST | `/:bucket/:key?type=upload_part&upload_id=ID&part_number=N` | Mint presigned URL for one MPU part |

All presign responses have shape `{ "url": "...", "expires_in": 3600, "key": "..." }`. The `url` can be passed directly to external consumers (vLLM, browsers, `curl`) — no GraphN auth required.

**Typical MPU flow from a client (no `foundry_helpers`):**

```bash
# 1. Initiate
INIT=$(curl -s -X POST -H "$AUTH" "$STORAGE/bkt/big.bin?uploads")
UPLOAD_ID=$(echo "$INIT" | jq -r .upload_id)

# 2. For each part, mint a presigned URL + PUT to it
for i in 1 2 3; do
  URL=$(curl -s -X POST -H "$AUTH" \
    "$STORAGE/bkt/big.bin?type=upload_part&upload_id=$UPLOAD_ID&part_number=$i" | jq -r .url)
  ETAG=$(curl -sI -X PUT --upload-file "part_$i.bin" "$URL" | grep -i '^etag:' | cut -d' ' -f2 | tr -d '\r"')
  PARTS="$PARTS,{\"part_number\":$i,\"etag\":\"$ETAG\"}"
done

# 3. Complete
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  "$STORAGE/bkt/big.bin?uploadId=$UPLOAD_ID" \
  -d "{\"parts\":[${PARTS#,}]}"
```
