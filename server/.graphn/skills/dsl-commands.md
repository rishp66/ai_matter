# Skill: CLI Command Reference

## IDs vs Names

The CLI accepts both names and IDs for most commands. However, after any `create` command,
you MUST **capture the returned ID** (e.g. agent_abc123, func_def456, wf_xyz000) and use it for
ALL subsequent operations. Names are ambiguous when workflow-scoped copies exist —
`GetByName` returns the first match, which may not be the resource you intended.

## Command Reference

### Discovery & Context
| Command | Description |
|---------|-------------|
| `graphn context` | Show workspace overview (agents, functions, workflows, etc.) |
| `graphn search <QUERY>` | Search across all components |
| `graphn whoami` | Show current user and workspace |
| `graphn scaffold <TYPE> --name N` | Generate boilerplate (agent, function, mcp-server, workflow) |
| `graphn connector list` | List available connectors and actions |

### Agents
| Command | Description |
|---------|-------------|
| `graphn agent list` | List agents |
| `graphn agent get <ID>` | Get agent details |
| `graphn agent create --name N --model M --instructions F` | Create agent (returns ID) |
| `graphn agent update <ID> --instructions F` | Update agent |
| `graphn agent dry-run --instructions F --message TEXT` | Stateless test (no saved agent needed) |
| `graphn agent publish <ID> -m MSG` | Publish version |
| `graphn agent publish-all` | Publish all agents |
| `graphn agent archive <ID>` | Archive agent |
| `graphn agent delete <ID>` | Delete agent |

### Functions
| Command | Description |
|---------|-------------|
| `graphn func list` | List functions |
| `graphn func get <ID>` | Get function details |
| `graphn func code <ID>` | View function source code |
| `graphn func create --name N --code F` | Create function (returns ID) |
| `graphn func update <ID> --code F` | Update function code |
| `graphn func test <ID> --input JSON` | Test function with input |
| `graphn func dry-run --code F --input JSON` | Stateless test (no saved function needed) |
| `graphn func publish <ID> -m MSG` | Publish version |
| `graphn func publish-all` | Publish all functions |
| `graphn func delete <ID>` | Delete function |

### MCP Tool Servers
| Command | Description |
|---------|-------------|
| `graphn mcp list` | List MCP servers |
| `graphn mcp get <ID>` | Get MCP server details |
| `graphn mcp code <ID>` | View server source code |
| `graphn mcp create --name N --code F` | Create hosted server (returns ID) |
| `graphn mcp update <ID> --code F` | Update server code |
| `graphn mcp tools <ID>` | List server's discovered tools |
| `graphn mcp refresh-tools <ID>` | Rediscover tools after code change |
| `graphn mcp test-tool <ID> --tool T --input JSON` | Test a specific tool |
| `graphn mcp publish <ID>` | Publish version |
| `graphn mcp publish-all` | Publish all MCP servers |
| `graphn mcp start <ID>` | Start server |
| `graphn mcp stop <ID>` | Stop server |
| `graphn mcp delete <ID>` | Delete MCP server |

### Workflows
| Command | Description |
|---------|-------------|
| `graphn wf list` | List workflows |
| `graphn wf get <ID>` | Get workflow details — response shape: `{ "workflow": {...}, "agents": [...], "functions": [...], "mcp_servers": [...] }`. Workflow-scoped copies have their own IDs separate from standalone resources. |
| `graphn wf create --name N --dsl F` | Create workflow (returns ID) |
| `graphn wf update <ID> --dsl F` | Update workflow DSL |
| `graphn wf validate F` | Validate DSL file locally |
| `graphn wf describe <ID>` | Show workflow structure and linked components |
| `graphn wf viz <ID>` | Open visual canvas in browser |
| `graphn wf dry-run <ID> --input JSON` | Test workflow |
| `graphn wf run <ID> --input JSON` | Run published workflow |
| `graphn wf run <ID> --mode async --input JSON` | Run async (returns exec ID) |
| `graphn wf publish <ID> -m MSG` | Publish version |
| `graphn wf publish-all` | Publish all workflows |
| `graphn wf save-bundle <ID> --bundle F` | Link all components to workflow |
| `graphn wf clone <ID> --name N` | Clone workflow |
| `graphn wf export <ID>` | Export workflow bundle |
| `graphn wf import --bundle F` | Import workflow from bundle |
| `graphn wf versions <ID>` | List published versions |
| `graphn wf restore <ID> --version N` | Restore to a previous version |
| `graphn wf diff <ID> --version N` | Diff against a version |
| `graphn wf health <ID>` | Check workflow health |
| `graphn wf delete <ID>` | Delete workflow |

### Executions
| Command | Description |
|---------|-------------|
| `graphn exec list` | List executions |
| `graphn exec list --workflow <ID>` | List executions for a workflow |
| `graphn exec get <EXEC_ID>` | Get execution status and results |
| `graphn exec get <EXEC_ID> --watch` | Poll until execution completes |
| `graphn exec cancel <EXEC_ID>` | Cancel a running execution |

### Batches
| Command | Description |
|---------|-------------|
| `graphn wf batch create <ID> --input-file F` | Create batch (F is a JSON array file) |
| `graphn wf batch list <ID>` | List batch executions |
| `graphn wf batch get <ID> <BATCH_ID>` | Get batch status |
| `graphn wf batch items <ID> <BATCH_ID>` | List batch items |
| `graphn wf batch cancel <ID> <BATCH_ID>` | Cancel batch execution |

### Knowledge Bases
| Command | Description |
|---------|-------------|
| `graphn kb list` | List knowledge bases |
| `graphn kb create --name N --description D` | Create knowledge base |
| `graphn kb get <ID>` | Get KB details |
| `graphn kb stats <ID>` | Get KB statistics (document count, etc.) |
| `graphn kb upload <ID> FILE` | Upload document to KB |
| `graphn kb documents <ID>` | List documents in KB |
| `graphn kb search <ID> --query Q --top-k N` | Semantic search |
| `graphn kb delete <ID>` | Delete knowledge base |

### Models
| Command | Description |
|---------|-------------|
| `graphn model list-chat` | List available chat models |
| `graphn model imported list` | List imported external models |
| `graphn model imported create --name N --endpoint URL --model-id M` | Import external model |
| `graphn model imported get <ID>` | Get imported model details |
| `graphn model imported update <ID> --endpoint URL` | Update imported model |
| `graphn model imported delete <ID>` | Delete imported model |
| `graphn model custom list` | List custom deployed models |
| `graphn model custom deploy --name N --hf-model-id M --gpu-count G` | Deploy HuggingFace model |
| `graphn model custom get <ID>` | Get custom model status |
| `graphn model custom refresh <ID>` | Refresh deployment status |
| `graphn model custom wake <ID>` | Wake from scale-to-zero |
| `graphn model custom test <ID> --prompt TEXT` | Test custom model inference |
| `graphn model custom gpu-hours` | Show GPU usage |
| `graphn model custom delete <ID>` | Delete custom model |

### Secrets
| Command | Description |
|---------|-------------|
| `graphn secret list` | List secrets |
| `graphn secret create --name N --value V` | Create secret |
| `graphn secret update <ID> --value V` | Update secret value |
| `graphn secret delete <ID>` | Delete secret |
| `graphn secret import FILE` | Import secrets from .env file |

### Storage
| Command | Description |
|---------|-------------|
| `graphn storage list` | List storage buckets |
| `graphn storage create --name N` | Create storage bucket |
| `graphn storage files <ID>` | List files in bucket |
| `graphn storage upload <ID> FILE` | Upload file (streams from disk; auto-multipart above ~64 MiB) |
| `graphn storage download <ID> KEY` | Download file (parallel Range GETs for large objects) |
| `graphn storage delete <ID> KEY` | Delete file |
| `graphn storage presign <ID> KEY --method get|put|upload-part` | Mint a presigned URL for direct-to-storage access |
| `graphn storage import s3://B/P <ID> --prefix X` | Streamed S3 → GraphN import (uses MPU) |

**Large-object flags** (on `upload` and `download`):
| Flag | Default | Purpose |
|------|---------|---------|
| `--multipart-threshold <bytes>` | 64 MiB | Switch to MPU / ranged GET above this size |
| `--part-size <bytes>` | 32 MiB | Bytes per part (server cap: 5 MiB ≤ size ≤ 64 MiB) |
| `--concurrency <n>` | 4 | Parallel part workers |

**Presign flags** (on `graphn storage presign`):
| Flag | Purpose |
|------|---------|
| `--method get|put|upload-part` | GET for reads, PUT for single-shot upload, upload-part for MPU parts |
| `--expires <seconds>` | Lifetime of the URL (default 3600) |
| `--max-size <bytes>` | (PUT only) enforce an upper bound on the uploaded body |
| `--content-type <mime>` | (PUT only) pin Content-Type the client must send |
| `--upload-id <id>`, `--part-number <n>` | (upload-part only) scope the URL to one MPU part |
| `--output url|json` | Just the URL (pipeable) or the full JSON response |

**When to reach for presigned URLs:**
- Passing a large media file (video/image) to `vision` / ASR / external models — mint a GET URL and hand over the URL string, not bytes.
- Accepting a > 100 MiB upload from a workflow trigger — Cloudflare caps single-request bodies at 100 MiB. Use presigned PUT (or presigned-per-part MPU) so the client uploads directly to storage.
- Sharing an object with a third-party tool without exposing the workspace API key.

### Monitoring
| Command | Description |
|---------|-------------|
| `graphn watch <WORKFLOW>` | Live tail workflow executions |
| `graphn logs <EXEC_ID>` | View execution logs |
| `graphn status` | Show system status |

### Config
| Command | Description |
|---------|-------------|
| `graphn config show` | Show current configuration |
| `graphn config set-url <URL>` | Set API URL |
| `graphn config set-key <KEY>` | Set API key |
| `graphn config set-workspace <ID>` | Set default workspace |
| `graphn config set-gateway-url <URL>` | Set gateway URL (for production runs) |

### Config patterns

**Always verify config before running commands:**
```bash
graphn whoami        # shows current user, workspace, and CP URL
graphn config show   # full config JSON
```

**The command is `set-key`**, not `set-api-key`. Using the wrong name returns
an "unknown command" error.

**Env-var overrides** avoid mutating `~/.graphn/config.json` for one-off calls:
```bash
GRAPHN_URL=https://… GRAPHN_API_KEY=gn_… GRAPHN_WORKSPACE=ws_… \
  graphn wf dry-run <wf_id> --input '{}'
```

| Variable | Purpose |
|----------|---------|
| `GRAPHN_URL` | CP base URL |
| `GRAPHN_API_KEY` | API key |
| `GRAPHN_WORKSPACE` | Workspace ID |
| `GRAPHN_GATEWAY_URL` | Gateway URL (required for `wf run`) |

**401 after changing the CP URL** almost always means the API key or workspace
ID belongs to a different environment. Run:
```bash
graphn config set-key <new_key>
graphn config set-workspace <new_ws>
graphn whoami   # confirm correct environment
```

