# Hippocampus OS — Architecture

## System Shape

```mermaid
graph TD
    A["User Code<br/>(OpenAI Client)"] -->|wraps| B["Hippocampus Wrapper<br/>(Drop-in Replacement)"]
    
    B -->|intercepts| C["Interceptor<br/>(Pipeline Orchestrator)"]
    
    C -->|pre_inject| D["Pre-Injection Stage"]
    C -->|post_route| E["Post-Routing Stage"]
    
    D --> D1["StateRouter<br/>(Classify Failures)<br/>&lt;5ms"]
    D --> D2["EpisodicGraph<br/>(Query Recent Failures)<br/>Redis Backend"]
    D --> D3["TemporalInhibitor<br/>(Filter Relevance)<br/>3-Tier Logic"]
    
    D1 --> D4["StateGuardCompiler<br/>(Generate Directives)<br/>XML at Position 0"]
    D2 --> D4
    D3 --> D4
    
    D4 -->|inject| F["Modified Messages<br/>(With State Guards)"]
    
    F -->|call| G["OpenAI API<br/>(chat.completions.create)"]
    
    G -->|response| E
    
    E --> E1["Route Result<br/>(Classify Response)"]
    E1 -->|store| E2["EpisodicGraph<br/>(Persist Episode)<br/>Intent → Action → Result"]
    
    E2 -->|return| H["Response to User<br/>(Unchanged)"]
    
    style A fill:#f0f4f8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style B fill:#e8f0f8,stroke:#3d5a80,stroke-width:3px,color:#1a1a1a
    style C fill:#e0ecf8,stroke:#4a6fa8,stroke-width:2px,color:#1a1a1a
    style D fill:#f5f7fa,stroke:#9ca3af,stroke-width:1px,color:#1a1a1a
    style E fill:#f5f7fa,stroke:#9ca3af,stroke-width:1px,color:#1a1a1a
    style D1 fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style D2 fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style D3 fill:#fef5e8,stroke:#9b7d54,stroke-width:2px,color:#1a1a1a
    style D4 fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style F fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
    style G fill:#fce8d8,stroke:#9a6f54,stroke-width:2px,color:#1a1a1a
    style E1 fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style E2 fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style H fill:#e8f0f8,stroke:#4a6fa8,stroke-width:2px,color:#1a1a1a
```

## Pipeline (6 stages)

```mermaid
sequenceDiagram
    participant User as 👤 User Code
    participant H as 🧠 Hippocampus
    participant I as 🔄 Interceptor
    participant R as 📊 Router
    participant G as 💾 Graph
    participant C as 📝 Compiler
    participant API as 🚀 OpenAI API
    
    User->>H: chat.completions.create(...)
    activate H
    H->>I: pre_inject(messages)
    activate I
    
    I->>R: route() - classify failures
    I->>G: get_recent_failures()
    I->>C: compile(failures) → XML
    I-->>H: modified_messages
    deactivate I
    
    H->>API: chat.completions.create(modified_messages)
    activate API
    API-->>H: response
    deactivate API
    
    H->>I: post_route(response)
    activate I
    I->>R: route(content)
    I->>G: add_failure() or add_success()
    I-->>H: RouteResult
    deactivate I
    
    H-->>User: response (unchanged)
    deactivate H
    
    Note over H: Total overhead: <17ms
    Note over API: LLM latency: 500-2000ms
```

| Stage | Component | Input | Output | Latency |
|-------|-----------|-------|--------|---------|
| 1️⃣ **Intercept** | `Interceptor` | kwargs from user | Extracted messages | <1ms |
| 2️⃣ **Route** | `StateRouter` | LLM response text | `RouteResult` | <5ms |
| 3️⃣ **Store** | `EpisodicGraph` | Failure episode | Redis hash written | <5ms |
| 4️⃣ **Inhibit** | `TemporalInhibitor` | Current context + graph | Filtered failures | <5ms |
| 5️⃣ **Compile** | `StateGuardCompiler` | Filtered failures | XML string | <1ms |
| 6️⃣ **Inject** | `Interceptor` | XML + messages | Modified messages | <1ms |

**Total overhead: <17ms per call** (negligible vs LLM latency of 500-2000ms).

## Data Flow

### On LLM Call (Pre-injection)

```mermaid
graph LR
    A["User Message<br/>(Input)"]
    B["Extract Intent<br/>(Last Message)"]
    C["Query Graph<br/>(Recent Failures)"]
    D["Filter Relevant<br/>(3-tier Logic)"]
    E["Compile Guards<br/>(State Guard XML)"]
    F["Inject at Position 0<br/>(System Message)"]
    G["Send to OpenAI<br/>(With Guards)"]
    
    A --> B --> C --> D --> E --> F --> G
    
    style A fill:#f0f4f8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style B fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style C fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style D fill:#fef5e8,stroke:#9b7d54,stroke-width:2px,color:#1a1a1a
    style E fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style F fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
    style G fill:#fce8d8,stroke:#9a6f54,stroke-width:2px,color:#1a1a1a
```

**Pre-injection Process:**
1. User calls `client.chat.completions.create(messages=[...])`
2. Interceptor extracts last user message for relevance matching
3. Inhibitor queries Redis for recent failures (TTL-based)
4. Filter by 3-tier relevance logic: high (≥0.5) / medium (≥0.2) / low (<0.2)
5. Compiler converts failures to State Guard XML directives
6. XML prepended to system message at position 0
7. Modified messages sent to OpenAI with full context engineering applied

### On LLM Response (Post-routing)

```mermaid
graph LR
    A["Response<br/>(From OpenAI)"]
    B["Route Content<br/>(Classify)"]
    C{Failure<br/>Detected?}
    D["Store Failure<br/>(Intent → Action → Fail)"]
    E["Store Success<br/>(Intent → Action → Success)"]
    F["Return Response<br/>(Unchanged)"]
    
    A --> B --> C
    C -->|Yes| D --> F
    C -->|No| E --> F
    
    style A fill:#f0f4f8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style B fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style C fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
    style D fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style E fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style F fill:#f0f4f8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
```

**Post-routing Process:**
1. Response arrives from OpenAI
2. Router classifies response content using deterministic regex patterns (<5ms)
3. If failure detected (403, 429, 500, etc.) → store failure episode in graph
4. If success detected → store success episode (temporal anchoring for future inhibition)
5. Original response returned to user unchanged (no mutation)

## Data Model (Redis)

### Node Structure (Redis Hash)

```mermaid
graph LR
    A["Redis Hash<br/>(hippo:agent:node:id)"] --> B["node_id<br/>(fail_a1b2c3d4e5f6)"]
    A --> C["agent_id<br/>(analyst_demo)"]
    A --> D["node_type<br/>(intent/action/fail/success)"]
    A --> E["content<br/>(Query text)"]
    A --> F["timestamp<br/>(unix epoch)"]
    A --> G["relevance_score<br/>(0.0 - 1.0)"]
    A --> H["ttl_seconds<br/>(86400 default)"]
    
    style A fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style B fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style C fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style D fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style E fill:#fef5e8,stroke:#9b7d54,stroke-width:2px,color:#1a1a1a
    style F fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style G fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
    style H fill:#fce8d8,stroke:#9a6f54,stroke-width:2px,color:#1a1a1a
```

### Episode Flow (Graph Edges)

```mermaid
graph LR
    A["Intent Node<br/>(Agent Goal)"] -->|ATTEMPTED_WITH| B["Action Node<br/>(Tool Called)"]
    B -->|FAILED_WITH| C["Failure Node<br/>(403 Auth Expired)"]
    B -->|SUCCEEDED_WITH| D["Success Node<br/>(Data Returned)"]
    
    C -->|Stored in<br/>Sorted Set| E["Recent Failures<br/>(Score: timestamp)"]
    D -->|Stored in<br/>Sorted Set| F["Recent Successes<br/>(Score: timestamp)"]
    
    style A fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style B fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style C fill:#fde8e8,stroke:#9a5a6f,stroke-width:2px,color:#1a1a1a
    style D fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style E fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style F fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
```

**Storage Architecture:**
- **Node**: Redis Hash with complete episode metadata
- **Edge**: Redis Set with edge type (ATTEMPTED_WITH, FAILED_WITH, SUCCEEDED_WITH)
- **Recent Failures**: Redis Sorted Set (score = timestamp) for fast TTL-based queries
- **Recent Successes**: Redis Sorted Set for temporal anchoring (prevents stale failures)

## Design Decisions

### Why Redis, not PostgreSQL?

```mermaid
graph LR
    A["Redis 7 Alpine<br/>(30MB image)<br/>(Sub-ms reads)<br/>(TTL built-in)<br/>(No server)"] -->|vs| B["PostgreSQL<br/>(400MB image)<br/>(10-50ms latency)<br/>(Manual cleanup)<br/>(Schema management)"]
    
    C["Selected<br/>Redis"] --> D["Optimized for<br/>(Real-time injection)<br/>(Episodic memory)<br/>(Lightweight SDK)"]
    
    style A fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
    style B fill:#fde8e8,stroke:#9a5a6f,stroke-width:2px,color:#1a1a1a
    style C fill:#e6f5e8,stroke:#5a7f6f,stroke-width:3px,color:#1a1a1a
    style D fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
```

### Why Deterministic Routing (Tier 1 only)?

**Failure Distribution:**
- 80% match deterministic regex patterns (403, 429, 500, apology loops)
- 20% other patterns requiring semantic analysis

**Tier 1 (Deterministic):**
- Covers 80% of real-world failures
- Latency: <5ms (zero LLM tokens)
- Pattern-proven approach (auth, rate limits, server errors)

**Tier 2 (LLM-based):**
- Future enhancement for ambiguous cases
- Won't break existing API
- Optional feature flag for adoption

### Why XML for State Guards?

```mermaid
graph TD
    A["State Guard as XML<br/>(Position 0)"] --> B["Enhanced Attention<br/>(LLM Focus)"]
    B --> C["Structured Signals<br/>(State_Guard Tags)"]
    C --> D["Prevents Summarization<br/>(Robust Directives)"]
    D --> E["Guaranteed Compliance<br/>(Agent Follows)"]
    
    style A fill:#f5e8f0,stroke:#8a5a7a,stroke-width:2px,color:#1a1a1a
    style B fill:#fef8e0,stroke:#9b8f54,stroke-width:2px,color:#1a1a1a
    style C fill:#e0ecf8,stroke:#5a7a99,stroke-width:2px,color:#1a1a1a
    style D fill:#fef5e8,stroke:#9b7d54,stroke-width:2px,color:#1a1a1a
    style E fill:#e6f5e8,stroke:#5a7f6f,stroke-width:2px,color:#1a1a1a
```

### Why 24-Hour TTL?

| Property | Value | Rationale |
|----------|-------|-----------|
| **TTL Duration** | 24 hours | Recent failures only, not permanent |
| **Age Handling** | Exponential decay | Old failures become irrelevant |
| **Service Recovery** | 24h window | Services recover, auth refreshes |
| **Memory Management** | Limited context | Prevents episodic graph bloat |
| **Configuration** | User-customizable | `HippocampusConfig.default_ttl` |
| **Pattern** | Episodic memory | Brain-like forgetting mechanism |
