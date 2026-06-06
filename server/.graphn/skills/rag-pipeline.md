# Skill: Building RAG Pipelines

## Overview

RAG (Retrieval-Augmented Generation) workflows search a knowledge base and use the results
to ground LLM responses with real data.

## Quick Start: Deploy the Blueprint

```bash
graphn bp deploy rag-research
```

This creates a complete RAG pipeline. Use `graphn bp info rag-research` to see the full code.

## Build from Scratch

### Step 1: Create a Knowledge Base

```bash
# Discover supported embedding models, vector sizes, and modalities (text, image)
graphn kb models

# Default model is text-only BAAI/bge-m3. Pick a multimodal model when you
# also want to ingest images via presigned URLs. embedding_model is immutable
# after creation, so choose deliberately up front.
graphn kb create --name "my-docs" --description "Product documentation"
# Or, for multimodal:
# graphn kb create --name "my-docs" --model Qwen/Qwen3-VL-Embedding-8B

# Capture the returned kb_xxx ID and use it for all subsequent commands
graphn kb upload <kb_id> ./docs/guide.pdf
graphn kb upload <kb_id> ./docs/faq.md

# Image ingest is URL-only and only works on multimodal KBs (1 image = 1 vector)
# graphn kb ingest-url <kb_id> https://example.com/diagram.png

graphn kb stats <kb_id>  # verify documents are indexed
```

### Step 2: Create an MCP Server with Search Tools

```bash
cat > main.py << 'PYEOF'
from fastmcp import FastMCP
from foundry_helpers import kb

mcp = FastMCP("SearchTools")

@mcp.tool()
async def semantic_search(query: str, top_k: int = 5) -> list:
    """Search the knowledge base for relevant documents."""
    results = await kb.search("KB_ID_HERE", query, top_k=top_k, rerank=True)
    return results
PYEOF
echo "fastmcp" > requirements.txt
graphn mcp create --name "SearchTools" --code main.py
graphn mcp tools <mcp_id>  # verify tool discovery (use ID from create output)
```

### Step 3: Create a Research Agent

```bash
cat > instructions.txt << 'EOF'
## Role
You are a research agent with access to a knowledge base.

## Tools
Use semantic_search to find relevant information before answering.

## Output Format
Provide a clear answer with citations from the search results.

## Constraints
- NEVER hallucinate or make up information
- Always cite which documents your answer comes from
- If no relevant results found, say so explicitly
EOF
graphn agent create --name "Researcher" --model qwen3-80b --instructions instructions.txt \
  --tools "SearchTools:semantic_search"
```

### Step 4: Write the Workflow DSL

```bash
cat > workflow.yaml << 'EOF'
document:
  dsl: "1.0.0"
  name: "RAG Research"
  version: "0.1.0"
agents:
  Researcher: ""
chat_hints: "I research topics using a knowledge base. Ask me a question or provide a topic to investigate."
input:
  query:
    type: string
    required: true
    description: "Research question"
steps:
  research:
    call: agent
    agent: Researcher
    input_template: "Research this question: ${input.query}"
    output: answer
output:
  result: ${steps.research.output}
EOF
graphn wf create --name "RAG Research" --dsl workflow.yaml
# Capture the returned wf_xxx ID and use it for ALL subsequent commands
```

### Step 5: Test, Publish, and Run

```bash
# Publish components first
graphn agent publish-all && graphn func publish-all && graphn mcp publish-all

# Dry-run
graphn wf dry-run <wf_id> --input '{"query": "How does authentication work?"}'

# Publish and run production
graphn wf publish <wf_id> -m "Initial RAG pipeline"
graphn wf run <wf_id> --input '{"query": "How does authentication work?"}'

# For long-running workflows, use async + poll
graphn wf run <wf_id> --mode async --input '{"query": "..."}'
# Returns an execution ID — poll until complete:
graphn exec get <exec_id> --watch
```

## Advanced: Multi-stage RAG with Ingestion

For document ingestion pipelines, check:
```bash
graphn bp info kb-ingestion
```

This blueprint shows how to OCR documents, chunk them, and ingest into a KB using for_each loops.

## Tips

- Use `rerank=True` in kb.search for better result quality
- Set `top_k=10` for complex questions, `top_k=3` for simple lookups
- Structure agent instructions with ## sections for clarity
- Always include prohibitions (NEVER hallucinate, etc.)
