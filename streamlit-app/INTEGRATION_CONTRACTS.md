# ZeroClaw Streamlit Integration Contracts

**Created:** 2026-02-21
**Purpose:** Define shared contracts between 4 concurrent implementation teams
**Status:** Active

---

## Team Overview

### Team 1: Real Agent Chat
**Lead:** CLI Executor & Response Streamer
**Deliverables:** Execute actual ZeroClaw CLI and stream responses

### Team 2: Live Dashboard Data
**Lead:** Process Monitor & Memory Reader
**Deliverables:** Display real agent state and activity

### Team 3: Tool Approval System
**Lead:** Security Interceptor & Approval UI
**Deliverables:** Intercept and approve dangerous operations

### Team 4: Gateway Integration
**Lead:** API Client & Webhook Manager
**Deliverables:** Full gateway API integration

---

## Shared State Management

### Session State Keys (No Conflicts)

```python
# Team 1: Chat State
st.session_state.chat_history = []           # List[Dict]
st.session_state.current_message = ""        # str
st.session_state.chat_process = None         # subprocess.Popen
st.session_state.chat_streaming = False      # bool

# Team 2: Dashboard State
st.session_state.processes = []              # List[ProcessInfo]
st.session_state.memory_data = {}           # Dict[str, Any]
st.session_state.tool_history = []          # List[ToolExecution]
st.session_state.last_refresh = None        # datetime

# Team 3: Tool Approval State
st.session_state.pending_tools = []         # List[ToolCall]
st.session_state.tool_decisions = {}        # Dict[str, bool]
st.session_state.audit_log = []             # List[AuditEntry]

# Team 4: Gateway State
st.session_state.gateway_status = "unknown" # str
st.session_state.gateway_paired = False     # bool
st.session_state.webhooks = []              # List[Webhook]
```

### File System Paths (Consistent)

```python
# ZeroClaw binary location
ZEROCLAW_BIN = "/Users/jakeprivate/zeroclaw/target/release/zeroclaw"

# State directories
ZEROCLAW_HOME = "~/.zeroclaw"
STATE_DIR = "~/.zeroclaw/state"
MEMORY_FILE = "~/.zeroclaw/memory_store.json"
COSTS_FILE = "~/.zeroclaw/state/costs.jsonl"
CONVERSATIONS_DIR = "~/.zeroclaw/conversations"

# Streamlit app directories
STREAMLIT_ROOT = "/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app"
LIB_DIR = f"{STREAMLIT_ROOT}/lib"
COMPONENTS_DIR = f"{STREAMLIT_ROOT}/components"
PAGES_DIR = f"{STREAMLIT_ROOT}/pages"
```

### Process Management (Single Source of Truth)

```python
# Team 1 owns the main chat process
# Team 2 monitors all ZeroClaw processes (read-only)

class ProcessManager:
    """Shared process management singleton."""

    _instance = None
    _chat_process: Optional[subprocess.Popen] = None
    _gateway_process: Optional[subprocess.Popen] = None

    @classmethod
    def get_chat_process(cls) -> Optional[subprocess.Popen]:
        """Get the current chat process (Team 1 only)."""
        return cls._chat_process

    @classmethod
    def set_chat_process(cls, process: subprocess.Popen):
        """Set the chat process (Team 1 only)."""
        cls._chat_process = process

    @classmethod
    def list_all_processes(cls) -> List[ProcessInfo]:
        """List all ZeroClaw processes (Team 2 read-only)."""
        # Implementation in Team 2
        pass
```

---

## Error Handling Contracts

### Common Error Types

```python
class ZeroClawError(Exception):
    """Base exception for all ZeroClaw errors."""
    pass

class ProcessError(ZeroClawError):
    """Process execution errors (Team 1)."""
    pass

class MonitoringError(ZeroClawError):
    """Monitoring/observation errors (Team 2)."""
    pass

class SecurityError(ZeroClawError):
    """Security/approval errors (Team 3)."""
    pass

class GatewayError(ZeroClawError):
    """Gateway API errors (Team 4)."""
    pass
```

### Error Handler Pattern

```python
def handle_error(error: Exception, context: str) -> None:
    """Standardized error handling across all teams.

    Args:
        error: The exception that occurred
        context: Human-readable context (e.g., "sending message")
    """
    st.error(f"Error {context}: {str(error)}")

    # Log to audit if security-related
    if isinstance(error, SecurityError):
        audit_log.append({
            "timestamp": datetime.now(),
            "type": "security_error",
            "message": str(error),
            "context": context
        })

    # Log to console for debugging
    import logging
    logging.error(f"{context}: {error}", exc_info=True)
```

---

## Security Boundaries

### Tool Danger Levels

```python
class ToolDangerLevel(Enum):
    """Standardized danger assessment (Team 3 defines, all teams respect)."""
    SAFE = 0         # No approval needed (memory_recall, web_search)
    LOW = 1          # Approval recommended (http_request)
    MEDIUM = 2       # Approval required (file_read, file_write)
    HIGH = 3         # Always require approval (shell, browser)
    CRITICAL = 4     # Require admin approval (system commands)
```

### Approval Contract

```python
class ToolCall:
    """Standardized tool call structure (Team 3)."""
    tool_name: str
    parameters: Dict[str, Any]
    danger_level: ToolDangerLevel
    timestamp: datetime
    approved: Optional[bool] = None
    approver: Optional[str] = None

def requires_approval(tool_call: ToolCall) -> bool:
    """Check if tool requires approval (Team 3 implements, all teams use)."""
    return tool_call.danger_level >= ToolDangerLevel.MEDIUM

def approve_tool(tool_call: ToolCall, approver: str) -> None:
    """Approve a tool execution (Team 3 only)."""
    tool_call.approved = True
    tool_call.approver = approver
    audit_log.append({
        "timestamp": datetime.now(),
        "action": "tool_approved",
        "tool": tool_call.tool_name,
        "approver": approver
    })

def reject_tool(tool_call: ToolCall, approver: str, reason: str) -> None:
    """Reject a tool execution (Team 3 only)."""
    tool_call.approved = False
    tool_call.approver = approver
    audit_log.append({
        "timestamp": datetime.now(),
        "action": "tool_rejected",
        "tool": tool_call.tool_name,
        "approver": approver,
        "reason": reason
    })
```

### Credential Handling

```python
# NEVER log or display:
SENSITIVE_KEYS = {
    "api_key", "api_token", "password", "secret",
    "bearer_token", "authorization", "credential"
}

def scrub_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data from logs/display (all teams must use)."""
    scrubbed = data.copy()
    for key in scrubbed:
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            scrubbed[key] = "***REDACTED***"
    return scrubbed
```

---

## Performance Contracts

### Polling Intervals

```python
# Team 2: Dashboard polling
DASHBOARD_REFRESH_INTERVAL = 5  # seconds
METRICS_POLL_INTERVAL = 10      # seconds
MEMORY_WATCH_INTERVAL = 15      # seconds

# Team 3: Approval polling (if async)
APPROVAL_CHECK_INTERVAL = 1     # seconds (fast for UX)

# Team 4: Gateway health checks
GATEWAY_HEALTH_INTERVAL = 30    # seconds
WEBHOOK_STATUS_INTERVAL = 60    # seconds
```

### File Watching Strategy

```python
class FileWatcher:
    """Shared file watching utility (Team 2 implements, others can use)."""

    def __init__(self, filepath: str, callback: Callable):
        self.filepath = filepath
        self.callback = callback
        self.last_mtime = None

    def check(self) -> bool:
        """Check if file changed, call callback if yes."""
        try:
            current_mtime = os.path.getmtime(self.filepath)
            if self.last_mtime is None or current_mtime > self.last_mtime:
                self.last_mtime = current_mtime
                self.callback()
                return True
        except FileNotFoundError:
            pass
        return False
```

### Caching Policy

```python
# Team 2: Cache process list for 5 seconds
@st.cache_data(ttl=5)
def get_process_list() -> List[ProcessInfo]:
    """Cached process listing."""
    pass

# Team 4: Cache gateway status for 30 seconds
@st.cache_data(ttl=30)
def get_gateway_health() -> Dict[str, Any]:
    """Cached health check."""
    pass
```

---

## Data Structures

### Process Info (Team 2 defines, Team 1 uses)

```python
@dataclass
class ProcessInfo:
    """Standard process information structure."""
    pid: int
    name: str                    # Process name
    status: str                  # running, sleeping, zombie, etc.
    cpu_percent: float          # CPU usage
    memory_mb: float            # Memory in MB
    cmdline: List[str]          # Command line args
    created: datetime           # Process start time
    is_zeroclaw: bool          # True if this is a ZeroClaw process
```

### Memory Entry (Team 2 defines, all teams use)

```python
@dataclass
class MemoryEntry:
    """Standard memory entry structure."""
    key: str
    value: str
    timestamp: datetime         # When stored
    category: Optional[str]     # Memory category
    ttl: Optional[int]          # Time-to-live in seconds
```

### Tool Execution (Team 3 defines, Team 2 displays)

```python
@dataclass
class ToolExecution:
    """Standard tool execution record."""
    id: str                     # Unique execution ID
    tool_name: str
    input_params: Dict[str, Any]
    output: Any
    success: bool
    duration_ms: float
    timestamp: datetime
    approved: bool
    approver: Optional[str]
    danger_level: ToolDangerLevel
```

### Webhook Info (Team 4 defines, others can use)

```python
@dataclass
class WebhookInfo:
    """Standard webhook information."""
    id: str
    url: str
    events: List[str]          # Event types this webhook handles
    secret: Optional[str]      # Webhook secret (masked)
    enabled: bool
    created: datetime
    last_triggered: Optional[datetime]
    success_count: int
    failure_count: int
```

---

## Integration Points

### Team 1 → Team 2
**Team 1 provides:** Process ID when chat starts
**Team 2 receives:** Monitors that process for status/metrics
**Contract:** Team 1 calls `ProcessManager.set_chat_process(process)` after starting

### Team 1 → Team 3
**Team 1 provides:** Tool calls extracted from CLI output
**Team 3 receives:** Tool calls for approval
**Contract:** Team 1 blocks execution until Team 3 approves/rejects

### Team 2 → Team 3
**Team 2 provides:** Tool execution history
**Team 3 receives:** Displays in audit log
**Contract:** Team 3 writes to `st.session_state.tool_history`, Team 2 reads

### Team 4 → All Teams
**Team 4 provides:** Gateway API client
**All teams receive:** Can use `GatewayClient` for API calls
**Contract:** Team 4 exposes singleton `gateway_client` instance

---

## Validation Contracts

### Team 1 Validation
```python
def validate_chat_response(response: str) -> bool:
    """Validate chat response is well-formed."""
    return response is not None and len(response.strip()) > 0

def validate_process_running(process: subprocess.Popen) -> bool:
    """Check if process is still running."""
    return process.poll() is None
```

### Team 2 Validation
```python
def validate_memory_file(filepath: str) -> bool:
    """Check if memory file exists and is valid JSON."""
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath) as f:
            json.load(f)
        return True
    except:
        return False
```

### Team 3 Validation
```python
def validate_tool_call(tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
    """Validate tool call structure."""
    if not tool_call.tool_name:
        return False, "Missing tool name"
    if not isinstance(tool_call.parameters, dict):
        return False, "Parameters must be dict"
    return True, None
```

### Team 4 Validation
```python
def validate_gateway_response(response: requests.Response) -> bool:
    """Validate gateway HTTP response."""
    if response.status_code >= 500:
        raise GatewayError(f"Gateway error: {response.status_code}")
    return response.status_code < 400
```

---

## Testing Contracts

### Unit Test Requirements

Each team must provide:
1. Unit tests for all public functions
2. Mock objects for external dependencies
3. Error case coverage (happy path + failures)
4. Performance tests (if applicable)

### Integration Test Requirements

Cross-team integration tests:
1. **Team 1 + Team 3:** Chat → Tool Call → Approval → Execution
2. **Team 1 + Team 2:** Chat → Process Monitor sees it
3. **Team 2 + Team 3:** Tool execution → History display
4. **Team 4 + All:** Gateway API calls work from all teams

---

## Communication Protocol

### Inter-Team Communication

If a team needs something from another team:
1. Check this contract first
2. If contract unclear, propose clarification
3. Document new contract in this file
4. Notify other teams of contract change

### Conflict Resolution

If teams have conflicting needs:
1. Identify the conflict clearly
2. Propose 2-3 solutions
3. Choose solution that:
   - Preserves security
   - Minimizes coupling
   - Maintains performance
4. Update this contract

---

## Rollback Strategy

### Team Independence

Each team's work can be disabled independently:

```python
# Feature flags (in settings or session state)
ENABLE_REAL_CHAT = True      # Team 1
ENABLE_LIVE_DASHBOARD = True # Team 2
ENABLE_TOOL_APPROVAL = True  # Team 3
ENABLE_GATEWAY_FULL = True   # Team 4

# Graceful degradation
if not ENABLE_REAL_CHAT:
    st.warning("Chat disabled, using mock responses")
    # Fall back to mock implementation
```

### Rollback Procedure

1. Set feature flag to `False`
2. Restart Streamlit app
3. Team's features disabled, others continue working
4. No data loss (all state in session or files)

---

## Deployment Checklist

Before merging any team's work:

- [ ] Unit tests pass
- [ ] Integration tests pass (if dependencies ready)
- [ ] Error handling implemented per contract
- [ ] Security boundaries respected
- [ ] Session state keys don't conflict
- [ ] File paths match contract
- [ ] Performance within contract limits
- [ ] Documentation updated
- [ ] Feature flag added (for rollback)
- [ ] Other teams notified of completion

---

## Contract Versioning

**Current Version:** 1.0
**Last Updated:** 2026-02-21

### Change Log

- **1.0 (2026-02-21):** Initial contract creation for 4-team parallel work

---

**End of Integration Contracts**
