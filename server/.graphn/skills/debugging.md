# Skill: Debugging Failed Workflows

## Quick Diagnostics

```bash
# 1. Check workflow structure
graphn wf describe <wf_id>

# 2. Validate DSL before deploying
graphn wf validate workflow.yaml

# 3. Check recent executions
graphn exec list --workflow <wf_id>

# 4. Get execution details (with step-by-step results)
graphn exec get <execution-id>

# 5. View logs
graphn logs <execution-id>
```

## Common Errors and Fixes

### "Max turns (0) exceeded"
**Cause:** Agent max_llm_calls was explicitly set to 0. The CLI default is 25 when creating agents.
**Fix:**
```bash
graphn agent update <agent_id> --max-llm-calls 25
```

### "Max turns (N) exceeded"
**Cause:** Agent hit the tool call limit. Complex tasks need more turns. Default is 25.
**Fix:** Increase `--max-llm-calls` to 30-50 for complex agents.

### "UNRESOLVED_RESOURCES"
**Cause:** Components not linked to the workflow.
**Fix:**
```bash
# Re-save the bundle to link all components
graphn wf save-bundle <wf_id> --bundle bundle.json
```

### "key not found" in expressions
**Cause:** Incorrect `${steps.X.output}` reference.
**Fix:**
```bash
# Check step names and outputs
graphn wf describe <wf_id>
# Validate DSL
graphn wf validate workflow.yaml
```

### Timeout errors / ReadTimeout in functions
**Cause:** Step or HTTP call took too long. Default timeout may be too short, or function code has no explicit timeout.
**Fix:** Increase agent timeout_seconds in spec, or simplify the task. For functions making HTTP calls, ALWAYS set explicit timeouts:
```python
async with httpx.AsyncClient(timeout=30) as client:
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        return {"error": "Request timed out", "url": url}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:500]}
```

### HTTP 502 from `wf run` or `wf dry-run`
**Cause:** Gateway timeout — the execution may still be running in the background.
**Fix:** Do NOT blindly retry. Check if the execution started:
```bash
graphn exec list --workflow <wf_id>
graphn exec get <exec_id>
```
If the execution is running or completed, inspect its results. Only retry if no execution was created.

### Dry-run logs not found (`test_` prefix)
**Cause:** Dry-run executions use `test_` prefixed IDs. `graphn logs` may not find them because dry-run logs are stored differently.
**Fix:** Use `graphn exec get <test_exec_id>` instead, which shows step-by-step output for dry-runs.

### "WARNING: Components with unpublished changes" after publish-all
**Cause:** This warning can appear after `wf create` because the workflow itself is not yet published (even if all agents/functions/MCP servers are). It does NOT mean your components failed to publish.
**Fix:** This is normal. Run `graphn wf publish <wf_id>` to resolve. Do NOT panic and recreate the workflow.

### MCP tool not found
**Cause:** Tool wasn't discovered or server isn't published.
**Fix:**
```bash
# Verify tools are discovered
graphn mcp tools <mcp_id>
# Refresh tool discovery
graphn mcp refresh-tools <mcp_id>
# Make sure server is published
graphn mcp publish <mcp_id>
```

## Debugging Workflow

1. **Validate first** — `graphn wf validate` catches DSL errors before creation
2. **Describe** — `graphn wf describe` shows the workflow structure and linked components
3. **Dry-run** — `graphn wf dry-run` executes without side effects
4. **Check logs** — `graphn logs <exec-id>` shows step-by-step execution details
5. **Watch live** — `graphn watch <workflow-id-or-name>` live-tails new executions as they complete

### `mcp start --wait` timed out
**Cause:** `mcp start --wait` waits up to ~2 minutes for the hosted MCP server to
reach a running state before returning. Hitting the timeout does NOT mean the
server failed — it means it took longer than the polling window.
**This does NOT block dry-run or workflow runs.** The workflow runtime starts
the server on-demand when the first tool call occurs. You can proceed to
`wf dry-run` or `wf run` immediately after a `mcp start` timeout.
**Only wait on `mcp start` if:** you need the server running for an external
integration test before any workflow execution.

### Dry-run client timeout (~2 min)
**Cause:** `wf dry-run` is synchronous. If the workflow has long-running steps
(LLM chains, large document processing, external APIs), the client HTTP
connection may time out at ~2 minutes even if the execution is still running.
**Fix:** Switch to async for any workflow that might take over 2 minutes:
```bash
graphn wf publish <wf_id> -m "test"
graphn wf run <wf_id> --mode async --input '{"key": "value"}'
graphn exec get <exec_id> --watch
```
For short, single-step tests, `graphn agent dry-run` is faster and has no
global timeout.

### Async run polling
After `wf run --mode async`, the output includes an execution or operation ID:
```bash
graphn wf run <wf_id> --mode async --input '{"key": "value"}'
# → exec_id: exec_abc123

# Poll until terminal state
graphn exec get exec_abc123 --watch

# Or inspect immediately
graphn exec get exec_abc123

# If exec list appears empty right after async run, wait a few seconds and retry
graphn exec list --workflow <wf_id>

# Stream logs as the execution runs
graphn logs exec_abc123
```

## Pro Tips

- Always `dry-run` before `publish`
- For long-running workflows, use `--mode async` then `graphn exec get <exec_id> --watch` to poll progress
- Use `graphn wf viz <wf_id>` to see the DAG structure visually
- When an agent fails, test it standalone (stateless): `graphn agent dry-run --instructions instructions.txt --message 'test prompt'`
- When an MCP tool fails, test it standalone: `graphn mcp test-tool <mcp_id> --tool tool_name --input '{}'`
- Check `graphn context` to verify all components exist and are linked
- Load `graphn docs skills gateway-modes` for the full sync vs async decision tree
