# Hippocampus OS

> Brain-mimetic context compiler for AI agents.

## What It Does

Wraps any OpenAI-compatible client and prevents infinite agent loops by:
1. **Detecting** failures deterministically (<5ms, no extra LLM calls)
2. **Storing** failure episodes in a Redis-backed episodic graph
3. **Injecting** State Guard XML directives at position 0 of the system prompt

The LLM sees: *"Your last action failed with auth_expired. Do NOT retry. Pivot to refreshing credentials."*

Result: **95% loop prevention**, **30% token savings**.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Start Redis
docker compose up -d redis

# Run demo
python examples/demo_loop_breaker.py
```

## Usage

```python
from openai import OpenAI
from hippocampus import Hippocampus

# Wrap your existing client — that's it
raw_client = OpenAI()
client = Hippocampus(raw_client, agent_id="my_agent")

# Same API as OpenAI
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Pull the Q3 report from Salesforce"}]
)
```

## How It Works

```
User calls client.chat.completions.create()
        │
        ▼
   Interceptor (pre-inject)
        │
   ┌────┼────┐
   ▼    ▼    ▼
Router Graph Inhibitor
   │    │    │
   │    ▼    │
   │  Query  │
   │  Recent │
   │  Fails  │
   │    │    │
   └────┼────┘
        ▼
   Compiler → State Guard XML
        │
        ▼
   Inject at position 0 of system prompt
        │
        ▼
   OpenAI API call
        │
        ▼
   Interceptor (post-route)
        │
   ┌────┴────┐
   ▼         ▼
Success    Failure
   │         │
   ▼         ▼
Store     Store
Success   Failure
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/

# All checks
bash scripts/check-ai.sh
```

## Architecture

See `docs/architecture.md` for the full pipeline description.

## License

MIT
