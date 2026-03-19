# Hippocampus OS — Architecture

## System Shape

```
User Code                   Hippocampus OS                  Redis
─────────                   ──────────────                  ─────

openai.Client ──────► Hippocampus(client) 
                         │
                         ▼
                      Interceptor
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          Router      Graph     Inhibitor
         (classify)  (store)   (filter)
              │          │          │
              │          ▼          │
              │     EpisodicGraph  │
              │     (Redis hashes) │
              │          │          │
              └──────────┼──────────┘
                         ▼
                      Compiler
                   (State Guard XML)
                         │
                         ▼
                   Inject at pos 0
                   of system prompt
                         │
                         ▼
                   openai.Client
                   .chat.completions
                   .create(**kwargs)
                         │
                         ▼
                     Response
```

## Pipeline (6 stages)

| Stage | Component | Input | Output | Latency |
|-------|-----------|-------|--------|---------|
| 1. Intercept | `Interceptor` | kwargs from user | Extracted messages | <1ms |
| 2. Route | `StateRouter` | LLM response text | `RouteResult` | <5ms |
| 3. Store | `EpisodicGraph` | Failure episode | Redis hash written | <5ms |
| 4. Inhibit | `TemporalInhibitor` | Current context + graph | Filtered failures | <5ms |
| 5. Compile | `StateGuardCompiler` | Filtered failures | XML string | <1ms |
| 6. Inject | `Interceptor` | XML + messages | Modified messages | <1ms |

Total overhead: <17ms per call (negligible vs LLM latency of 500-2000ms).

## Data Flow

### On LLM Call (Pre-injection)
1. User calls `client.chat.completions.create(messages=[...])`
2. Interceptor extracts last user message
3. Inhibitor queries graph for relevant failures
4. Compiler converts failures to State Guard XML
5. XML is prepended to system message (position 0)
6. Modified messages are sent to real OpenAI client

### On LLM Response (Post-routing)
1. Response arrives from OpenAI
2. Router classifies response content (regex, <5ms)
3. If failure detected → graph stores: INTENT → ACTION → FAIL
4. If success detected → graph stores: INTENT → ACTION → SUCCESS
5. Original response is returned to user (unchanged)

## Data Model (Redis)

### Node (Redis Hash)
Key: `hippo:{agent_id}:node:{node_id}`
Fields:
- node_id: string (e.g., "fail_a1b2c3d4e5f6")
- agent_id: string
- node_type: "intent" | "action" | "result" | "fail"
- content: string
- timestamp: float (unix epoch)
- relevance_score: float (0.0-1.0)
- ttl_seconds: int (default 86400)

### Edge (Redis Set)
Key: `hippo:{agent_id}:edges:{from_node_id}`
Members: "{to_node_id}:{edge_type}"
Edge types: "ATTEMPTED_WITH" | "FAILED_WITH" | "SUCCEEDED_WITH"

### Recent Failures (Redis Sorted Set)
Key: `hippo:{agent_id}:recent_failures`
Members: "{action_id}|{error_type}|{error_detail}"
Score: timestamp

## Design Decisions

### Why Redis, not Postgres?
- SDK product — no server/DB to manage
- Sub-ms reads for real-time injection
- TTL built-in (failures decay naturally)
- Docker: `redis:7-alpine` is 30MB, Postgres is 400MB

### Why Deterministic Routing (Tier 1 only)?
- 80% of failures match regex patterns (403, 429, 500, apology loops)
- <5ms latency, zero token cost
- No extra LLM call needed
- Tier 2 (LLM-based) can be added later without breaking API

### Why XML for State Guards?
- XML is a strong attention signal for LLMs
- Tags like `<STATE_GUARD priority="critical">` are un-ignorable
- Position 0 of system prompt = maximum attention weight
- Structured format prevents the LLM from "summarizing away" the directive

### Why 24h TTL?
- Episodic memory = recent, not permanent
- Old failures become irrelevant (services recover, auth refreshes)
- Prevents context bloat
- Configurable via `HippocampusConfig`
