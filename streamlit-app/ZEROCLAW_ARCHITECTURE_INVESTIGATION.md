# ZeroClaw Agent Runtime Architecture Investigation

**Investigation Date:** 2026-02-21  
**Investigator:** Claude Code (Primary Investigation)  
**Status:** Comprehensive Analysis Complete  
**Deliverable Type:** Architecture Map + UI Requirements

---

## Executive Summary

ZeroClaw is a **Rust-based autonomous agent runtime** with trait-driven modular architecture. The codebase reveals a sophisticated, production-grade system for:

1. **Multi-agent orchestration** via delegation tool
2. **Token tracking & cost management** via detailed tracking system
3. **Gateway API** with webhook, pairing, rate-limiting, and health endpoints
4. **Real-time observability** via Prometheus, OpenTelemetry, and log backends
5. **Rich tool ecosystem** with 30+ executable tools for shell, file, memory, browser, hardware, cron, and integrations

**Key Finding:** "Research tokens" are not a discrete concept in the codebase. Instead, the runtime uses a comprehensive **cost tracking system** that monitors token usage, cost in USD, and enforces daily/monthly budgets. This is the primary metric for resource management.

---

## 1. CORE AGENT RUNTIME ARCHITECTURE

### 1.1 Agent Core Components

**File:** `/Users/jakeprivate/zeroclaw/src/agent/`

#### Agent Structure
```
Agent {
  provider: Box<dyn Provider>,          // LLM provider (OpenAI, Anthropic, Gemini, etc.)
  tools: Vec<Box<dyn Tool>>,            // Available tool implementations
  memory: Arc<dyn Memory>,              // Persistent memory backend
  observer: Arc<dyn Observer>,          // Metrics/logging
  prompt_builder: SystemPromptBuilder,  // Prompt engineering
  tool_dispatcher: Box<dyn ToolDispatcher>, // Tool call parsing
  memory_loader: Box<dyn MemoryLoader>, // Memory retrieval
  config: AgentConfig,                  // Runtime config
  model_name: String,                   // Selected model
  temperature: f64,                     // Model temperature
  history: Vec<ConversationMessage>,    // Session conversation
  skills: Vec<Skill>,                   // Loaded skill modules
}
```

#### Agent Lifecycle
1. **Initialization** (`AgentBuilder`)
   - Provider setup (with resilient wrapper)
   - Tool registry assembly
   - Memory backend initialization
   - Security policy attachment
   - Observer/metrics setup

2. **Execution Loop** (`src/agent/loop_.rs`)
   - `process_message()` - Single message handling
   - `run_tool_call_loop()` - Main agentic loop (tool invocation)
   - Tool iteration max: `DEFAULT_MAX_TOOL_ITERATIONS = 10` (prevents runaway loops)
   - Auto-compaction when history exceeds threshold (default 50 messages)

3. **Tool Execution** (`src/agent/dispatcher.rs`)
   - XML-based tool call parsing (`XmlToolDispatcher`)
   - Native/structured tool call support
   - Result formatting and feedback to LLM
   - Credential scrubbing (auto-redacts tokens, passwords, API keys)

### 1.2 Multi-Agent Orchestration

**File:** `/Users/jakeprivate/zeroclaw/src/tools/delegate.rs`

The runtime supports **multi-agent workflows** via the `DelegateTool`:

```
DelegateTool {
  agents: Arc<HashMap<String, DelegateAgentConfig>>,
  depth: u32,                 // Delegation chain depth (prevents infinite loops)
  security: SecurityPolicy,   // Enforces tool access per agent
  parent_tools: Arc<Vec<Tool>>, // Inherited tool registry
}
```

**Delegation Features:**
- **Sub-agent specialization**: Configure per-agent with different models, providers, and tools
- **Depth limiting**: Max depth configurable (prevents infinite loops)
- **Tool inheritance**: Sub-agents inherit safe subset of parent tools (exclude nested delegates)
- **Timeout enforcement**: Sub-agent calls timeout after 120–300 seconds
- **Cost propagation**: Sub-agent token usage rolls up to parent metrics

**Use Case Example:**
```
Primary Agent (Claude Sonnet 4)
  └─→ delegate("research_agent") → (OpenAI GPT-4)
      └─→ delegate("summarizer") → (Anthropic Claude 3.5)
```

### 1.3 Agent Lifecycle States

- **Initialized**: Agent created, tools loaded, memory ready
- **Running**: Processing user message, invoking tools
- **Waiting**: Awaiting user response or external resource
- **Completed**: Message processed, results returned
- **Paused**: Security policy block or user intervention

---

## 2. RESEARCH TOKENS & TOKEN TRACKING

### 2.1 "Research Tokens" Definition

**Key Finding:** There is **no "research token" as a discrete entity**. Instead, the runtime uses:

**Token Usage Tracking** (`src/cost/types.rs`):
```rust
pub struct TokenUsage {
    pub model: String,                   // e.g., "anthropic/claude-sonnet-4"
    pub input_tokens: u64,               // Prompt tokens
    pub output_tokens: u64,              // Completion tokens
    pub total_tokens: u64,               // Sum
    pub cost_usd: f64,                   // Calculated cost
    pub timestamp: DateTime<Utc>,        // Request timestamp
}
```

**Cost Calculation:**
```
cost_usd = (input_tokens / 1_000_000) × input_price_per_million
         + (output_tokens / 1_000_000) × output_price_per_million
```

### 2.2 Cost Tracking System

**File:** `/Users/jakeprivate/zeroclaw/src/cost/tracker.rs`

The `CostTracker` manages all token/cost tracking:

#### Storage Model
- **JSONL format**: `~/.zeroclaw/state/costs.jsonl` (line-delimited JSON)
- **Per-request records**: Each API call creates one `CostRecord`
- **Session scoping**: Costs grouped by session ID
- **Persistent + In-Memory**: Durable storage + fast session aggregates

#### Cost Aggregation
```
pub struct CostSummary {
    pub session_cost_usd: f64,           // Current session total
    pub daily_cost_usd: f64,             // Today's total
    pub monthly_cost_usd: f64,           // This month's total
    pub total_tokens: u64,               // Session token count
    pub request_count: usize,            // API calls in session
    pub by_model: HashMap<String, ModelStats>, // Per-model breakdown
}
```

#### Budget Enforcement
```
pub enum BudgetCheck {
    Allowed,                              // Request OK
    Warning {
        current_usd: f64,
        limit_usd: f64,
        period: UsagePeriod,              // Day/Month/Session
    },
    Exceeded {
        current_usd: f64,
        limit_usd: f64,
        period: UsagePeriod,
    }
}
```

**Limits Configured via:** `src/config/schema.rs::CostConfig`
```
[cost]
enabled = true
daily_limit_usd = 10.0
monthly_limit_usd = 100.0
warn_at_percent = 80  # Warn at 80% threshold
```

### 2.3 Model Pricing Database

**File:** `src/config/schema.rs::ModelPricing`

The runtime includes hardcoded pricing for 100+ models:
- OpenAI (GPT-4, GPT-3.5-turbo, etc.)
- Anthropic Claude models
- Google Gemini variants
- OpenRouter models
- Local/self-hosted models (Ollama, etc.)

**Pricing Format:**
```toml
[[model_pricing]]
model = "anthropic/claude-sonnet-4-20250514"
input_price_per_million = 3.0    # $3 per 1M input tokens
output_price_per_million = 15.0  # $15 per 1M output tokens
```

### 2.4 Token Flow in Agent Loop

```
User Message
    ↓
Provider API Call (with tools)
    ↓
Receive: input_tokens, output_tokens
    ↓
CostTracker.record_usage(TokenUsage)
    ↓
↳ Persist to JSONL
↳ Update session aggregate
↳ Check budget (Allowed/Warning/Exceeded)
    ↓
Tool Execution (if needed)
    ↓
Repeat until: no tool calls | max iterations reached | budget exceeded
    ↓
Return CostSummary in response
```

---

## 3. GATEWAY API ENDPOINTS

### 3.1 HTTP Gateway

**File:** `/Users/jakeprivate/zeroclaw/src/gateway/mod.rs`

The gateway is built on **Axum** (Rust async web framework) with security-first design.

#### Available Endpoints

| Endpoint | Method | Purpose | Auth | Rate Limit |
|----------|--------|---------|------|-----------|
| `/health` | GET | Health check | Public | 60/min |
| `/metrics` | GET | Prometheus metrics | Public | 60/min |
| `/pair` | POST | Client pairing (one-time code) | Header: X-Pairing-Code | 10/min |
| `/webhook` | POST | Generic webhook handler | Bearer token or secret hash | 100/min |
| `/whatsapp` | GET | Meta webhook verification | verify_token | N/A |
| `/whatsapp` | POST | WhatsApp message webhook | X-Hub-Signature-256 | 100/min |
| `/linq` | POST | Linq (iMessage/RCS/SMS) webhook | HMAC signature | 100/min |

#### Security Features
- **Rate Limiting**: Sliding window per IP (configurable)
- **Idempotency**: Deduplication via idempotency key (TTL 3600s default)
- **Pairing**: Required by default (can be disabled)
- **Secret Hashing**: X-Webhook-Secret hashed to SHA256 (never plaintext in memory)
- **Body Limits**: Max 64KB per request
- **Request Timeouts**: 30-second timeout per request
- **IP Forwarding**: X-Forwarded-For and X-Real-IP header trust (configurable)

### 3.2 Health Endpoint Response

```json
{
  "status": "ok",
  "paired": true,
  "runtime": {
    "components": {...},
    "uptime_secs": 3600
  }
}
```

### 3.3 Metrics Endpoint

Returns **Prometheus text exposition format** (if enabled):
```
# HELP zeroclaw_requests_total Total API requests
# TYPE zeroclaw_requests_total counter
zeroclaw_requests_total{method="POST",path="/webhook",status="200"} 1234

# ... more metrics
```

### 3.4 Webhook Flow

```
POST /webhook {"message": "your prompt"}
    ↓
Rate limit check (IP)
    ↓
Idempotency check (if provided)
    ↓
Pairing verification (if required)
    ↓
Message → Agent loop
    ↓
Stream response (text + tool invocations)
    ↓
Return final response JSON
```

**Request Body Schema:**
```json
{
  "message": "user input text",
  "idempotency_key": "uuid-optional",  // For dedup
  "session_id": "uuid-optional"         // For memory scoping
}
```

---

## 4. PROVIDERS & MODEL SELECTION

### 4.1 Provider Architecture

**File:** `/Users/jakeprivate/zeroclaw/src/providers/`

Core trait:
```rust
pub trait Provider: Send + Sync {
    async fn chat(&self, request: ChatRequest<'_>) -> Result<ChatResponse>;
}
```

#### Supported Providers (13 implementations)

| Provider | File | Models | Features |
|----------|------|--------|----------|
| **Anthropic** | `anthropic.rs` | Claude 3.5, 4, 4.5 | Streaming, vision, tool use |
| **OpenAI** | `openai.rs` | GPT-4, GPT-3.5 | Native tool calling |
| **OpenRouter** | `openrouter.rs` | 100+ (router) | Cost-optimized routing |
| **Gemini** | `gemini.rs` | Gemini 1.5, 2.0 | Vision, embeddings |
| **GLM** | `glm.rs` | Zhipu AI models | Chinese-optimized |
| **Ollama** | `ollama.rs` | Local models | Self-hosted |
| **Copilot** | `copilot.rs` | GitHub Copilot models | GitHub integration |
| **Bedrock** | `bedrock.rs` | AWS models | AWS integration |
| **Compatible** | `compatible.rs` | OpenAI-compatible | Generic proxy |
| **ZAI** | (in compatible) | Custom endpoints | White-label support |
| **Reliable** | `reliable.rs` | Wrapper | Fallback/retry logic |

### 4.2 Model Selection Logic

**Config-driven:**
```toml
default_provider = "openrouter"  # or "anthropic", "openai", "ollama", etc.
default_model = "anthropic/claude-sonnet-4"

[[model_routes]]
hint = "code"                    # Route "hint:code" queries
provider = "openai"
model = "gpt-4-turbo"

[[model_routes]]
hint = "research"
provider = "anthropic"
model = "claude-opus"
```

### 4.3 Provider Capabilities

Each provider exposes:
```rust
pub enum ProviderCapabilityError {
    ToolsNotSupported,
    VisionNotSupported,
    StreamingNotSupported,
    // ...
}
```

The agent loop gracefully downgrades if capabilities unavailable.

---

## 5. TOOL EXECUTION SYSTEM

### 5.1 Tool Registry (30+ Tools)

**File:** `/Users/jakeprivate/zeroclaw/src/tools/`

#### Tool Categories

**System Execution:**
- `shell` - Execute shell commands
- `browser` - Computer use (vision + clicking)
- `screenshot` - Capture screen

**File Operations:**
- `file_read` - Read files
- `file_write` - Write/append files
- `git_operations` - Git commands

**Memory:**
- `memory_store` - Persist facts to memory
- `memory_recall` - Semantic search memory
- `memory_forget` - Delete memory entries

**Information:**
- `web_search_tool` - Web search
- `http_request` - HTTP requests
- `image_info` - Analyze images

**Scheduling:**
- `schedule` - Schedule one-time tasks
- `cron_*` - Cron job management (add/list/remove/run/update)

**Hardware:**
- `hardware_board_info` - Get board info
- `hardware_memory_map` - Memory layout
- `hardware_memory_read` - Read hardware memory

**Integrations:**
- `composio` - Managed OAuth tools
- `pushover` - Notifications
- `browser_open` - Open URLs
- `delegate` - Delegate to sub-agents
- `proxy_config` - Configure proxies

### 5.2 Tool Execution Model

```
LLM Response
    ↓
ToolDispatcher.parse_response()
    ↓
For each tool call:
    ├─ Find tool by name
    ├─ Validate parameters against schema
    ├─ Check security policy (can this agent use this tool?)
    ├─ Execute: tool.execute(params).await
    ├─ Scrub credentials from output
    └─ Record execution in observability
    ↓
ToolDispatcher.format_results()
    ↓
Feed back to LLM (as tool_result message)
```

### 5.3 Security Model

Each tool checks:
```rust
pub fn execute(...) -> Result<ToolResult> {
    self.security.enforce_tool_operation(
        ToolOperation::Act,   // Read/Act/Execute
        "tool_name"
    )?;
    // ... execution
}
```

Configured via:
```toml
[autonomy]
level = "supervised"  # restricted | supervised | autonomous
allow_shell = true
allow_file_write = false
allow_browser = true
```

---

## 6. MEMORY SYSTEMS

### 6.1 Memory Architecture

**File:** `/Users/jakeprivate/zeroclaw/src/memory/`

Core trait:
```rust
pub trait Memory: Send + Sync {
    async fn store(&self, key, content, category, session_id) -> Result<()>;
    async fn recall(&self, query, limit, session_id) -> Result<Vec<MemoryEntry>>;
    async fn get(&self, key) -> Result<Option<MemoryEntry>>;
    async fn list(&self, category, session_id) -> Result<Vec<MemoryEntry>>;
    async fn forget(&self, key) -> Result<bool>;
    async fn count(&self) -> Result<usize>;
}
```

#### Memory Categories
- **Core**: Long-term facts, preferences, decisions
- **Daily**: Session logs for today
- **Conversation**: Current conversation context
- **Custom(name)**: User-defined categories

### 6.2 Memory Backends

| Backend | Implementation | Features | Use Case |
|---------|---|----------|---|
| **SQLite** | `sqlite.rs` | FTS (full-text search), sessions, categories | Default, portable |
| **Markdown** | `markdown.rs` | File-based, readable, Git-friendly | Documentation-focused |
| **Embeddings** | `embeddings.rs` | Vector search, semantic recall | Similarity-based retrieval |
| **Postgres** | `postgres.rs` | Scalable, JSONB, pgvector | Production databases |
| **None** | `none.rs` | No-op | Testing, stateless mode |

### 6.3 Semantic Search

If embeddings enabled:
```
1. User query → Embed (OpenAI/Anthropic embeddings)
2. Store memory → Embed + Store vector
3. Recall → Vector similarity search (cosine)
4. Top-K results returned
```

**Config:**
```toml
[memory]
backend = "sqlite"
auto_save = true

[[memory.embedding_providers]]
provider = "openai"
model = "text-embedding-3-small"
```

---

## 7. OBSERVABILITY & METRICS

### 7.1 Observer Architecture

**File:** `/Users/jakeprivate/zeroclaw/src/observability/`

Core trait:
```rust
pub trait Observer: Send + Sync {
    fn name(&self) -> &str;
    fn record_event(&self, event: ObserverEvent);
    fn record_metric(&self, metric: ObserverMetric);
}
```

#### Event Types

```rust
pub enum ObserverEvent {
    AgentStart { session_id, timestamp },
    ToolCall { tool_name, input, status },
    ToolResult { tool_name, output, duration },
    ProviderCall { provider, model, tokens },
    Error { message, source },
    // ... more
}

pub enum ObserverMetric {
    TokenUsage { model, input, output, cost },
    LatencyMs { operation, duration },
    CacheHit { operation },
    CacheMiss { operation },
}
```

### 7.2 Observer Backends

| Backend | Purpose | Output |
|---------|---------|--------|
| **Prometheus** | Metrics exposition | Text format (port /metrics) |
| **OpenTelemetry** | Distributed tracing | OTLP (gRPC/HTTP) |
| **Log** | Structured logging | JSON/plaintext logs |
| **Verbose** | Debug output | Stdout |
| **MultiObserver** | Composite | Multiple backends simultaneously |
| **NoopObserver** | Testing | No-op |

### 7.3 Real-Time Metrics

**Available Metrics:**
- API request count (by status, provider, model)
- Token usage per request (input/output)
- Tool execution latency
- Error rates and types
- Cache hit/miss ratios
- Agent session duration
- Budget burn rate

**Queried at:** `/metrics` endpoint (Prometheus format)

---

## 8. CURRENT STREAMLIT UI STATUS

### 8.1 What's Implemented

**Pages:**
- ✓ Dashboard (real-time metrics, activity stream, agent status)
- ✓ Analytics (request volume, response time, error rates)
- ✓ Reports (markdown viewer, PDF export)
- ✓ Settings (configuration panel)

**Components:**
- ✓ Matrix green theme
- ✓ Sidebar navigation
- ✓ Mock data generation (for testing)
- ✓ Session state management

**API Client:**
- ✓ Health check
- ✓ Metrics fetch (Prometheus text parsing)
- ✓ Report listing/viewing
- ✓ Timeout/error handling

### 8.2 What's Missing

**Critical Gaps:**
1. ❌ No real cost tracking display
2. ❌ No token usage monitoring
3. ❌ No real cost summary (daily/monthly/session)
4. ❌ No budget enforcement UI
5. ❌ No agent orchestration visualization
6. ❌ No tool execution history
7. ❌ No model/provider selection UI
8. ❌ No memory recall interface
9. ❌ No webhook test interface
10. ❌ No pairing token management

---

## 9. INTEGRATION GAPS & REQUIRED FEATURES

### 9.1 Missing Data Sources

The Streamlit UI currently pulls from:
- ✓ `/health` - Basic health
- ✓ `/metrics` - Prometheus text format

But should also expose:
- ❌ `/api/cost-summary` - Cost tracking
- ❌ `/api/budget-status` - Budget enforcement
- ❌ `/api/agents` - Agent list/status
- ❌ `/api/tool-executions` - Tool history
- ❌ `/api/memory` - Memory operations
- ❌ `/api/models` - Available models
- ❌ `/api/pairing-status` - Pairing state

### 9.2 UI Features Needed

**Dashboard:**
- [ ] Cost gauge (today, month, session)
- [ ] Budget warning/exceeded alerts
- [ ] Active agent list with status
- [ ] Tool execution timeline
- [ ] Model selector (quick-switch)
- [ ] Cost burn rate (per minute)

**Cost Management:**
- [ ] Daily cost graph (7-day rolling)
- [ ] Monthly cost breakdown
- [ ] Cost per model
- [ ] Budget configuration UI
- [ ] Cost alerts
- [ ] Token distribution pie chart

**Agent Orchestration:**
- [ ] Multi-agent workflow visualizer
- [ ] Delegation depth monitor
- [ ] Sub-agent status panel
- [ ] Manual agent delegation trigger

**Tools & Memory:**
- [ ] Tool execution history (searchable)
- [ ] Memory recall interface
- [ ] Memory store UI
- [ ] Tool parameter validation UI
- [ ] Tool execution logs

**Gateway Management:**
- [ ] Pairing token display/refresh
- [ ] Webhook test sender
- [ ] Rate limit status
- [ ] Connected clients list

---

## 10. PRIORITY FEATURES FOR STREAMLIT UI

### Phase 1: Critical (Must-Have)

1. **Cost Dashboard**
   - Current session cost (USD)
   - Daily cost (USD)
   - Monthly cost (USD)
   - Budget status (% remaining)
   - Cost per model breakdown

2. **Token Monitoring**
   - Input/output tokens per request
   - Token usage graph (last 24h)
   - Average tokens per request
   - Total tokens (session)

3. **Agent Status**
   - Current agent
   - Available agents
   - Agent switch button
   - Sub-agent delegation status (if applicable)

### Phase 2: Important (High Priority)

4. **Budget Management**
   - Daily/monthly limit display
   - Warning threshold configuration
   - Budget exceeded protection indicator
   - Cost projection (at current burn rate)

5. **Tool Execution Monitor**
   - Recent tool calls
   - Tool execution latency
   - Success/failure rate
   - Tool parameters display

6. **Model Selection**
   - Current model
   - Available models
   - Quick-switch buttons
   - Model pricing display

### Phase 3: Nice-to-Have

7. **Memory Management**
   - Memory recall search
   - Memory store form
   - Memory category browser
   - Memory entry count

8. **Webhook Testing**
   - Webhook URL display
   - Test message sender
   - Pairing token management
   - Rate limit status

9. **Multi-Agent Workflows**
   - Delegation tree visualizer
   - Sub-agent performance stats
   - Delegation timeout warnings

10. **Advanced Analytics**
    - Cost trend analysis
    - Model popularity ranking
    - Tool usage frequency
    - Response time distribution

---

## 11. IMPLEMENTATION REQUIREMENTS

### 11.1 Gateway API Extensions Needed

To support full Streamlit UI, the ZeroClaw gateway needs these new endpoints:

```rust
// Cost tracking
GET /api/cost-summary -> CostSummary {
    session_cost_usd,
    daily_cost_usd,
    monthly_cost_usd,
    total_tokens,
    request_count,
    by_model: HashMap<String, ModelStats>
}

// Budget status
GET /api/budget-check -> BudgetCheckResponse {
    status: Allowed | Warning { percent, message } | Exceeded { message },
    daily_limit, monthly_limit,
    daily_spent, monthly_spent
}

// Agents
GET /api/agents -> Vec<AgentInfo> {
    name,
    model,
    provider,
    status: running | idle | error,
    tool_count,
    last_activity: Timestamp
}

// Tool execution history
GET /api/tool-executions?limit=100&offset=0 -> Vec<ToolExecution> {
    id,
    name,
    input_params,
    output,
    success: bool,
    duration_ms,
    timestamp
}

// Memory operations
GET /api/memory?category=core&limit=10 -> Vec<MemoryEntry>
POST /api/memory { key, content, category } -> { id, success }
DELETE /api/memory/{key} -> { success }
POST /api/memory/recall { query, limit } -> Vec<MemoryEntry>

// Model/provider info
GET /api/models -> Vec<ModelInfo> {
    id,
    provider,
    display_name,
    pricing: { input_per_mtok, output_per_mtok }
}

// Pairing & gateway config
GET /api/gateway/pairing-status -> {
    require_pairing: bool,
    is_paired: bool,
    pairing_code: Option<String>
}

GET /api/gateway/config -> {
    rate_limits: { pair_per_min, webhook_per_min },
    max_body_size_bytes,
    request_timeout_secs
}
```

### 11.2 Real-Time Updates

Current approach is **polling**. For better UX:

**Option A: Polling (Simpler)**
- Streamlit auto-refresh (5s interval)
- Cost/status polls `/api/cost-summary` every request
- Acceptable for web UI

**Option B: WebSocket (Better)**
- Gateway exposes WebSocket at `/ws/stream`
- Server pushes cost updates in real-time
- Streamlit receives via `st.connection('websocket')`
- Requires gateway refactor (Axum supports WebSocket)

**Option C: Server-Sent Events (Middle Ground)**
- Gateway `/stream` endpoint (Server-Sent Events)
- Browser receives real-time events
- Streamlit integration requires custom HTML

### 11.3 Data Binding

Streamlit UI → Rust Gateway:
- UI reads from `/api/*` endpoints
- Configuration changes: PATCH `/api/config`
- Manual triggers: POST `/api/tools/execute` (test tool calls)

---

## 12. ARCHITECTURE MAP DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZeroClaw Agent Runtime                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Providers    │  │ Tools        │  │ Memory       │           │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤           │
│  │ Anthropic    │  │ Shell        │  │ SQLite       │           │
│  │ OpenAI       │  │ Browser      │  │ Markdown     │           │
│  │ Gemini       │  │ File I/O     │  │ Embeddings   │           │
│  │ OpenRouter   │  │ Memory       │  │ Postgres     │           │
│  │ Ollama       │  │ Web search   │  │ Vectors      │           │
│  │ Bedrock      │  │ Cron jobs    │  └──────────────┘           │
│  │ Copilot      │  │ HTTP         │                              │
│  └──────────────┘  │ Composio     │                              │
│       ▲            │ Delegate     │                              │
│       │            └──────────────┘                              │
│       │                   ▲                                      │
│       └───┬───────────────┘                                      │
│           │                                                      │
│      ┌────▼──────────────────────┐                              │
│      │   Agent Loop              │                              │
│      │  (orchestration)           │                              │
│      │                            │                              │
│      │  1. Receive message        │                              │
│      │  2. Provider chat() call   │                              │
│      │  3. Parse tool calls       │                              │
│      │  4. Execute tools          │                              │
│      │  5. Record metrics         │                              │
│      │  6. Return response        │                              │
│      └────────────────────────────┘                              │
│           ▲                                                      │
│           │                                                      │
│  ┌────────▼──────────────────────┐                              │
│  │  Cost Tracking                 │                              │
│  │  └─────────────────────┐      │                              │
│  │     session_cost_usd   │      │                              │
│  │     daily_cost_usd     │──────┼─> JSONL File (~/.zeroclaw)   │
│  │     monthly_cost_usd   │      │                              │
│  │     by_model[]         │      │                              │
│  └────────────────────────┘      │                              │
│                                   │                              │
│  ┌────────────────────────────────▼────┐                        │
│  │  Observability Backends              │                        │
│  │  ├─ Prometheus                       │                        │
│  │  ├─ OpenTelemetry                    │                        │
│  │  ├─ Log                              │                        │
│  │  └─ Multi (composite)                │                        │
│  └────────────────────────────────────┘                          │
│           ▲                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            │
┌───────────▼──────────────────────────────────────────────────────┐
│              HTTP Gateway (Axum)                                  │
├──────────────────────────────────────────────────────────────────┤
│  GET  /health          - Health check                            │
│  GET  /metrics         - Prometheus metrics                      │
│  POST /pair            - Client pairing                          │
│  POST /webhook         - Generic webhook                         │
│  GET  /whatsapp        - WhatsApp verification                   │
│  POST /whatsapp        - WhatsApp webhook                        │
│  POST /linq            - Linq message webhook                    │
│                                                                   │
│  [NEW] GET  /api/cost-summary                                    │
│  [NEW] GET  /api/budget-check                                    │
│  [NEW] GET  /api/agents                                          │
│  [NEW] GET  /api/tool-executions                                 │
│  [NEW] GET  /api/models                                          │
│  [NEW] GET  /api/memory                                          │
└──────────────────────────────────────────────────────────────────┘
            ▲
            │
┌───────────▼──────────────────────────────────────────────────────┐
│           Streamlit UI (Python)                                   │
├──────────────────────────────────────────────────────────────────┤
│  📊 Dashboard                                                     │
│     ├─ Real-time cost meter                                     │
│     ├─ Token gauge                                              │
│     ├─ Agent status                                             │
│     └─ Tool activity stream                                     │
│                                                                   │
│  💰 Cost Management                                              │
│     ├─ Cost graph (7-day)                                       │
│     ├─ Monthly breakdown                                        │
│     ├─ Budget configuration                                     │
│     └─ Cost per model                                           │
│                                                                   │
│  🔧 Tools & Agent Management                                     │
│     ├─ Tool execution history                                   │
│     ├─ Model selector                                           │
│     ├─ Memory interface                                         │
│     └─ Agent delegation UI                                      │
│                                                                   │
│  🌐 Gateway Management                                           │
│     ├─ Pairing tokens                                           │
│     ├─ Webhook testing                                          │
│     └─ Rate limit status                                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 13. CRITICAL IMPLEMENTATION NOTES

### 13.1 Cost Tracking Integration

**UI Must Know:**
1. `CostTracker` stores costs as JSONL in `~/.zeroclaw/state/costs.jsonl`
2. Each request generates a `TokenUsage` record with model-specific pricing
3. Daily/monthly costs are cached but refreshed if date changes
4. Budget limits are enforced **before** API call (prevent overage)
5. Session costs are in-memory aggregates + persistent log

**UI Action Items:**
- Poll `/api/cost-summary` every 5–10 seconds
- Display cost/token deltas since last update
- Show budget status prominently when >80%
- Warn when exceeded
- Allow manual budget reset (admin-only)

### 13.2 Agent Orchestration Complexity

**Key Points:**
1. **DelegateTool** enables multi-agent workflows
2. **Depth limiting** prevents infinite loops (max depth configurable)
3. **Tool inheritance** passes safe tools to sub-agents
4. **Cost rollup** sub-agent costs roll up to parent metrics
5. **Timeout per agent** prevents runaway sub-agents

**UI Visualization Needs:**
- Tree view of delegation chain
- Depth indicator
- Sub-agent cost contribution
- Sub-agent timeout status

### 13.3 Security Implications

The gateway enforces:
1. **Pairing** (one-time code exchange)
2. **Rate limiting** per IP (configurable)
3. **Body size limits** (64KB max)
4. **Request timeouts** (30s max)
5. **Secret hashing** (SHA256, never plaintext)
6. **Credential scrubbing** (auto-redacts in logs)

**UI Must Respect:**
- Display pairing code when available
- Show rate limit status
- Warn on large payloads
- Never expose API tokens

### 13.4 Real-Time Metric Challenges

**Current Metric Sources:**
- Prometheus text format (requires manual parsing)
- `/health` endpoint (limited info)
- JSONL cost file (requires file I/O)

**Better Approach:**
- Extend gateway with structured JSON endpoints
- Add WebSocket for real-time updates
- Cache metrics in gateway (avoid repeated file I/O)

---

## 14. SUMMARY & RECOMMENDATIONS

### What ZeroClaw Exposes

✓ **Trait-driven architecture** (swappable providers, tools, memory, observers)  
✓ **Multi-agent support** (delegation tool + depth limiting)  
✓ **Comprehensive cost tracking** (JSONL store + USD budgets)  
✓ **30+ tools** (shell, file, browser, cron, memory, integrations)  
✓ **Real-time observability** (Prometheus, OpenTelemetry)  
✓ **Security-first gateway** (pairing, rate limiting, secret hashing)  

### What Streamlit UI Needs

1. **Extend gateway** with `/api/*` endpoints for cost, agents, tools, memory
2. **Display cost metrics** prominently (session/daily/monthly)
3. **Add budget UI** (limits, warnings, exceeded alerts)
4. **Visualize agent orchestration** (delegation tree, sub-agent status)
5. **Provide tool execution history** (searchable, filterable)
6. **Add model/provider selector** (quick-switch UI)
7. **Memory management UI** (recall, store, forget)
8. **Gateway management** (pairing, webhook testing, rate limits)

### Implementation Order

**Phase 1 (Critical):**
- Cost dashboard
- Token monitor
- Budget enforcement UI

**Phase 2 (Important):**
- Tool execution history
- Agent orchestration visualizer
- Model selector

**Phase 3 (Nice-to-Have):**
- Memory management
- Webhook testing
- Advanced analytics

---

## Appendices

### A. File Map

- `/Users/jakeprivate/zeroclaw/src/agent/` - Agent orchestration
- `/Users/jakeprivate/zeroclaw/src/cost/` - Cost tracking (types + tracker)
- `/Users/jakeprivate/zeroclaw/src/gateway/mod.rs` - HTTP gateway (Axum)
- `/Users/jakeprivate/zeroclaw/src/providers/` - Model providers (13 implementations)
- `/Users/jakeprivate/zeroclaw/src/tools/` - 30+ executable tools
- `/Users/jakeprivate/zeroclaw/src/memory/` - Memory backends + embeddings
- `/Users/jakeprivate/zeroclaw/src/observability/` - Metrics backends
- `/Users/jakeprivate/zeroclaw/src/config/schema.rs` - Full configuration schema

### B. Key Data Structures

**Cost Tracking:**
- `TokenUsage` (input, output, model, cost_usd, timestamp)
- `CostRecord` (id, session_id, usage)
- `CostSummary` (session/daily/monthly costs, by_model breakdown)
- `BudgetCheck` (Allowed | Warning | Exceeded)

**Agent Runtime:**
- `Agent` (provider, tools, memory, observer, config)
- `ChatRequest` (messages, optional tools)
- `ChatResponse` (text, tool_calls)
- `ToolResult` (name, output, success)

**Gateway:**
- `AppState` (config, provider, memory, rate_limiter, observer)
- `GatewayRateLimiter` (pair, webhook rate limiters)
- `IdempotencyStore` (dedup cache)

### C. Configuration Example

```toml
api_key = "your-api-key"
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4"
default_temperature = 0.7

[observability]
backend = "prometheus"

[agent]
max_tool_iterations = 10

[gateway]
host = "127.0.0.1"
port = 8000
require_pairing = true
pair_rate_limit_per_minute = 10
webhook_rate_limit_per_minute = 100

[[gateway.paired_tokens]]
token = "your-token"
created = "2025-01-01"

[cost]
enabled = true
daily_limit_usd = 10.0
monthly_limit_usd = 100.0
warn_at_percent = 80

[memory]
backend = "sqlite"
auto_save = true
```

---

**Investigation Complete — Ready for UI Development**
