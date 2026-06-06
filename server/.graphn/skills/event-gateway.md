# Skill: Event Gateway (Triggers)

Triggers are named entry-points attached to a workflow. A trigger either fires
on a Temporal cron schedule or exposes a webhook URL that external systems
can POST to. Either way, each fire creates a real workflow execution with the
trigger's static input merged in.

## Prerequisite: enable the event gateway on the workflow

A workflow must list `event` in `supported_gateways` before any trigger can be
attached. This is a workflow-level setting; it is **not** part of the DSL YAML.

```bash
# Enable at create time
graphn wf create --name "My Flow" --dsl workflow.yaml --gateways sync,event

# Or add event after the fact
graphn wf update "My Flow" --gateways sync,event
```

If you try to create a trigger on a workflow that doesn't support event,
you'll see:

    Error: workflow must include "event" in supported_gateways to use triggers

Fix it with the `graphn wf update ... --gateways sync,event` above.

## Recipes

### Cron schedule with static input

```bash
graphn trigger create \
  --workflow "My Flow" \
  --name nightly-digest \
  --cron "0 2 * * *" \
  --input '{"mode": "full"}'
```

`cron_schedule` uses standard 5-field crontab syntax. Every fire creates one
workflow execution with the `--input` object merged into workflow inputs.

**Important:** GraphN does NOT validate cron syntax at create time — Temporal
parses it asynchronously. The CLI inspects `schedule_synced` and
`schedule_status` on the create/update response and prints a warning if the
schedule landed in `error` state. If you see that warning, the cron string is
bad (e.g. `0 2 * *` — 4 fields instead of 5) — fix it with
`graphn trigger update`.

### Bearer webhook (default)

```bash
graphn trigger create --workflow "My Flow" --name ci-hook --print-url
# -> stdout: https://gateway.graphn.ai/v1/<ws>/<wf>/event/trig_abc...
```

Clients POST JSON bodies to that URL with
`Authorization: Bearer <your-workspace-api-key>`. Any `graphn` API key
scoped to the workspace works. The full URL is always:

    {gateway_base}/v1/{workspace_id}/{workflow_id}/event/{trigger_id}

You can re-derive it any time with `graphn trigger url <trigger> --workflow <wf>`
(stdout only, safe for shell substitution).

### GitHub-style raw-body HMAC webhook

GitHub and many SaaS products sign webhook payloads with
`HMAC-SHA256(secret, raw_body)` and send the hex digest in a header like
`X-Hub-Signature-256: sha256=<hex>`.

```bash
# 1. store the shared secret in GraphN
graphn secret create --name GH_WEBHOOK_SECRET --value-file ./gh_secret.txt

# 2. attach an HMAC trigger
graphn trigger create \
  --workflow "My Flow" \
  --name github-push \
  --webhook-auth hmac \
  --hmac-secret GH_WEBHOOK_SECRET \
  --hmac-scheme raw_body_hmac_sha256 \
  --hmac-header X-Hub-Signature-256 \
  --print-url
```

Paste the printed URL into GitHub's webhook settings. The gateway verifies
the digest on every call — mismatches return 401 and never reach the
workflow.

### Slack request-signing v0

Slack uses a different scheme (timestamp + body under `v0:` prefix). No header
flag needed; Slack sends `X-Slack-Signature` and `X-Slack-Request-Timestamp`
and the gateway knows to look for both.

```bash
graphn secret create --name SLACK_SIGNING_SECRET --value-file ./slack.txt
graphn trigger create \
  --workflow "My Flow" \
  --name slack-slash \
  --webhook-auth hmac \
  --hmac-secret SLACK_SIGNING_SECRET \
  --hmac-scheme slack_request_signing_v0 \
  --print-url
```

### Inspect, disable, and delete

```bash
graphn trigger list --workflow "My Flow"
graphn trigger get github-push --workflow "My Flow"
graphn trigger disable github-push --workflow "My Flow"  # pauses Temporal schedule OR rejects webhooks
graphn trigger enable  github-push --workflow "My Flow"
graphn trigger delete  github-push --workflow "My Flow"
```

### Filter executions caused by a trigger

Fires carry `metadata.trigger_id` (and `metadata.source=schedule` for crons)
on the resulting execution. Useful when soaking:

```bash
graphn exec list --workflow "My Flow" | jq '.items[] | select(.metadata.trigger_id)'
```

## HMAC scheme reference

| Scheme | Header the client sends | Good for |
|--------|------------------------|----------|
| `raw_body_hmac_sha256` | `--hmac-header` (default `X-Graphn-Signature`) — `HMAC-SHA256(secret, raw_body)` | GitHub (`X-Hub-Signature-256`), Stripe, custom webhooks |
| `slack_request_signing_v0` | `X-Slack-Signature` + `X-Slack-Request-Timestamp` (fixed; `--hmac-header` ignored) | Slack only |

Algorithm is always SHA-256; there's no flag to change it because no other
algorithm is supported today. Body size limit on the webhook is 1 MiB.

## Webhook URL anatomy

    https://gateway.graphn.ai/v1/<workspace_id>/<workflow_id>/event/<trigger_id>

- `workspace_id` — from `graphn whoami` or `graphn config show`
- `workflow_id` — from `graphn wf get <name>` (a `wf_...` id)
- `trigger_id` — from `graphn trigger get <name> --workflow <wf>` (a `trig_...` id)

The gateway host can be overridden with `--gateway-url`, `GRAPHN_GATEWAY_URL`,
or `graphn config set-gateway-url` — `graphn trigger url` always assembles from
whichever one resolves first.

## Common pitfalls

- **Forgetting `--gateways event` on the workflow.** Create will 400 with
  `EVENT_GATEWAY_REQUIRED`. Run `graphn wf update <wf> --gateways sync,event` first.
- **Dropping `event` from `supported_gateways` while triggers exist.** The server
  rejects this with a clear message; the CLI surfaces "delete triggers first".
  Use `graphn trigger list --workflow <wf>` to find what still references it.
- **Assuming HTTP 201 means a healthy cron.** It does not — the CLI inspects
  `schedule_synced` and `schedule_status` and warns on `error`. Fix the cron
  string and `graphn trigger update`.
- **Name collisions.** Trigger names are unique per workflow (normalized
  lower-cased + trimmed). Two workflows can both have `nightly`; one workflow
  cannot have `nightly` twice.
- **Mass PATCH with `--disabled` default.** `graphn trigger update` only sends
  fields you explicitly pass — `--cron ""` sends an empty string to clear cron,
  and omitted flags stay untouched server-side.
- **POST retries on 5xx.** `c.Do` retries transient 5xx on `graphn trigger create`.
  If the first POST landed but returned 5xx to the retry, the retry hits the
  per-workflow uniqueness check and gets a clean 409 `NAME_CONFLICT` — which is
  the correct outcome. No duplicate triggers are created.

## Quick command index

| Command | Description |
|---------|-------------|
| `graphn trigger list [--workflow NAME-OR-ID]` | List triggers (optionally filtered by workflow) |
| `graphn trigger get <name-or-id> [--workflow W]` | Get a trigger's full state |
| `graphn trigger create --workflow W --name N [opts]` | Create a cron or webhook trigger |
| `graphn trigger update <name-or-id> [opts]` | Partial update (only fields you pass) |
| `graphn trigger enable <name-or-id> [--workflow W]` | Resume the Temporal schedule / accept webhooks |
| `graphn trigger disable <name-or-id> [--workflow W]` | Pause the schedule or reject webhooks |
| `graphn trigger delete <name-or-id> [--workflow W] [--force]` | Delete trigger (and its Temporal schedule) |
| `graphn trigger url <name-or-id> [--workflow W]` | Print the webhook URL (stdout, shell-safe) |

For API-level access, see `graphn docs skills dsl-api`.
