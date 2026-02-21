# Agent 03 Investigation: Multi-Agent Project Coordination in ZeroClaw

**Investigation Date**: 2026-02-21  
**Agent**: Agent 03 (Project/Session Coordination Specialist)  
**Mission**: Understand how multiple agents coordinate on projects and how project boundaries are defined

---

## Executive Summary

ZeroClaw **does not implement a "project" abstraction** as a first-class concept. Instead, the system uses **session-based isolation** combined with **shared workspace coordination**. Multiple agents coordinate within the same ZeroClaw runtime through:

1. **Session IDs** (UUID-based) for cost tracking and memory scoping
2. **Shared memory backends** (SQLite/PostgreSQL) for inter-agent context sharing
3. **Cron jobs and scheduled tasks** for task coordination
4. **Workspace-scoped security policies** for multi-agent isolation

This is a **session-centric, not project-centric** architecture. Projects would be implemented at the application layer (e.g., Streamlit UI) rather than in the core runtime.

---

## 1. Project vs. Session Concept

### Current Reality

**What Exists**: Sessions  
- Each `CostTracker` instance creates a **unique session_id** (UUID) on initialization
- Session IDs persist throughout the runtime lifecycle
- Session IDs are used as the primary grouping mechanism for tracking related operations

**What Does NOT Exist**: Projects  
- No `struct Project` or `pub struct Project` anywhere in the codebase
- No project ID concept at the core runtime level
- No "project creation" or "project boundary" APIs
- No dedicated project metadata storage or registry

### Code Evidence

```rust
// src/cost/tracker.rs - Session ID generation
pub struct CostTracker {
    config: CostConfig,
    storage: Arc<Mutex<CostStorage>>,
    session_id: String,  // <-- UUID-based session identifier
    session_costs: Arc<Mutex<Vec<CostRecord>>>,
}

impl CostTracker {
    pub fn new(config: CostConfig, workspace_dir: &Path) -> Result<Self> {
        Ok(Self {
            config,
            storage: Arc::new(Mutex::new(storage)),
            session_id: uuid::Uuid::new_v4().to_string(),  // <-- Generated once per tracker
            session_costs: Arc::new(Mutex::new(Vec::new())),
        })
    }
    
    pub fn session_id(&self) -> &str {
        &self.session_id
    }
}
```

---

## 2. Session Data Model and Schema

### Core Session Structure

A **session** in ZeroClaw is defined by:

| Field | Type | Lifecycle | Purpose |
|-------|------|-----------|---------|
| `session_id` | UUID String | Created on `CostTracker::new()` | Primary grouping key across all operations |
| `created_at` | DateTime (UTC) | Implicit from first cost record | Session start marker |
| `last_activity` | DateTime (UTC) | Updated per cost record timestamp | Session end/activity marker |
| Cost records | JSONL entries | Persisted to `~/.zeroclaw/state/costs.jsonl` | All operations tracked under session |
| Memory entries | SQLite/Postgres rows | Scoped by `session_id` column | Agent-local context and knowledge |

### Cost Record Schema

**File**: `~/.zeroclaw/state/costs.jsonl` (JSONL format, one record per line)

```json
{
  "id": "2fe9e123-09a0-4b5a-a187-104d253d6820",
  "session_id": "b9b607f9-eb13-4302-94ae-61ecbdbf2c97",
  "model": "anthropic/claude-sonnet-4",
  "input_tokens": 2537,
  "output_tokens": 1475,
  "total_tokens": 4012,
  "cost_usd": 0.029736,
  "timestamp": "2026-01-21T10:37:08.529651Z"
}
```

**Rust Implementation**: `src/cost/types.rs`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostRecord {
    pub id: String,                      // Unique cost event ID
    pub session_id: String,              // Links to session
    pub model: String,                   // Model used
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub total_tokens: u64,
    pub cost_usd: f64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl CostRecord {
    pub fn new(session_id: impl Into<String>, usage: TokenUsage) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            usage,
            session_id: session_id.into(),
        }
    }
}
```

### Memory Entry Schema

**File**: SQLite database at `~/.zeroclaw/state/` (configured in `memory.backend = "sqlite"`)

```rust
// src/memory/traits.rs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub id: String,
    pub key: String,
    pub content: String,
    pub category: MemoryCategory,
    pub timestamp: String,
    pub session_id: Option<String>,  // <-- Optional session scoping
    pub score: Option<f64>,           // Relevance score from embeddings
}

pub enum MemoryCategory {
    Core,                  // Long-term facts
    Daily,                 // Daily session logs
    Conversation,          // Conversation context
    Custom(String),        // User-defined
}
```

**Trait Definition** (`src/memory/traits.rs`):
```rust
#[async_trait]
pub trait Memory: Send + Sync {
    // Store memory, optionally scoped to session
    async fn store(
        &self,
        key: &str,
        content: &str,
        category: MemoryCategory,
        session_id: Option<&str>,  // <-- Session filtering
    ) -> anyhow::Result<()>;
    
    // Recall memories, optionally scoped to session
    async fn recall(
        &self,
        query: &str,
        limit: usize,
        session_id: Option<&str>,  // <-- Session isolation
    ) -> anyhow::Result<Vec<MemoryEntry>>;
    
    // List memories with optional session and category filtering
    async fn list(
        &self,
        category: Option<&MemoryCategory>,
        session_id: Option<&str>,
    ) -> anyhow::Result<Vec<MemoryEntry>>;
}
```

---

## 3. Real-World Session Data Analysis

### Session Summary from costs.jsonl

The following three sessions are tracked in the system:

```
Session A: ae6b5bf6-e3ea-4b74-8d65-ade545090d05
  - 16 cost records
  - Duration: 2026-02-06 to 2026-02-19 (13 days)
  - Total Cost: $0.4033
  - Models: claude-sonnet-4, claude-3.5-sonnet, gpt-4o, gpt-4o-mini

Session B: b9b607f9-eb13-4302-94ae-61ecbdbf2c97
  - 9 cost records
  - Duration: 2026-01-21 to 2026-02-13 (23 days)
  - Total Cost: $0.2536
  - Models: claude-sonnet-4, claude-3.5-sonnet, gpt-4o

Session C: ec1a8033-14d8-4371-9613-d44f02abe4ab
  - 25 cost records (most active)
  - Duration: 2026-01-22 to 2026-02-21 (30 days)
  - Total Cost: $0.6816
  - Models: claude-sonnet-4, claude-3.5-sonnet, gpt-4o, gpt-4o-mini
```

### Key Observations

1. **Sessions are long-lived**: Each session spans weeks, not minutes
2. **Sessions group multi-model work**: A single session uses multiple providers/models
3. **Sessions are NOT one-to-one with agents**: The runtime has one active `CostTracker`, but could theoretically spawn multiple
4. **Session isolation is voluntary**: Memory queries optionally filter by session ID—enforcement is at the caller level

---

## 4. Multi-Agent Coordination Architecture

### How Multiple Agents Share Work

ZeroClaw enables multi-agent coordination through:

#### 4.1 Shared Memory Backend

**Mechanism**: All agents in the same runtime instance share the same memory store.

```rust
// src/agent/agent.rs - Agent initialization
pub async fn from_config(config: &Config) -> Result<Self> {
    // All agents created from same Config share the same memory instance
    let memory: Arc<dyn Memory> = Arc::from(
        memory::create_memory_with_storage_and_routes(
            &config.memory,
            &config.embedding_routes,
            Some(&config.storage.provider.config),
            &config.workspace_dir,
            config.api_key.as_deref(),
        )?
    );
    
    // Each agent gets Arc to shared memory
    Agent::builder()
        .memory(memory)  // <-- Shared arc
        // ... other config
        .build()
}
```

**Result**: Multiple agents can store and recall memories from the same central store, enabling context sharing.

#### 4.2 Optional Session Filtering

Agents can optionally isolate memories by session:

```rust
// From agent loop
async fn turn(&mut self, user_message: &str) -> Result<String> {
    if self.auto_save {
        let _ = self
            .memory
            .store("user_msg", user_message, MemoryCategory::Conversation, None)
            .await;  // <-- No session_id provided: shared globally
    }
    
    // Load context for this turn
    let context = self
        .memory_loader
        .load_context(self.memory.as_ref(), user_message)
        .await
        .unwrap_or_default();  // <-- Retrieves without session filtering
}
```

#### 4.3 Cron Jobs and Task Coordination

Cron jobs enable multi-agent task orchestration:

**Job Types** (`src/cron/types.rs`):
```rust
pub enum JobType {
    Shell,   // Execute shell commands
    Agent,   // Run agent prompts
}

pub enum SessionTarget {
    Isolated,  // Run in new isolated session
    Main,      // Run in main/shared session
}

pub struct CronJob {
    pub id: String,
    pub expression: String,              // Cron schedule
    pub schedule: Schedule,               // Actual schedule
    pub command: String,                  // Shell cmd or agent prompt
    pub job_type: JobType,               // Type of job
    pub session_target: SessionTarget,   // Where to run
    pub enabled: bool,
    pub delivery: DeliveryConfig,        // Channel delivery config
    pub last_run: Option<DateTime<Utc>>,
    pub last_status: Option<String>,
    pub last_output: Option<String>,
}
```

**Coordination Pattern**:
- Cron scheduler manages job timing
- Each job can target `Main` session (shared context) or `Isolated` (separate)
- Job output is recorded and can be delivered to channels
- Jobs can be auto-deleted after completion

---

## 5. Progress Tracking and Aggregation

### Cost Summary Aggregation

The `CostTracker` provides session-scoped summaries:

```rust
pub async fn get_summary(&self) -> Result<CostSummary> {
    let (daily_cost, monthly_cost) = {
        let mut storage = self.lock_storage();
        storage.get_aggregated_costs()?
    };
    
    let session_costs = self.lock_session_costs();
    let session_cost: f64 = session_costs
        .iter()
        .map(|record| record.usage.cost_usd)
        .sum();
    
    Ok(CostSummary {
        session_cost_usd: session_cost,      // <-- Session total
        daily_cost_usd: daily_cost,          // <-- Global daily
        monthly_cost_usd: monthly_cost,      // <-- Global monthly
        total_tokens: total_tokens,
        request_count: session_costs.len(),  // <-- Session request count
        by_model: build_session_model_stats(&session_costs),  // <-- Per-model breakdown
    })
}
```

### Status Tracking via Cron Runs

Cron job execution is tracked in a separate `CronRun` table:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CronRun {
    pub id: i64,
    pub job_id: String,
    pub started_at: DateTime<Utc>,
    pub finished_at: DateTime<Utc>,
    pub status: String,            // "success", "failure", "timeout"
    pub output: Option<String>,    // Job output/result
    pub duration_ms: Option<i64>,  // Execution time
}
```

**Progress Indicators**:
- Last run timestamp
- Last execution status
- Last output
- Duration metrics

---

## 6. Project Metadata (Proposed)

Since "projects" don't exist as a core concept, here's what would be needed to implement project tracking:

### Minimal Project Abstraction

A project would need to track:

```rust
pub struct Project {
    pub id: String,                    // UUID
    pub name: String,                  // User-facing name
    pub description: Option<String>,   // Project purpose
    pub created_at: DateTime<Utc>,     // Start time
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub status: ProjectStatus,         // Active, Completed, Archived
    pub workspace_dir: PathBuf,        // Isolated workspace (optional)
    pub session_ids: Vec<String>,      // Associated sessions
    pub total_cost_usd: f64,          // Aggregated
    pub agent_count: usize,           // Number of agents
    pub metadata: Map<String, Value>,  // Custom fields
}

pub enum ProjectStatus {
    Planning,
    Active,
    OnHold,
    Completed,
    Archived,
}
```

### Storage Location

Projects would be stored in:
- **File**: `~/.zeroclaw/projects.jsonl` (similar to costs.jsonl)
- **Database**: Separate `projects` table in SQLite/Postgres
- **UI State**: Streamlit session state (for web UI integration)

---

## 7. Multi-Agent Coordination Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZeroClaw Runtime Instance                     │
│                   (Single Process, Multi-Agent)                  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  │              │              │
            ┌─────▼─────┐  ┌─────▼─────┐  ┌────▼──────┐
            │  Agent 1  │  │  Agent 2  │  │  Agent N  │
            └─────┬─────┘  └─────┬─────┘  └────┬──────┘
                  │              │              │
                  └──────────────┼──────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
           ┌────────▼─────────┐   ┌──────────▼─────────┐
           │  Shared Memory   │   │   CostTracker      │
           │  (SQLite/PG)     │   │   (Session-based)  │
           │                  │   │                    │
           │ MemoryEntry      │   │ CostRecord (JSONL) │
           │ - session_id     │   │ - session_id       │
           │ - category       │   │ - timestamp        │
           │ - content        │   │ - cost_usd         │
           │                  │   │                    │
           └────────┬─────────┘   └──────────┬─────────┘
                    │                        │
         Optional session                Database/
         filtering for                    File Persistence
         isolation
                    │
           ┌────────┴────────┐
           │                 │
       ┌───▼──┐          ┌───▼──────┐
       │Cron  │          │Gateway   │
       │Jobs  │          │Server    │
       │      │          │(Webhooks)│
       └──────┘          └──────────┘
```

---

## 8. Gateway and Webhook Coordination

The gateway (`src/gateway/mod.rs`, 2,139 lines) provides HTTP endpoints for multi-agent triggering:

**Gateway Features**:
- Webhook endpoints for triggering agents
- Pairing/authentication for secure access
- Rate limiting per token
- Idempotency guarantees

**Session Handling in Gateway**:
```rust
// Gateway doesn't explicitly manage sessions—
// Sessions are created by agents on demand.
// The gateway just triggers agent execution.
```

**Coordination Pattern**:
1. Webhook received by gateway
2. Gateway passes message to agent
3. Agent creates/uses existing `CostTracker` with session ID
4. Agent stores memories (optionally scoped to session)
5. Agent returns response to gateway
6. Gateway sends response back to caller

---

## 9. Example Multi-Agent Workflow (Hypothetical)

```
Timeline:
┌──────────────────────────────────────────────────────────────┐
│ 2026-02-21 Session: ec1a8033-14d8-4371-9613-d44f02abe4ab    │
└──────────────────────────────────────────────────────────────┘

09:00 - Agent 1 processes document
        Cost: $0.05 (claude-sonnet-4, 4,200 tokens)
        Memory: Stores extracted facts in Conversation category

12:00 - Agent 2 queries memory ("What facts were extracted?")
        Finds shared memories from Agent 1
        Cost: $0.03 (gpt-4o, 2,500 tokens)
        Memory: Adds analysis notes

15:00 - Cron job Agent 3 summarizes session progress
        Queries ALL memories (or session-filtered)
        Cost: $0.04 (claude-sonnet-4, 3,100 tokens)
        Memory: Stores summary

End of Day:
  Session Summary:
    - Total Cost: $0.12
    - Request Count: 3
    - Total Tokens: 9,800
    - Models Used: [claude-sonnet-4, gpt-4o]
    - Duration: 6 hours
```

---

## 10. UI Project Dashboard Requirements

For a **Streamlit-based project dashboard**, the following would be needed:

### Dashboard Data Model

```python
@dataclass
class ProjectDashboard:
    sessions: List[SessionSummary]
    
    # Session aggregation
    total_cost_by_session: Dict[str, float]
    request_count_by_session: Dict[str, int]
    duration_by_session: Dict[str, timedelta]
    
    # Agent metrics
    active_agents: int
    agent_status: Dict[str, AgentStatus]
    
    # Cost trends
    daily_cost: float
    monthly_cost: float
    burn_rate: float  # USD/hour
    
    # Task tracking
    cron_jobs: List[CronJobStatus]
    last_execution_times: Dict[str, datetime]
    success_rates: Dict[str, float]
    
    # Memory stats
    total_memories: int
    memories_by_category: Dict[str, int]
```

### UI Components

1. **Session Browser**: List/filter/drill-down into sessions
2. **Cost Timeline**: Visualize cost accumulation per session
3. **Agent Status**: Show running agents and their costs
4. **Cron Job Monitor**: Last run status, next run time, error logs
5. **Memory Inspector**: Browse/search memories with session filtering
6. **Cost Forecast**: Predict monthly spend based on burn rate

### Data Sources

- `~/.zeroclaw/state/costs.jsonl` → Cost dashboard
- Memory store (SQLite/PG) → Memory inspector, agent insights
- Cron store → Task/job status
- Live metrics from agents → Agent status, real-time costs

---

## 11. Implementation Guidance

### For Implementing Projects in ZeroClaw

To add "project" support, implement at the **application layer** (Streamlit UI):

1. **Create Project Table**:
   ```sql
   CREATE TABLE projects (
       id TEXT PRIMARY KEY,
       name TEXT NOT NULL,
       description TEXT,
       created_at TIMESTAMP NOT NULL,
       completed_at TIMESTAMP,
       status TEXT NOT NULL,
       session_ids TEXT[],  -- JSON array of session UUIDs
       metadata JSONB
   );
   ```

2. **Track Project-Session Mapping**:
   - When creating a session, provide optional `project_id`
   - Store in `CostRecord.metadata` or separate junction table
   - Filter costs by project via session_ids

3. **Aggregate Per Project**:
   ```rust
   pub fn aggregate_project_costs(
       project_id: &str,
       cost_records: &[CostRecord]
   ) -> ProjectCostSummary {
       cost_records
           .iter()
           .filter(|r| r.project_id == project_id)  // Filter
           .fold(Default::default(), |mut acc, r| {
               acc.total_cost += r.cost_usd;
               acc.total_tokens += r.total_tokens;
               acc
           })
   }
   ```

4. **Update UI**:
   - Replace "Sessions" view with "Projects" view
   - Drill-down from project → sessions → cost records
   - Display project status, timeline, agent assignments

---

## 12. Key Findings Summary

| Aspect | Finding |
|--------|---------|
| **Projects as First-Class Concept** | ❌ No—not implemented |
| **Sessions** | ✅ Yes—UUID-based, lifetime-scoped |
| **Session Boundaries** | `session_id` UUID + timestamps |
| **Multi-Agent Sharing** | ✅ Via shared memory + optional session filtering |
| **Cost Aggregation** | Per-session totals + daily/monthly rollup |
| **Progress Tracking** | Via `CronRun` records + cost summaries |
| **Metadata Storage** | JSONL (costs), SQLite/Postgres (memory), database (cron) |
| **Coordination Primitive** | Memory trait + Cron jobs + Gateway webhooks |
| **Architecture Pattern** | Session-scoped, not project-scoped |

---

## 13. Recommendations

### Short-Term (For Current State)

1. **Use Sessions as Project Proxies**: Assign a user-facing name/description to each session via UI
2. **Track Session-to-Purpose Mapping**: Store metadata (e.g., "Session X = Build Feature Y")
3. **Build Session Analytics**: Display per-session timelines, costs, agents

### Medium-Term (Next Phase)

1. **Implement Projects Table**: Create project metadata store with session references
2. **Add Project UI**: Streamlit dashboard with project-centric views
3. **Extend Cost Tracking**: Link `CostRecord.session_id` → project via lookup

### Long-Term (Architecture Evolution)

1. **Consider Project-Level Isolation**: Separate workspaces per project
2. **Add Project Policies**: Per-project budget limits, model restrictions
3. **Enable Project Collaboration**: Multi-user project sharing, RBAC

---

## Conclusion

**ZeroClaw is fundamentally session-oriented, not project-oriented.** This design choice reflects the system's focus on:

- **Simplicity**: Sessions are ephemeral, automatic, and require no management
- **Flexibility**: Applications can layer project abstractions on top
- **Scalability**: Sessions can be distributed across instances easily

For multi-agent coordination **within a single runtime**, sessions provide natural isolation boundaries while shared memory enables inter-agent communication. For cross-runtime or user-facing project management, the Streamlit UI should implement a project abstraction layer above sessions.

---

**Report Generated**: 2026-02-21  
**Investigation Thoroughness**: Very Thorough  
**Evidence Sources**: 
- `src/cost/tracker.rs` and `src/cost/types.rs`
- `src/memory/traits.rs` and implementations
- `src/agent/agent.rs` and orchestration loop
- `src/cron/types.rs` and scheduler
- `~/.zeroclaw/state/costs.jsonl` (real data analysis)
- `src/config/schema.rs` (configuration model)

