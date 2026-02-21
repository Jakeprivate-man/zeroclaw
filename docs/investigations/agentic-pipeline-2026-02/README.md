# Agentic Pipeline Investigation - February 2026

## Overview

This investigation was conducted using 12 specialized agents to map the complete end-to-end agentic pipeline architecture in ZeroClaw, with a focus on understanding why nested agent research pipelines are not visible in the Streamlit UI.

**Investigation Date**: February 21, 2026
**Investigation Method**: 12 concurrent specialized agents
**Total Documentation**: ~200KB across 29 files

## Problem Statement

User reported: "I can't see the researching bot nested as a project with the agents showing the token research pipeline"

## Root Causes Identified

### 1. NoopObserver Pattern (Critical)
- Child agents execute with `NoopObserver` that discards all events
- Located in `src/tools/delegate.rs:393, 479-493`
- **Impact**: Complete invisibility of nested agent execution

### 2. Disconnected Token Tracking (Critical)
- Token tracking infrastructure exists but never wired to runtime
- Providers don't extract tokens, agent loop doesn't record them
- **Impact**: No actual token/cost tracking in production

### 3. Missing Tool History Persistence (Critical)
- Python UI expects `tool_history.jsonl` but Rust never creates it
- Tool execution is 70% complete but no persistent logging
- **Impact**: Tool execution timeline invisible

## Investigation Team Structure

### Team 1: Agent Orchestration Pipeline
- **Agent 1**: Lifecycle Investigation
- **Agent 2**: Delegation Deep Dive
- **Agent 3**: Multi-Agent Project Tracking

### Team 2: Token & Cost Pipeline
- **Agent 4**: Token Tracking Architecture
- **Agent 5**: Cost Aggregation & Reporting
- **Agent 6**: Budget Enforcement Integration

### Team 3: Agent Output Capture
- **Agent 7**: Agent Result Streaming
- **Agent 8**: Tool Execution Tracking
- **Agent 9**: Memory & State Persistence

### Team 4: UI Integration Points
- **Agent 10**: Real-time Data Pipelines
- **Agent 11**: Visualization Gaps Analysis
- **Agent 12**: Integration Architecture Synthesis

## Key Deliverables

### Quick Start
- **[SYNTHESIS_SUMMARY.txt](./SYNTHESIS_SUMMARY.txt)** - Executive summary (5-10 min read)
- **[INVESTIGATION_INDEX.md](./INVESTIGATION_INDEX.md)** - Navigation guide

### Master Reports
- **[AGENTIC_PIPELINE_MASTER_REPORT.md](./AGENTIC_PIPELINE_MASTER_REPORT.md)** - Complete architecture synthesis (585 lines)

### Individual Agent Reports

| Agent | Focus Area | Report | Supporting Docs |
|-------|-----------|--------|-----------------|
| 01 | Lifecycle | [AGENT_01_LIFECYCLE_REPORT.md](./AGENT_01_LIFECYCLE_REPORT.md) | - |
| 02 | Delegation | [AGENT_02_DELEGATE_REPORT.md](./AGENT_02_DELEGATE_REPORT.md) | [Findings](./AGENT_02_FINDINGS_SUMMARY.md), [Index](./AGENT_02_INVESTIGATION_INDEX.md) |
| 03 | Projects | [AGENT_03_PROJECTS_REPORT.md](./AGENT_03_PROJECTS_REPORT.md) | [Quick Ref](./AGENT_03_QUICK_REFERENCE.md) |
| 04 | Tokens | [AGENT_04_TOKENS_REPORT.md](./AGENT_04_TOKENS_REPORT.md) | - |
| 05 | Costs | [AGENT_05_COSTS_REPORT.md](./AGENT_05_COSTS_REPORT.md) | [Summary](./AGENT_05_INVESTIGATION_SUMMARY.txt), [Quick Ref](./AGENT_05_QUICK_REFERENCE.md), [README](./AGENT_05_README.md) |
| 06 | Budget | [AGENT_06_BUDGET_REPORT.md](./AGENT_06_BUDGET_REPORT.md) | [Summary](./AGENT_06_SUMMARY.txt) |
| 07 | Streaming | [AGENT_07_STREAMING_REPORT.md](./AGENT_07_STREAMING_REPORT.md) | [Index](./AGENT_07_INDEX.md), [Summary](./AGENT_07_SUMMARY.txt) |
| 08 | Tools | [AGENT_08_TOOLS_REPORT.md](./AGENT_08_TOOLS_REPORT.md) | [Summary](./AGENT_08_EXECUTIVE_SUMMARY.txt), [Files](./AGENT_08_FILES_EXAMINED.txt), [Index](./AGENT_08_INDEX.txt) |
| 09 | Memory | [AGENT_09_MEMORY_REPORT.md](./AGENT_09_MEMORY_REPORT.md) | [Summary](./AGENT_09_INVESTIGATION_SUMMARY.txt), [README](./AGENT_09_README.md) |
| 10 | Real-time | [AGENT_10_REALTIME_REPORT.md](./AGENT_10_REALTIME_REPORT.md) | - |
| 11 | Gaps | [AGENT_11_GAPS_REPORT.md](./AGENT_11_GAPS_REPORT.md) | [Summary](./AGENT_11_SUMMARY.txt) |
| 12 | Synthesis | [AGENTIC_PIPELINE_MASTER_REPORT.md](./AGENTIC_PIPELINE_MASTER_REPORT.md) | - |

## Implementation Roadmap

### Phase 1 (1-2 weeks, 27 hours)
**Objective**: Make delegations visible in logs and basic UI

- Replace NoopObserver with forwarding observer
- Add DelegationStart/DelegationEnd events
- Create basic delegation tree UI component

### Phase 2 (2-3 weeks, 50 hours)
**Objective**: Capture complete execution context

- Wire token tracking to runtime
- Add agent_id to CostRecord schema
- Implement ToolHistoryObserver
- Build per-agent cost breakdown UI

### Phase 3 (3-4 weeks, 40 hours)
**Objective**: Interactive research pipeline visualization

- Build interactive delegation tree
- Add tool execution timeline (Gantt chart)
- Create agent research workflow visualizer

**Total Effort**: 6-9 weeks, 117 hours

## Critical Gaps Identified

| Gap | Severity | Agent | Impact |
|-----|----------|-------|--------|
| No delegation tree tracking | CRITICAL | 2 | Cannot visualize multi-agent hierarchies |
| Disconnected token tracking | CRITICAL | 4 | No production token/cost data |
| Missing tool history persistence | CRITICAL | 8 | Tool execution invisible |
| No per-agent cost attribution | HIGH | 4,5 | Cannot identify expensive agents |
| Real-time polling stubbed | MEDIUM | 10 | UI uses mock data |

## Data Sources Analyzed

- `~/.zeroclaw/state/costs.jsonl` (50 records, $1.80 total)
- `~/.zeroclaw/memory_store.json` or `brain.db` (16 memories, 106KB)
- `~/.zeroclaw/config.toml` (complete configuration)
- 20+ Rust source files across all subsystems
- 20+ Streamlit UI components

## Verification

✅ All reports verified to contain:
- Actual code references with line numbers
- Real data examples from production files
- No pseudo code or placeholder implementations
- No fake endpoints (except legitimate examples)

## Usage

**For Quick Understanding** (5-10 min):
1. Read [SYNTHESIS_SUMMARY.txt](./SYNTHESIS_SUMMARY.txt)

**For Implementation Planning** (30 min):
2. Read [AGENTIC_PIPELINE_MASTER_REPORT.md](./AGENTIC_PIPELINE_MASTER_REPORT.md)
3. Focus on Section 9: Implementation Roadmap

**For Deep Technical Details** (2-3 hours):
4. Read individual agent reports based on subsystem of interest
5. Use [INVESTIGATION_INDEX.md](./INVESTIGATION_INDEX.md) for navigation

## Next Steps

1. Review and approve investigation findings
2. Prioritize implementation phases
3. Begin Phase 1: Delegation visibility
4. Track progress against 3-phase roadmap

## Contact

This investigation was conducted by the ZeroClaw development team in response to user feedback about nested agent visibility in the Streamlit UI.
