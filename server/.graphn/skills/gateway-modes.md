# Skill: Gateway Modes

A workflow can be invoked through four execution modes. Each is enabled or
disabled per-workflow at create/update time with `--gateways`.

## The four modes

| Mode | Flag value | What it does |
|------|-----------|--------------|
| **sync** | `sync` | HTTP long-poll: blocks until completion or timeout (~2 min). Good for short tests. |
| **async** | `async` | Returns an execution/operation ID immediately; caller polls for results. Use for anything that might take over 2 minutes. |
| **batch** | `batch` | Submits a JSON-array file as parallel executions; results collected together. |
| **event** | `event` | Enables cron and webhook triggers. Required for event-gateway triggers. |

## Setting gateways on a workflow

```bash
# At create time
graphn wf create --name "My Workflow" --dsl workflow.yaml --gateways sync,async

# After creation
graphn wf update <wf_id> --gateways sync,async,event

# Check current gateways
graphn wf get <wf_id>
```

**All four values are independent flags.** You can enable any combination.
A workflow without `async` cannot be called with `--mode async` — you'll get
a 400 error. A workflow without `event` cannot have triggers attached.

## Choosing sync vs async

```
Need to run a workflow?
│
├─ Will it finish in under ~2 minutes?
│  └─ YES ──→ wf dry-run (no side effects) or wf run (sync)
│
└─ NO / unsure / has external calls / LLM chains
   └─ wf run --mode async ──→ capture exec ID ──→ exec get <id> --watch
```

**Dry-run shares the sync timeout constraint.** If a dry-run is still running
after ~2 minutes the client connection may time out. The execution itself
continues in the backend — check `graphn exec list --workflow <wf_id>` to
see if it completed.

## Async run — full pattern

```bash
# Publish workflow first (runtime requires published version)
graphn wf publish <wf_id> -m "ready for test"

# Run async — returns an exec ID immediately
graphn wf run <wf_id> --mode async --input '{"query": "test"}'
# Output includes: exec_id: exec_abc123  (or op_abc123 via gateway)

# Poll until done (exits when status is completed or failed)
graphn exec get exec_abc123 --watch

# Or view logs as it runs
graphn logs exec_abc123
```

`exec get --watch` polls every few seconds and exits when the execution
reaches a terminal state (completed, failed, cancelled). Use `graphn watch <wf_id>`
to live-tail all new executions for a workflow.

## Batch mode

```bash
# input-file.json should be a JSON array: [{...}, {...}, ...]
graphn wf batch create <wf_id> --input-file input-file.json

# Check progress
graphn wf batch get <wf_id> <batch_id>
graphn wf batch items <wf_id> <batch_id>
```

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `400 gateway mode not supported` | Workflow not created with that mode | `graphn wf update <id> --gateways sync,async` |
| Client times out on dry-run | Long-running step exceeded ~2 min client timeout | Switch to async: `wf run --mode async` |
| `exec list` shows no results after async run | Execution registered asynchronously — retry after a few seconds | `graphn exec list --workflow <id>` again |

For event-gateway triggers (cron / webhooks), see `graphn docs skills event-gateway`.
