# Hippocampus OS — Data & API Contracts

## Core Entities

### EpisodicNode
```
node_id:       string, required, format "intent_{hash12}" | "action_{hash12}" | "fail_{hash12}"
agent_id:      string, required
node_type:     enum("intent", "action", "result", "fail"), required
content:       string, required
timestamp:     float, required, unix epoch seconds
relevance_score: float, default 1.0, range [0.01, 1.0]
ttl_seconds:   int, default 86400
```

### EpisodicEdge
```
from_node:  string, required (node_id)
to_node:    string, required (node_id)
edge_type:  enum("ATTEMPTED_WITH", "FAILED_WITH", "SUCCEEDED_WITH"), required
timestamp:  float, required, unix epoch seconds
```

### RouteResult
```
is_failure:  bool, required
is_success:  bool, required
error_type:  FailureType | None, required
detail:      string, required
```

### FailureType (Enum)
```
AUTH_EXPIRED       = "auth_expired"
RATE_LIMITED       = "rate_limited"
NOT_FOUND          = "not_found"
SERVER_ERROR       = "server_error"
PERMISSION_DENIED  = "permission_denied"
VALIDATION_ERROR   = "validation_error"
APOLOGY_LOOP       = "apology_loop"
NONE               = "none"
```

### StateGuard (Compiled)
```
action:    string, required
error_type: string, required
detail:    string, required, max 150 chars
severity:  enum("critical", "high", "medium"), required
directive: string, required
```

### HippocampusConfig
```
redis_url:          string, default "redis://localhost:6379"
default_ttl:        int, default 86400 (24 hours)
max_guards:         int, default 3 (max State Guards per injection)
inhibition_threshold: float, default 0.1 (relevance below this = suppress)
high_relevance:     float, default 0.5 (above this = always inject)
medium_relevance:   float, default 0.2 (above this = inject if related)
```

## Public API (User-Facing)

### Hippocampus(client, agent_id, config?)
- `client`: `openai.OpenAI` instance
- `agent_id`: string, unique identifier for this agent
- `config`: optional `HippocampusConfig`
- Returns: `Hippocampus` instance with `.chat.completions.create()` proxy

### Hippocampus.chat.completions.create(**kwargs)
- Same signature as `openai.OpenAI.chat.completions.create()`
- Intercepts messages, injects State Guards, routes response
- Returns: unmodified OpenAI response object

### Hippocampus.graph.add_failure(agent_id, intent, action, error, error_detail)
- Stores a failure episode
- Returns: node_id of the fail node

### Hippocampus.graph.add_success(agent_id, intent, action)
- Stores a success episode
- Returns: node_id of the action node

### Hippocampus.graph.get_recent_failures(limit=5)
- Returns: list of failure dicts with relevance scores

### Hippocampus.graph.check_action_failed_recently(action)
- THE key query for loop prevention
- Returns: failure dict or None

## Schema Stability Policy

Any change to these entities or the public API must:
1. Be documented in an ADR (adrs/000X-...)
2. Maintain backward compatibility (no breaking changes)
3. Update this file BEFORE code changes
4. Include migration notes if Redis key format changes
