# Phase 1: Delegation Visibility Implementation Plan

## Objective
Make nested agent delegations visible by replacing NoopObserver with event forwarding.

## Current Problem
- Child agents execute with `NoopObserver` at `src/tools/delegate.rs:393`
- All child LLM calls, tool executions, and errors are discarded
- Delegation tree is completely invisible to observability systems

## Implementation Steps

### Step 1: Add Delegation Events to ObserverEvent
**File**: `src/observability/traits.rs`

Add two new event variants to `ObserverEvent` enum:

```rust
/// A sub-agent delegation has started.
DelegationStart {
    /// Name of the sub-agent being delegated to
    agent_name: String,
    /// Provider for the sub-agent
    provider: String,
    /// Model for the sub-agent
    model: String,
    /// Delegation depth (0 = root agent, 1 = first-level sub-agent, etc.)
    depth: u32,
    /// Whether this is an agentic delegation (full agent loop) or simple (single call)
    agentic: bool,
},
/// A sub-agent delegation has completed.
DelegationEnd {
    /// Name of the sub-agent that completed
    agent_name: String,
    /// Provider for the sub-agent
    provider: String,
    /// Model for the sub-agent
    model: String,
    /// Delegation depth
    depth: u32,
    /// Duration of the delegation
    duration: Duration,
    /// Whether the delegation succeeded
    success: bool,
    /// Error message if delegation failed
    error_message: Option<String>,
},
```

### Step 2: Create ForwardingObserver
**File**: `src/tools/delegate.rs`

Replace `NoopObserver` (lines 479-493) with:

```rust
/// Observer that forwards events from child agents to a parent observer,
/// enabling visibility into nested agent execution.
struct ForwardingObserver {
    parent: Arc<dyn Observer>,
    agent_name: String,
    depth: u32,
}

impl ForwardingObserver {
    fn new(parent: Arc<dyn Observer>, agent_name: String, depth: u32) -> Self {
        Self {
            parent,
            agent_name,
            depth,
        }
    }
}

impl Observer for ForwardingObserver {
    fn record_event(&self, event: &ObserverEvent) {
        // Forward all child events to parent observer
        self.parent.record_event(event);
    }

    fn record_metric(&self, metric: &ObserverMetric) {
        // Forward all child metrics to parent observer
        self.parent.record_metric(metric);
    }

    fn name(&self) -> &str {
        "forwarding"
    }

    fn as_any(&self) -> &dyn std::any::Any {
        self
    }
}
```

### Step 3: Add Parent Observer to DelegateTool
**File**: `src/tools/delegate.rs`

1. Add field to `DelegateTool` struct (after line 36):
```rust
/// Parent observer for forwarding child agent events
parent_observer: Option<Arc<dyn Observer>>,
```

2. Update constructors to accept parent observer

3. Pass `ForwardingObserver` instead of `NoopObserver` at line 393-401

### Step 4: Emit Delegation Events
**File**: `src/tools/delegate.rs`

1. Before starting delegation (around line 395):
```rust
if let Some(parent) = &self.parent_observer {
    parent.record_event(&ObserverEvent::DelegationStart {
        agent_name: agent_name.to_string(),
        provider: agent_config.provider.clone(),
        model: agent_config.model.clone(),
        depth: self.depth + 1,
        agentic: true,
    });
}
```

2. After delegation completes (around line 416-446):
```rust
if let Some(parent) = &self.parent_observer {
    parent.record_event(&ObserverEvent::DelegationEnd {
        agent_name: agent_name.to_string(),
        provider: agent_config.provider.clone(),
        model: agent_config.model.clone(),
        depth: self.depth + 1,
        duration: start_time.elapsed(),
        success: result.is_ok(),
        error_message: result.as_ref().err().map(|e| e.to_string()),
    });
}
```

### Step 5: Update Agent Initialization
**File**: `src/agent/mod.rs` (or wherever DelegateTool is registered)

Pass the agent's observer to DelegateTool constructor so it can forward events.

## Testing Strategy

1. **Unit Tests**: Add tests in `src/tools/delegate.rs` to verify:
   - ForwardingObserver forwards all events
   - DelegationStart/End events are emitted correctly
   - Depth tracking is accurate

2. **Integration Tests**: Test multi-level delegation (parent → child → grandchild)

3. **Manual Testing**: Run agent with delegation and verify events appear in logs

## Success Criteria

- ✅ Child agent LLM calls visible in parent observer
- ✅ Child agent tool calls visible in parent observer
- ✅ Delegation start/end events emitted
- ✅ Depth tracking accurate
- ✅ No performance regression
- ✅ All existing tests still pass

## Estimated Effort
- Code changes: 4 hours
- Testing: 2 hours
- Documentation: 1 hour
- **Total: 7 hours**

## Risks
- Recursive delegation could create event loops if not careful
- Performance impact of forwarding all events (minimal expected)
- Breaking changes to Observer trait consumers (low risk - adding variants)

## Next Steps After Phase 1
- Phase 2: Wire token tracking to runtime
- Phase 2: Add agent_id to CostRecord
- Phase 2: Implement ToolHistoryObserver
