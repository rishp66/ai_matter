# Skill: DSL Schema

**IMPORTANT**: All DSL YAML must be wrapped in a `document:` block. Every example below assumes this wrapper:

```yaml
document:
  dsl: "1.0.0"
  name: "My Workflow"
  version: "0.1.0"
# ... agents, functions, input, steps, output sections go here
```

## Full DSL Schema (1.0.0)

```yaml
document:
  dsl: "1.0.0"
  name: "Workflow Name"
  version: "0.1.0"

# Declare components used by this workflow (name: "" or name: "res://agents/id")
agents:
  MyAgent: ""
functions:
  my_function: ""
mcp_servers:
  MyTools: ""
secrets:
  api_key: "$secret:secret_id"

chat_hints: |
  Tell the user what this workflow does and what inputs it expects.
  Example: "I investigate production alerts. Give me an alert description or paste an AlertManager payload."

# Input schema
input:
  query:
    type: string          # string | number | boolean | object | array
    required: true
    description: "Search query"
    default: ""           # optional default value

# Execution steps (DAG)
steps:
  step_name:
    call: agent           # step type (see below)
    agent: MyAgent        # resource reference
    input_template: "${input.query}"
    output: result_var    # output key name
    after: [prev_step]    # explicit dependencies
    when: "${input.mode == 'full'}"  # guard condition (optional)

# Workflow output
output:
  result: ${steps.step_name.output}
```

## Input Schema Best Practices

The DSL `input:` block is automatically extracted as `input_schema` when the
workflow is created or updated via the CLI. This schema powers:
- **Chat mode**: the LLM learns what parameters to collect before executing
- **Web UI**: the test panel shows proper input fields
- **API docs**: the workflow API panel shows typed parameters

Always include `type`, `required`, and `description` for each input field:

```yaml
input:
  query:
    type: string
    required: true
    description: "The search query to research"
  files:
    type: array
    required: false
    description: "Optional PDF files to include"
```

## Output Key Convention

The workflow output section MUST use `result` as the key name. The web UI and chat mode
both have hardcoded logic that looks for a `result` key to display output cleanly.
Using custom names like `answer`, `response`, or `summary` will cause the UI to show raw JSON
instead of clean text.

```yaml
# CORRECT — web and chat render this cleanly
output:
  result: ${steps.final_step.output}

# WRONG — UI shows raw JSON object
output:
  answer: ${steps.final_step.output}
```

## chat_hints (Conversational UX)

`chat_hints` is a top-level string that tells the chat UI what the workflow does and what inputs it expects.
When users run a workflow in chat mode, this text is shown as guidance. Always include it.

```yaml
chat_hints: |
  I am an ops investigator. Describe a production alert or paste an AlertManager webhook payload.
  I will check pod health, logs, events, and resource pressure, then produce a diagnosis with remediation steps.
```

Tips for writing chat_hints:
- First person ("I do X") — the workflow speaks as itself
- State what it does and what input it needs
- Mention supported input formats (free text, JSON, file, etc.)
- Keep it 2-3 sentences max

## Step Types

**agent** — Execute an LLM agent with tools
```yaml
step_name:
  call: agent
  agent: AgentName
  input_template: "Analyze: ${input.query}"
  output: analysis
```

**function** — Execute custom Python code
```yaml
step_name:
  call: function
  function: my_function
  input:
    text: ${steps.prev.output}
  secrets:
    api_key: "$secret:my_api_key"
  output: processed
```

**mcp_tool** — Call a single MCP tool directly
```yaml
step_name:
  call: mcp_tool
  server: MyTools
  tool: semantic_search
  input:
    query: ${input.query}
    top_k: 5
  output: search_results
```

**connector** — Built-in external integration (no create/link needed — platform-level)

Discover available connectors and their actions:
```bash
graphn connector list
```

Prefer connectors over custom functions when a supported integration exists.
Connectors are platform-managed, require no code, and handle auth/retries automatically.

```yaml
step_name:
  call: connector
  connector: slack          # provider id from catalog
  action: send_message      # action supported by the provider
  input:
    channel: "#alerts"
    text: "Result: ${steps.analysis.output}"
```

**handoff_router** — Triage agent routes to specialists
```yaml
step_name:
  call: handoff_router
  entry_agent: Triage_Agent
  specialists:
    - agent: Order_Specialist
      role: orders
    - agent: Returns_Specialist
      role: returns
    - agent: Product_Advisor
      role: products
  input_template: "Customer: ${input.message}"
  output: response
```

**CRITICAL**: The `entry_agent` MUST have `max_llm_calls >= 2` (recommended: 25). With `max_llm_calls: 1`, the entry agent cannot call the auto-injected `transfer_to_*` tools, causing silent fallthrough — the workflow reports success but the specialist is never called.

**parallel_analyzer** — Run analysts concurrently, then aggregate
```yaml
step_name:
  call: parallel_analyzer
  analysts:
    - agent: Security_Analyst
      role: analyst
    - agent: Infrastructure_Analyst
      role: analyst
  aggregator: Incident_Commander
  input_template: "Alert: ${input.alert}"
  output: report
```

**judge_loop** — Generate, evaluate, iterate until passing
```yaml
step_name:
  call: judge_loop
  generator: Writer
  evaluator: Critic
  pass_condition: "${steps.refine.output.approved == true}"
  max_iterations: 3
  input_template: "Write about: ${input.topic}"
  output: final_draft
```
Note: `pass_condition` must reference the judge_loop step's own output (e.g. `${steps.refine.output.approved == true}` where "refine" is the step name).

The **evaluator** agent must have `max_llm_calls >= 2` (recommended: 25) so it can complete its evaluation (including any tool use the platform injects for the judge loop).

**for_each** — Loop over a list (default max_iterations: 50)
```yaml
step_name:
  call: for_each
  items: ${input.files}
  as: file
  max_iterations: 50
  do:
    process:
      call: function
      function: process_file
      input:
        path: ${input.file}
      output: processed
  output: all_results
```
Notes:
- The loop variable (set by `as:`) is injected into `input`, so access it as `${input.file}` (not `${steps.file}`).
- `for_each` returns a list of outputs, one per iteration.
- Default `max_iterations` is 50 if not specified.

**while** — Loop until condition is false
```yaml
step_name:
  call: while
  condition: "${steps.check.output.needs_more}"
  max_iterations: 10
  do:
    fetch:
      call: function
      function: fetch_page
      output: page_data
    check:
      call: function
      function: check_complete
      output: status
  output: collected
```
Notes:
- The first iteration always runs. The condition is checked starting from the second iteration.
- The `while` loop shares context -- each iteration can see outputs from previous iterations.

**conditional** — Evaluates an expression and stores the boolean result as output. Downstream steps branch using `when`.
```yaml
step_name:
  call: conditional
  condition: "${input.include_summary == true}"
  output: should_summarize
```
Notes:
- Evaluates the expression and stores the result as a boolean output.
- Downstream steps use `when: "${steps.should_summarize.output}"` to branch.
- It does NOT wrap or guard another step inline.
- If a step's `when` guard evaluates false, the step is skipped and no output is stored.

## Expression Syntax

All expressions use `${ }` delimiters:

| Expression | Description |
|-----------|-------------|
| `${input.field}` | Workflow input field |
| `${input.nested.field}` | Nested input access |
| `${steps.step_name.output}` | Step output reference |
| `${steps.step_name.output.key}` | Nested step output |
| `${steps.X.output \| default "fallback"}` | Default value |
| `${input.mode == 'full'}` | Comparison (==, !=, <, >, <=, >=) |
| `${cond1 && cond2}` | Boolean AND |
| `${val1 \|\| val2}` | Boolean OR / coalesce |

Rules:
- If entire string is one expression, returns typed value (not string)
- If expressions mixed with text, returns interpolated string
- If a step returns a JSON string, the runtime auto-parses it so downstream steps can traverse fields
- Unknown fields in step definitions are silently ignored -- no validation error
