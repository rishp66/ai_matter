# Skill: Workflow Building (Enhanced v4)

## Deploy Checklist (read before creating any components)

### Blueprint-first (preferred)

Check for an existing template before building from scratch:

```bash
graphn blueprint list
graphn blueprint info <blueprint_id>
graphn blueprint deploy <blueprint_id> --name "My Workflow"
```

If a blueprint covers your use case, deploy it and customize — this saves the
manual 8-step creation sequence below.

### Manual creation — strict order

If no blueprint fits, create components in this order:

```bash
# 1. MCP servers first (if needed)
graphn mcp create --name MyTools --code tools.py
graphn mcp publish <mcp_id>            # publish before workflow creation
# Skip mcp start for now; the runtime starts it on first tool call

# 2. Agents
graphn agent create --name MyAgent --model <model_id> --instructions agent.txt
graphn agent publish <agent_id>

# 3. Workflow (must include --gateways; async is required for long runs)
graphn wf create --name "My Workflow" --dsl workflow.yaml --gateways sync,async
graphn wf publish <wf_id> -m "initial"

# 4. Test
graphn wf dry-run <wf_id> --input '{"key": "value"}'   # short workflows only
graphn wf run <wf_id> --mode async --input '{"key": "value"}'  # long / production
graphn exec get <exec_id> --watch
```

**Critical:** `wf publish` is separate from `agent publish` and `mcp publish`.
All three must be published for a production run to use the latest versions.

After `wf create`, always use **workflow-scoped IDs** for updates — the
workflow gets its own copies of all components. Get those scoped IDs with
`graphn agent list --workflow <wf_id>` before updating anything.

### Secrets for MCP and function code

Store sensitive values as GraphN secrets; never hardcode them:

```bash
graphn secret create --name EXTERNAL_API_KEY --value "sk-…"
# Reference in DSL: "$secret:sec_xxx"
# Access in Python (FES / MCP sandbox): os.environ["EXTERNAL_API_KEY"]
```

---

You build workflows by **designing a graph**, not by writing YAML. Think in
three phases: **Pattern → Decomposition → Implementation**.

---

## Phase 1: Choose the Right Pattern

Every workflow maps to one of these orchestration patterns. Pick the simplest
one that fits.

### Pattern Catalog

| Pattern | When to Use | GraphN Primitive | Shape |
|---------|-------------|------------------|-------|
| **Sequential** | Steps must happen in order; each needs the previous output | agent/function steps with after: | A → B → C |
| **Tool-augmented agent** | An agent needs to reason about which tools to call and when | agent step + MCP tools | Agent ⇄ Tools |
| **Split-and-merge** | Independent work that can run in parallel, then converge | Parallel agent/function steps → synthesizer with after: [all] | ⫘ → S |
| **Router** | Input needs to go to different specialists based on classification | handoff_router step | Triage → {A, B, C} |
| **Judge loop** | Output must meet a quality bar; retry with feedback if not | judge_loop step | Worker ⇄ Judge (max N) |
| **Iteration** | Process each item in a collection the same way | for_each step | Loop(item → process) → collect |
| **Conditional** | Different paths based on a runtime value | conditional step | If P then A else B |
| **Composite** | Complex tasks need multiple patterns combined | Mix of the above | DAG |

### Pattern Selection Rules

1. **Can a single agent with tools do it?** → Tool-augmented agent. Stop here.
2. **Are there independent subtasks with no data dependency?** → Split-and-merge.
3. **Does input need classification before routing?** → Router.
4. **Must output meet a quality bar?** → Judge loop (wrap around the producing step).
5. **Is there a collection to process?** → for_each.
6. **Do steps depend on each other sequentially?** → Sequential.
7. **Multiple of the above?** → Composite. Sketch the DAG before writing YAML.

### When NOT to Use Each Pattern

- **Don't use parallel** when steps actually depend on each other — you'll get race conditions.
- **Don't use handoff_router** for binary decisions — use conditional instead.
- **Don't use judge_loop** without clear evaluation criteria — the judge needs a rubric, not vibes.
- **Don't use for_each** when the collection is always a fixed, small set — just use named parallel steps.
- **Don't use agents** for deterministic data fetching — use function steps (cheaper, faster, no LLM needed).

---

## Phase 2: Decompose into Steps

### The Decomposition Method

1. **List the work** — What concrete jobs need to happen? Write each as a verb phrase.
2. **Classify each job:**
   - **Deterministic data I/O** → function (HTTP calls, DB queries, file processing)
   - **Requires LLM reasoning** → agent (analysis, writing, classification, synthesis)
   - **Requires tool use with judgment** → agent + MCP tools
3. **Draw dependencies** — Which jobs need output from other jobs? This gives you the DAG.
4. **Identify parallelism** — Jobs with no dependency between them can run in parallel.
5. **Add quality gates** — Any output that goes to a user or external system should have a judge loop.

### Agent Design Principles

An agent is only as good as its instructions. Follow these rules:

**Scope narrowly.** Each agent does ONE job. "You are a security reviewer" not
"You are a helpful assistant that can review code, write tests, and deploy."

**Specify the workflow.** Tell the agent its exact steps:

  WORKFLOW:
  1. Read the input data
  2. Identify X, Y, Z
  3. Use tool A to check...
  4. Return findings as...

**Document tools.** Remind the agent what tools it has and when to use them:

  YOUR TOOLS:
  - search(query, top_k): Find relevant documents. Use for factual claims.
  - lookup_order(id): Get order details. Always call before answering order questions.
Only bind tools the agent actually needs — don't give every agent every tool.

**Define output format.** If the next step needs structured data, say so:

  OUTPUT FORMAT: Return a JSON object with keys: severity (P1-P4), summary (string), evidence (array of strings).

For multi-step workflows, prefer JSON output so downstream steps can reference specific
fields via ${steps.X.output.field}. Free-text output is fine only for final/terminal steps.

**Handle edge cases.** What should the agent do when data is missing?

  If no results are found, return {"status": "no_data", "suggestion": "Try broader query"}.
  Do NOT hallucinate data. Say what is missing.

**Enforce output discipline.** Agents in judge_loops or multi-step chains tend to add
meta-commentary ("Great question!", "You're absolutely right..."). Prevent this:

  Output ONLY the marketing copy. Do not include commentary, self-assessment,
  or acknowledgment of feedback. Return the deliverable and nothing else.

**Anti-hallucination.** For agents working with retrieved data, always include:

  Base ALL content on provided evidence. Do NOT fabricate data, statistics, or claims.
  If evidence is insufficient, state what is missing rather than guessing.

### Understanding instructions vs input_template

These are two separate things that combine at runtime:

- **instructions** (set at agent creation) — permanent identity: role, workflow steps,
  tool docs, output format, edge cases. This is the agent's "job description."
- **input_template** (set in DSL per step) — per-run context: the specific data for
  this execution. Variables like ${input.query} and ${steps.X.output} are resolved here.

At runtime the platform concatenates: instructions + resolved input_template = full prompt.

Keep instructions generic and reusable. Put run-specific data in input_template.

### Function vs Agent Decision

| Signal | Use Function | Use Agent |
|--------|-------------|-----------|
| HTTP API call | Yes | No |
| Fixed transformation | Yes | No |
| Needs judgment/reasoning | No | Yes |
| Output depends on context | No | Yes |
| Needs to call tools conditionally | No | Yes (with MCP) |
| Handles secrets/API keys | Yes | No (pass via function) |

---

## Phase 3: Implement

Building a workflow means creating ALL the components — agents, functions, MCP servers —
then wiring them together with DSL. The DSL references components by name; they must
exist before you create the workflow.

### Step 3a: Pre-flight

1. **Check context** — `graphn context` — reuse existing agents, MCP servers, KBs.
2. **Check blueprints** — `graphn bp list` — if a template covers 80%+ of the task, deploy and customize it.

### Step 3b: Create Agents

Each agent from your decomposition needs to be created with instructions, model, and optional tool bindings.

```bash
# Write instructions to a file first (easier to iterate than inline strings)
cat > researcher_instructions.txt << 'INST'
You are a security code reviewer.

WORKFLOW:
1. Read the PR diff provided in the input
2. Identify vulnerabilities: injection, auth bypass, data exposure, hardcoded secrets
3. For each finding, note file, line, severity (Critical/High/Medium/Low), and fix
4. If no issues found, explicitly state the code passes security review

YOUR TOOLS:
- (none — you work from the diff provided in the input)

OUTPUT FORMAT: Return a JSON object:
{"findings": [{"file": "", "line": 0, "severity": "", "issue": "", "fix": ""}],
 "summary": "", "pass": true/false}

If the diff is empty or unparseable, return {"findings": [], "summary": "No diff provided", "pass": false}.
INST

graphn agent create --name "SecurityReviewer" --model qwen3-30b --instructions researcher_instructions.txt
```

**Agent instruction rules:**
- **Role** — one sentence: who the agent is
- **WORKFLOW** — numbered steps the agent follows every time
- **YOUR TOOLS** — list each tool with signature and when to use it (or state "none")
- **OUTPUT FORMAT** — exact structure the next step expects (JSON schema, markdown template, etc.)
- **EDGE CASES** — what to do when data is missing, empty, or malformed

**Tool bindings** — if the agent needs MCP tools, bind them at creation.
IMPORTANT: Use separate `--tools` flags for each tool (not space-separated):
```bash
graphn agent create --name "KBAssistant" --model qwen3-80b \
  --instructions assistant.txt \
  --tools "ProductKB:semantic_search" --tools "ProductKB:keyword_search"
```

**Knowledge base binding** — for direct KB access without MCP tools:
```bash
graphn agent create --name "DocAssistant" --model qwen3-80b \
  --instructions assistant.txt --knowledge-base <kb_id>
```
Use the KB ID (`kb_xxx`), not the name — name resolution may fail for KBs with special characters.

**Model selection:**
- `qwen3-30b` — fast, good for classification, routing, simple analysis
- `qwen3-80b` — balanced, good for synthesis, writing, multi-step reasoning
- `qwen3-235b` — strongest, use for complex analysis or when quality matters most

### Step 3c: Create Functions

Functions are for deterministic work: HTTP calls, data transforms, file processing.
No LLM involved — faster and cheaper than agents.

Write the Python code to a file:
```python
# fetch_news.py
import httpx

async def fetch_news(query: str = "", API_KEY: str = "", **kwargs) -> dict:
    """Fetch news articles for a company from the news API."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                "https://newsapi.example.com/v2/everything",
                params={"q": query, "sortBy": "publishedAt", "pageSize": 10},
                headers={"X-Api-Key": API_KEY},
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return {
                "status": "success",
                "count": len(articles),
                "articles": [{"title": a["title"], "source": a["source"]["name"],
                              "url": a["url"], "summary": a.get("description", "")}
                             for a in articles],
            }
        except httpx.TimeoutException:
            return {"status": "error", "error": "timeout", "query": query}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": f"HTTP {e.response.status_code}",
                    "detail": e.response.text[:500]}
```

Then create it:
```bash
graphn func create --name "fetch_news" --code fetch_news.py
# If you need extra packages beyond httpx:
graphn func create --name "fetch_news" --code fetch_news.py --requirements requirements.txt
```

**Function rules:**
- ALL HTTP calls MUST have `timeout=30` (or appropriate value)
- ALL HTTP calls MUST have try/except for TimeoutException and HTTPStatusError
- Return `{"status": "success", ...}` or `{"status": "error", ...}` so downstream agents can handle failures
- Secrets are received as kwargs — declare them as parameters with defaults: `API_KEY: str = ""`
- Use `**kwargs` to accept extra parameters the platform may inject
- Functions run on Python 3.11 with 8GB RAM, internet access, `httpx` pre-installed

### Step 3d: Create MCP Servers

MCP servers give agents interactive tools. Use them when an agent needs to call tools
with judgment (deciding which tool, what parameters, how many times).

Write the server code:
```python
# search_tools.py
from fastmcp import FastMCP
from foundry_helpers import kb

mcp = FastMCP("SearchTools")

@mcp.tool()
async def semantic_search(kb_id: str, query: str, top_k: int = 8) -> dict:
    """Search knowledge base by semantic meaning.
    Args:
        kb_id: Knowledge base ID to search
        query: Natural language search query
        top_k: Number of results (default 8)
    Returns:
        Search results with text, source, and relevance score
    """
    if not kb_id or not query:
        return {"status": "error", "error": "kb_id and query required"}
    results = await kb.search(kb_id, query, top_k=top_k)
    return {
        "status": "success",
        "results": [{"text": r.get("text", ""), "source": r.get("source", ""),
                      "score": round(r.get("score", 0), 3)} for r in results],
    }
```

Then create it:
```bash
graphn mcp create --name "SearchTools" --code search_tools.py
```

**MCP server rules:**
- Every `@mcp.tool()` MUST have a docstring — it becomes the tool description the agent sees
- Include Args and Returns in the docstring so the agent knows the signature
- Validate inputs and return error objects instead of raising exceptions
- Use `foundry_helpers` for KB search, storage, and other platform features

### Step 3e: Create Secrets

For any API keys or tokens your functions need:
```bash
graphn secret create --name "NEWS_API_KEY" --value "sk-..."   # returns sec_xxx
graphn secret create --name "SLACK_WEBHOOK" --value "https://hooks.slack.com/..."
```
Capture the `sec_xxx` ID.

**How to pass secrets to function steps in DSL:**
Declare secrets at the **step level** using `$secret:sec_xxx`, NOT in function input:
```yaml
  fetch_news:
    call: function
    function: news_fetcher
    input:
      query: "${input.company}"
    secrets:
      api_key: "$secret:sec_abc123"
    output: news_data
```
The function receives `api_key` as a kwarg with the decrypted value.

WRONG — do not use `${secrets.X}` in function input:
```yaml
  # BAD: ${secrets.api_key} will not resolve
  fetch_news:
    call: function
    function: news_fetcher
    input:
      query: "${input.company}"
      api_key: "${secrets.api_key}"    # DOES NOT WORK
```

### Step 3f: Write the DSL

Now that all components exist, write the workflow YAML referencing them by name:

```yaml
document:
  dsl: "1.0.0"
  name: "Workflow Name"
  version: "0.1.0"

agents:
  AgentName: ""          # references by name, resolved at create time
functions:
  function_name: ""
mcp_servers:
  ToolServer: ""
secrets:
  api_key: "$secret:sec_xxx"

chat_hints: "One sentence describing what this workflow does and what input to provide."

input:
  field_name:
    type: string         # string, number, boolean, array, object
    required: true
    description: "What this field is for"

steps:
  step_name:
    call: <step_type>    # see step type reference below
    # ... step-specific fields
    output: result_var
    after: [dependency]  # omit for steps with no dependencies (they run in parallel)
    when: "${condition}" # optional conditional execution

output:
  result: ${steps.final_step.output}
```

### Step Type Reference

**agent** — Call an LLM agent:
```yaml
  analyze:
    call: agent
    agent: MyAgent
    input_template: "Analyze this: ${input.data}\nContext: ${steps.fetch.output}"
    output: analysis
```
CRITICAL: Always use `input_template:`, NEVER `input: {prompt: ...}`.

The `input_template` provides per-run context. The agent's permanent instructions
(created in step 3b) define its behavior. Together they form the full prompt:
  instructions (who you are, your workflow, output format) + input_template (this specific task data)

**function** — Call a Python function (deterministic, no LLM):
```yaml
  fetch_data:
    call: function
    function: my_fetcher
    input:
      url: "${input.api_url}"
    secrets:
      api_key: "$secret:sec_xxx"
    output: raw_data
```
Secrets are declared at the step level with `secrets:`, not in `input:`.

**mcp_tool** — Call a specific MCP tool directly (bypasses agent reasoning):
```yaml
  search:
    call: mcp_tool
    server: MyTools
    tool: semantic_search
    input:
      query: "${input.question}"
      kb_id: "${input.kb_id}"
    output: results
```

**handoff_router** — Route to specialists based on classification:
```yaml
  support:
    call: handoff_router
    entry_agent: Triage
    specialists:
      - agent: BillingAgent
        role: billing
      - agent: TechAgent
        role: technical
    input_template: "${input.message}"
    output: response
```
Runtime behavior: The platform injects `transfer_to_<role>` tools into the entry agent
(e.g., transfer_to_billing, transfer_to_technical). The entry agent classifies the input
and calls the appropriate transfer tool to route to a specialist.

CRITICAL: The entry agent MUST have max_llm_calls >= 2 (default is 20, which is fine).
If max_llm_calls is set to 1, the agent cannot call the transfer tool and routing
silently fails — the workflow completes but the specialist never executes.

Entry agent instructions should say: "Classify the intent and route immediately using
the transfer tools. Do NOT attempt to resolve the issue yourself."

**parallel_analyzer** — Run multiple agents in parallel and aggregate:
```yaml
  multi_review:
    call: parallel_analyzer
    agents:
      - agent: SecurityReviewer
        focus: "security vulnerabilities"
      - agent: PerfReviewer
        focus: "performance issues"
    aggregator_agent: Synthesizer
    input_template: "${input.pr_diff}"
    output: report
```
Runtime behavior: All analyst agents run concurrently. The aggregator receives a
formatted string with each analyst's output under a header:
  ## SecurityReviewer
  {security output}
  ## PerfReviewer
  {perf output}
The aggregator's instructions should expect this format.

**judge_loop** — Evaluate and retry until quality bar is met:
```yaml
  quality_check:
    call: judge_loop
    worker_agent: Writer
    judge_agent: Editor
    max_iterations: 3
    input_template: "Write copy for: ${input.product}"
    output: final_copy
```
Runtime behavior: On iteration 0, worker receives the input_template. On subsequent
iterations, worker receives: original input + "Previous feedback: {evaluator output}".
The evaluator receives the worker output and must respond with "PASS" if acceptable,
otherwise provide specific feedback. Loop exits when evaluator says PASS or max_iterations
reached. Default max_iterations is 5 if not specified.

The judge agent's instructions MUST include:
- A scoring rubric or checklist (e.g., "Evaluate on: accuracy, tone, completeness, length")
- A pass threshold (e.g., "Pass if score >= 8/10")
- A requirement to say "PASS" explicitly when criteria are met
- Actionable feedback format (not "make it better" — say exactly what to change)

**for_each** — Iterate over a collection:
```yaml
  process_items:
    call: for_each
    items: "${input.urls}"
    as: url
    max_iterations: 50
    do:
      fetch:
        call: function
        function: fetcher
        input:
          path: "${input.url}"
      summarize:
        call: agent
        agent: Summarizer
        after: [fetch]
        input_template: "Summarize: ${steps.fetch.output}"
    output: summaries
```
CRITICAL for_each syntax:
- Use `as:` (NOT `item_var:`) for the loop variable name
- Use `do:` (NOT `steps:`) for the nested steps block
- Access the loop variable as `${input.<var_name>}` (it's injected into the input object)
- Default max_iterations is 50. Returns a list of outputs, one per iteration.

**conditional** — Branch based on a value:
```yaml
  route:
    call: conditional
    condition: "${steps.triage.output.severity == 'P1'}"
    then:
      call: agent
      agent: UrgentResponder
      input_template: "URGENT: ${steps.triage.output}"
    else:
      call: agent
      agent: StandardResponder
      input_template: "${steps.triage.output}"
    output: response
```

**while** — Loop until a condition is false:
```yaml
  refine:
    call: while
    condition: "${steps.refine.output.needs_more == true}"
    max_iterations: 10
    do:
      check:
        call: agent
        agent: Checker
        input_template: "Check: ${steps.refine.output}"
    output: final_result
```
Default max_iterations is 10. Condition re-evaluated after each iteration using
current step outputs. Use for polling or iterative refinement when judge_loop
doesn't fit.

**connector** — Call a pre-built external integration (zero code):
```yaml
  notify:
    call: connector
    connector: slack
    action: send_message
    input:
      channel: "#alerts"
      text: "Done: ${steps.analysis.output.summary}"
    output: notification
```
Run `graphn connector list` to see available connectors and actions.

### Expression Syntax

| Pattern | Example |
|---------|---------|
| Workflow input | ${input.query} |
| Step output | ${steps.fetch.output} |
| Nested field | ${steps.triage.output.severity} |
| Default value | ${val \| default "fallback"} |
| Comparison | ${steps.check.output.score > 0.8} |
| Boolean | ${a && b}, ${a \|\| b} |

### Data Flow Patterns

**Sequential passthrough:**
step_a.output → ${steps.step_a.output} in step_b's input_template

**Fan-out / fan-in (split-and-merge):**
step_a splits into step_b and step_c (no after between them),
step_d merges with after: [step_b, step_c] and references both outputs.

**Conditional data flow:**
step_a → conditional (checks step_a.output) → then_branch OR else_branch → step_final

### Step 3g: Validate, Create, Publish, Run

```bash
# Validate DSL syntax before creating
graphn wf validate workflow.yaml

# Create the workflow (auto-links components by name)
graphn wf create --name "My Workflow" --dsl workflow.yaml   # capture wf_xxx

# Publish all components (agents, functions, MCP servers must be published before running)
graphn agent publish-all
graphn func publish-all
graphn mcp publish-all

# Test with a dry run
graphn wf dry-run <wf_id> --input '{"query": "test"}'

# Review the workflow structure
graphn wf describe <wf_id>

# Publish the workflow
graphn wf publish <wf_id> -m "v1 - initial release"

# Run it
graphn wf run <wf_id> --input '{"query": "real input"}'

# For long-running workflows
graphn wf run <wf_id> --input '{"query": "..."}' --mode async
graphn exec get <exec_id> --watch
```

### Verification

After each creation step, verify:

| Created | Verify with |
|---------|------------|
| Agent | `graphn agent get <id>` — check instructions, model, tools |
| Function | `graphn func test <id> --input '{...}'` — test with sample data |
| MCP Server | `graphn mcp tools <id>` — confirm tools discovered |
| Workflow | `graphn wf describe <id>` — verify structure and linked components |
| DSL file | `graphn wf validate workflow.yaml` — BEFORE creating |

If verification fails, fix with `update` + `publish` (not delete + recreate):
```bash
graphn agent update <id> --instructions new_prompt.txt && graphn agent publish <id> -m "Fix"
graphn func update <id> --code main.py && graphn func publish <id> -m "Fix"
```

---

## Worked Example: PR Review Workflow

Applying Pattern → Decomposition → Implementation end-to-end.

**Task:** Review a pull request from three angles (security, performance, test coverage) and synthesize a report.

**Phase 1 — Pattern:** Split-and-merge (3 independent reviews → synthesizer).

**Phase 2 — Decomposition:**
- 3 agent steps (security, perf, coverage) — all need LLM reasoning, no data deps between them → parallel
- 1 agent step (synthesizer) — merges results → after all three

**Phase 3 — Implementation:**

Create 4 agents (each with narrow instructions, JSON output format), then DSL:
```yaml
document:
  dsl: "1.0.0"
  name: "PR Multi-Angle Review"
  version: "0.1.0"
agents:
  SecurityReviewer: ""
  PerformanceReviewer: ""
  CoverageReviewer: ""
  ReportSynthesizer: ""
chat_hints: "I review pull requests from security, performance, and test coverage angles. Provide a PR diff and description."
input:
  pr_diff:
    type: string
    required: true
    description: "The pull request diff"
  pr_description:
    type: string
    required: true
    description: "PR description and context"
steps:
  security_review:
    call: agent
    agent: SecurityReviewer
    input_template: "PR: ${input.pr_description}\n\nDiff:\n${input.pr_diff}"
    output: security_result
  performance_review:
    call: agent
    agent: PerformanceReviewer
    input_template: "PR: ${input.pr_description}\n\nDiff:\n${input.pr_diff}"
    output: performance_result
  coverage_review:
    call: agent
    agent: CoverageReviewer
    input_template: "PR: ${input.pr_description}\n\nDiff:\n${input.pr_diff}"
    output: coverage_result
  synthesize:
    call: agent
    agent: ReportSynthesizer
    input_template: "Security: ${steps.security_review.output}\n\nPerformance: ${steps.performance_review.output}\n\nCoverage: ${steps.coverage_review.output}"
    after: [security_review, performance_review, coverage_review]
    output: report
output:
  result: ${steps.synthesize.output}
```

The three reviews have NO `after:` between them — they run in parallel automatically.
The synthesizer waits for all three via `after: [security_review, performance_review, coverage_review]`.

---

## Knowledge Base Integration

Two ways to give agents access to documents:

**Option A — Direct KB binding** (simple, platform-managed):
```bash
graphn kb create --name "product-docs" --description "Product documentation"
graphn kb upload <kb_id> ./docs/*.pdf
graphn kb stats <kb_id>  # wait for indexing
graphn agent create --name "DocAssistant" --model qwen3-80b \
  --instructions assistant.txt --knowledge-base "product-docs"
```
The agent automatically searches the KB when needed. No tool setup required.

**Option B — MCP search tools** (customizable, explicit control):
Create an MCP server with search tools (see Step 3d). Gives you control over
reranking, top_k, hybrid search, and result formatting.

| Factor | Direct KB | MCP Tools |
|--------|-----------|-----------|
| Setup effort | One flag | Create MCP server + code |
| Customization | None (platform defaults) | Full (reranking, filtering, formatting) |
| Agent control | Automatic search | Agent decides when/how to search |
| Use when | Simple Q&A, docs lookup | Complex RAG with preprocessing |

---

## Connectors

Connectors are pre-built, zero-code integrations for external services.
No code, no auth setup — just reference in DSL.

```yaml
  send_alert:
    call: connector
    connector: slack
    action: send_message
    input:
      channel: "#alerts"
      text: "Incident: ${steps.triage.output.summary}"
    after: [triage]
    output: slack_response
```

Run `graphn connector list` to see available connectors and actions.
Use connectors for Slack, email, webhooks. Use functions for custom API logic.

---

## Designing for Chat Mode

Workflows can be used interactively via `graphn chat --workflow "My Workflow"`.

**chat_hints** tells the user what to provide:
```yaml
chat_hints: "Ask a question about our products. Provide the knowledge base ID if you have one."
```

**Chat-friendly workflow design:**
- Keep total execution under 30 seconds for good UX
- Use clear, human-readable output (markdown, not raw JSON)
- Make optional inputs truly optional with defaults
- For long workflows, use `--mode async` and let the user poll

---

## Debugging Failed Workflows

When a workflow fails, use these tools in order:

**1. Check health first:**
```bash
graphn wf health <wf_id>
```
Shows: component status, publish state, max_llm_calls, tool discovery, recent success rate.
Catches: unpublished components, agents with max_llm_calls=0, MCP servers with 0 tools.

**2. Inspect the execution trace:**
```bash
graphn logs <exec_id> --analyze
```
Shows: step timeline with durations, inputs/outputs per step, bottleneck detection,
parallel efficiency. Use `--full` for complete (untruncated) I/O.

**3. Watch a live execution:**
```bash
graphn exec get <exec_id> --watch   # polls every 2s until terminal state
```

**4. Deep validation:**
```bash
graphn wf validate workflow.yaml --deep   # checks components exist, not just syntax
```

**Common failure causes:**
- Agent with max_llm_calls=1 can't use tools or transfer → increase to default (20)
- MCP server not published → tools not discovered → agent has no tools
- Function timeout → increase timeout or add error handling
- Step output > 10MB → reduce output size, summarize large results
- input.prompt instead of input_template → agent receives empty input
- `${!steps.X.output}` fails — negation operator `!` is not supported in expressions.
  Use `${steps.X.output == false}` instead.

**CRITICAL: Compound steps cannot reference outer step outputs.**
Compound steps (judge_loop, parallel_analyzer, handoff_router) have limited access to
outputs from steps outside the compound step. If your judge_loop input_template references
`${steps.triage.output}` or `${steps.fetch.output}`, the expressions may NOT resolve — the
worker agent receives literal `${steps...}` text instead of actual data.

**Workaround:** Add an intermediate agent step before the compound step that compiles all
upstream data into a single output. Then reference only that one step:

```yaml
  # BAD: judge_loop tries to reference multiple outer steps
  review:
    call: judge_loop
    worker_agent: Writer
    judge_agent: Reviewer
    input_template: "Data: ${steps.fetch.output}\nAnalysis: ${steps.triage.output}"  # MAY NOT RESOLVE

  # GOOD: intermediate step compiles data, judge_loop references only one step
  compile:
    call: agent
    agent: Compiler
    input_template: "Data: ${steps.fetch.output}\nAnalysis: ${steps.triage.output}"
    after: [fetch, triage]
    output: compiled_context

  review:
    call: judge_loop
    worker_agent: Writer
    judge_agent: Reviewer
    input_template: "${steps.compile.output}"  # single reference, resolves correctly
    after: [compile]
    output: final_report
```
This pattern also applies to handoff_router and parallel_analyzer — keep their
input_template simple, with at most one outer step reference.

---

## Cost & Latency Optimization

**Model right-sizing:**
- Don't use qwen3-235b for classification — qwen3-30b is 8x faster for simple tasks
- Use qwen3-80b (default) unless you have a reason to go bigger or smaller
- Triage/routing agents: always qwen3-30b (fast classification is all they do)

**Reduce LLM calls:**
- Use functions instead of agents for deterministic work (API calls, transforms)
- Set `max_llm_calls` explicitly — don't leave at 25 if the agent only needs 1-3

**Maximize parallelism:**
- Remove unnecessary `after:` dependencies — steps without after run in parallel
- In split-and-merge, the wall-clock time equals the slowest branch, not the sum

**Keep outputs lean:**
- Large outputs slow down expression evaluation and may hit the 10MB limit
- Have agents summarize rather than pass through raw data
- Functions should return only the fields downstream steps need

---

## Quick-Start Shortcuts

**Scaffold boilerplate:**
```bash
graphn scaffold agent --name "MyAgent"       # creates instructions.txt template
graphn scaffold function --name "my_func"    # creates main.py + requirements.txt
graphn scaffold mcp-server --name "MyTools"  # creates server.py + requirements.txt
graphn scaffold workflow --name "MyFlow"     # creates workflow.yaml template
```

**Clone and customize an existing workflow:**
```bash
graphn wf clone "RAG Research Assistant" --name "My Custom RAG"
# Clones all agents, functions, MCP servers + workflow. Edit and republish.
```

**Deploy a blueprint as a starting point:**
```bash
graphn bp list                    # see all 10 templates
graphn bp info rag-research       # inspect code before deploying
graphn bp deploy rag-research     # deploy with one command
```

---

## Platform Notes & Limits

**Agent defaults & limits:**
- Default model: qwen3-80b
- Default timeout: 120 seconds (range: 10–900)
- Default max_llm_calls: 20 (range: 1–100)
- Agents need max_llm_calls >= 2 to use tools or make handoff transfers

**Model selection guide:**
- `qwen3-30b` — Fast. Use for classification, routing, triage, simple extraction.
- `qwen3-80b` — Balanced (default). Use for synthesis, writing, multi-step reasoning.
- `qwen3-235b` — Strongest. Use for complex analysis where quality is critical.

**Function runtime:**
- Python 3.11, 8GB RAM, internet access, `httpx` pre-installed
- Default timeout: 300 seconds (max 900)
- Secrets injected as kwargs matching the secret name

**Loop iteration defaults:**
- for_each: max 50 iterations
- judge_loop: max 5 iterations
- while: max 10 iterations

**Parallelism:** Steps with no `after:` field run in parallel automatically.
The executor groups steps by topological depth and runs each group concurrently.

**Expression evaluation:** A single expression like `${steps.X.output}` returns the
typed value (dict, list, number). Multiple expressions in a string like
`"Score: ${steps.X.output.score} out of 10"` return an interpolated string.
Agent outputs that are valid JSON are auto-parsed — you can access fields directly
(e.g., `${steps.analyze.output.severity}`) without manual parsing.

**Output size limit:** Step outputs are capped at 10MB at the transport layer.
Larger outputs cause the execution to fail. Have agents summarize large results.

**MCP tool discovery:** MCP servers must be published before workflow execution.
Tool discovery runs on create/update/publish for hosted servers. If tools aren't
discovered, the agent won't see them — run `graphn mcp tools <id>` to verify.

**Compound step limitations:**
- parallel_analyzer, judge_loop, and handoff_router may not pass MCP tools to their
  sub-agents. If you need tool access, use individual agent steps with `after:` dependencies.
- Validator may warn "agent declared but not referenced" for agents inside compound steps
  (judge_loop worker/judge, handoff_router specialists, conditional branches). These are
  false positives — the workflow is correct.

**CLI output:** All commands return JSON. Warnings go to stderr.

## Deep Reference

For full DSL schema, foundry_helpers API, and command reference:
  `graphn docs skills dsl-schema` — DSL schema, step types, expressions
  `graphn docs skills dsl-commands` — CLI command reference
  `graphn docs skills dsl-helpers` — foundry_helpers Python API
  `graphn docs skills dsl-api` — REST API reference
