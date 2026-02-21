# ZeroClaw Streamlit Migration - Agent Coordination Plan

## Execution Strategy: Claude Teams (Sequential, Not Parallel)

**Per CLAUDE.md Protocol:**
- ALL agents are .md files in `.claude/agents/` directory
- Execution via Claude Teams coordination (NOT parallel Task calls)
- Each agent has YAML frontmatter + embedded Streamlit documentation
- Sequential execution respecting dependencies

## Agent Team Structure (19 Remaining Agents)

### Phase 2: Dashboard Components (5 agents)
**Dependencies:** Agents 23, 24 (foundation - completed)

- `agent-01-realtime-metrics.md` ✓ Created
- `agent-02-activity-stream.md` - TODO
- `agent-03-agent-status-monitor.md` - TODO
- `agent-04-quick-actions-panel.md` - TODO
- `agent-17-dashboard-page.md` - TODO (depends on 1-4)

### Phase 3: Analytics Components (9 agents)
**Dependencies:** Agents 23, 24

- `agent-05-request-volume-chart.md` - TODO
- `agent-06-response-time-chart.md` - TODO
- `agent-07-request-distribution-chart.md` - TODO
- `agent-08-error-rate-chart.md` - TODO
- `agent-09-error-types-chart.md` - TODO
- `agent-10-user-activity-chart.md` - TODO
- `agent-11-feature-usage-chart.md` - TODO
- `agent-12-performance-metrics-chart.md` - TODO
- `agent-18-analytics-page.md` - TODO (depends on 5-12)

### Phase 4: Reports Components (4 agents)
**Dependencies:** Agents 23, 24

- `agent-13-reports-listing.md` - TODO
- `agent-14-markdown-viewer.md` - TODO
- `agent-15-table-of-contents.md` - TODO
- `agent-16-pdf-export.md` - TODO

### Phase 5: Final Page (1 agent)
**Dependencies:** Agents 23, 24

- `agent-19-analyze-page.md` - TODO

## Execution Plan

### Step 1: Create All .md Agent Files (18 remaining)
Each agent file contains:
- YAML frontmatter with metadata
- Official Streamlit documentation for required APIs
- React component context
- Implementation requirements
- Testing instructions

### Step 2: Execute Phases Sequentially Using Claude Teams

**Phase 2 Execution:**
1. Execute agents 1-4 using Claude Teams
2. Validate each component independently
3. Execute agent 17 (dashboard page integration)
4. Test complete dashboard

**Phase 3 Execution:**
1. Execute agents 5-12 using Claude Teams
2. Validate each chart component
3. Execute agent 18 (analytics page integration)
4. Test complete analytics

**Phase 4 Execution:**
1. Execute agents 13-16 using Claude Teams
2. Validate report viewing components
3. Test complete reports workflow

**Phase 5 Execution:**
1. Execute agent 19
2. Test analyze page

### Step 3: Integration Testing
- Test all pages together
- Verify routing works
- Test real-time updates
- Validate Matrix Green theme across all pages

### Step 4: Merge to Main
- Commit all changes in worktree
- Test in worktree one final time
- Merge `streamlit-migration` branch to `main`
- Remove React web-ui directory
- Update ZeroClaw config for Streamlit

## Advantages of Claude Teams Sequential Approach

1. **Better dependency management** - Agents execute in order respecting dependencies
2. **Easier debugging** - One agent at a time, clear error isolation
3. **Quality control** - Validate each component before moving to next
4. **Protocol compliance** - Follows CLAUDE.md mandate for .md agents
5. **Clearer coordination** - Team lead agent coordinates sequentially

## Next Steps

1. Create remaining 18 .md agent files
2. Execute Phase 2 (Dashboard) using Claude Teams
3. Execute Phase 3 (Analytics) using Claude Teams
4. Execute Phase 4 (Reports) using Claude Teams
5. Execute Phase 5 (Final page) using Claude Teams
6. Integration testing
7. Merge to main

---

*Protocol: CLAUDE.md Agentic Task Execution*
*Agents: .md files in `.claude/agents/`*
*Execution: Claude Teams Sequential Coordination*
