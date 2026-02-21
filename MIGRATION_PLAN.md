# ZeroClaw Streamlit Migration Plan

## Overview
This document coordinates the 24-agent team migrating the ZeroClaw React UI to Streamlit.

## Worktree Location
- **Worktree Path:** `/Users/jakeprivate/zeroclaw-streamlit-ui`
- **Branch:** `streamlit-migration`
- **Main Repo:** `/Users/jakeprivate/zeroclaw`

## Agent Team Structure

### Phase 1: Foundation (Agents 20-24) - PRIORITY
These agents create the base infrastructure that all other agents depend on.

- **Agent 20:** Sidebar Navigation
- **Agent 21:** Settings Page
- **Agent 22:** Root App Layout + Routing
- **Agent 23:** API Client (Python)
- **Agent 24:** Session State Management + Mock Data Generators

**Dependencies:** None - can start immediately
**Output:** Core app structure, API client, state management

### Phase 2: Dashboard (Agents 1-4, 17)
Real-time monitoring components

- **Agent 1:** RealTimeMetrics Component
- **Agent 2:** ActivityStream Component
- **Agent 3:** AgentStatusMonitor Component
- **Agent 4:** QuickActionsPanel Component
- **Agent 17:** Dashboard Page Orchestration

**Dependencies:** Agents 23, 24
**Output:** Complete dashboard with real-time updates

### Phase 3: Analytics (Agents 5-12, 18)
Time-series analytics and charts

- **Agent 5:** RequestVolumeChart
- **Agent 6:** ResponseTimeChart
- **Agent 7:** RequestDistributionChart
- **Agent 8:** ErrorRateChart
- **Agent 9:** ErrorTypesChart
- **Agent 10:** UserActivityChart
- **Agent 11:** FeatureUsageChart
- **Agent 12:** PerformanceMetricsChart
- **Agent 18:** Analytics Page Orchestration

**Dependencies:** Agents 23, 24
**Output:** Complete analytics dashboard with 8 charts

### Phase 4: Reports (Agents 13-16)
Document management and viewing

- **Agent 13:** Reports Listing Page
- **Agent 14:** MarkdownViewer Component
- **Agent 15:** TableOfContents Component
- **Agent 16:** PDF Export + Utilities

**Dependencies:** Agents 23, 24
**Output:** Report viewing with markdown rendering and PDF export

### Phase 5: Final Pages (Agent 19)
Remaining pages

- **Agent 19:** Analyze Page Form

**Dependencies:** Agents 23, 24
**Output:** Analysis configuration interface

## Execution Strategy

1. **Deploy Phase 1 (5 agents)** - Get foundation in place
2. **Test Foundation** - Verify app runs, routing works, API client functional
3. **Deploy Phases 2-5 in parallel (19 agents)** - Maximum parallelism
4. **Integration Testing** - Test all pages together
5. **Polish & Validation** - Fix bugs, improve UX
6. **Merge to Main** - Replace React UI

## Success Criteria

- ✅ All 5 pages render correctly
- ✅ Real-time updates work (2-second refresh or better)
- ✅ Reports load and display with syntax highlighting
- ✅ PDF export generates valid PDFs
- ✅ Settings persist across sessions
- ✅ No critical errors in console/logs
- ✅ Mobile-responsive (functional minimum)
- ✅ Matches or exceeds React UI functionality

## Testing Checklist

### Foundation Testing
- [ ] App launches without errors
- [ ] Sidebar navigation works
- [ ] Page routing functional
- [ ] API client can connect to gateway
- [ ] Session state persists across reruns

### Dashboard Testing
- [ ] Metrics update every 2 seconds
- [ ] Activity stream shows events
- [ ] Agent cards display health
- [ ] Quick actions provide feedback

### Analytics Testing
- [ ] Time range selector works
- [ ] All 8 charts render
- [ ] Charts update when range changes
- [ ] Tabs switch correctly

### Reports Testing
- [ ] Report list loads
- [ ] Search filters work
- [ ] Markdown renders correctly
- [ ] Syntax highlighting works
- [ ] TOC navigation functional
- [ ] PDF export generates files

### Settings Testing
- [ ] Gateway URL saves
- [ ] Connection test works
- [ ] Settings persist in localStorage/file

## File Structure

```
streamlit-app/
├── app.py                    # Main entry (Agent 22)
├── pages/
│   ├── dashboard.py          # Agent 17
│   ├── analytics.py          # Agent 18
│   ├── reports.py            # Agent 13
│   ├── analyze.py            # Agent 19
│   └── settings.py           # Agent 21
├── components/
│   ├── dashboard/
│   │   ├── real_time_metrics.py    # Agent 1
│   │   ├── activity_stream.py      # Agent 2
│   │   ├── agent_status_monitor.py # Agent 3
│   │   └── quick_actions_panel.py  # Agent 4
│   ├── analytics/
│   │   ├── request_volume_chart.py      # Agent 5
│   │   ├── response_time_chart.py       # Agent 6
│   │   ├── request_distribution_chart.py # Agent 7
│   │   ├── error_rate_chart.py          # Agent 8
│   │   ├── error_types_chart.py         # Agent 9
│   │   ├── user_activity_chart.py       # Agent 10
│   │   ├── feature_usage_chart.py       # Agent 11
│   │   └── performance_metrics_chart.py # Agent 12
│   ├── reports/
│   │   ├── markdown_viewer.py      # Agent 14
│   │   ├── table_of_contents.py    # Agent 15
│   │   └── pdf_export.py           # Agent 16
│   └── sidebar.py           # Agent 20
├── lib/
│   ├── api_client.py        # Agent 23
│   ├── session_state.py     # Agent 24
│   └── mock_data.py         # Agent 24
├── requirements.txt
├── .streamlit/
│   └── config.toml
└── README.md
```

## Agent Coordination

- Each agent creates one or more Python files
- Agents must read this plan before starting
- Agents must include official Streamlit documentation in their context
- Agents should test their components independently where possible
- Agent 22 (root app) integrates all pages
- Agent 17, 18, 13 integrate their respective component sets

## Timeline Estimate

- **Phase 1 (Foundation):** 2-4 hours
- **Phase 2 (Dashboard):** 3-5 hours
- **Phase 3 (Analytics):** 4-6 hours
- **Phase 4 (Reports):** 3-5 hours
- **Phase 5 (Final):** 1-2 hours
- **Testing & Integration:** 2-4 hours
- **Total:** ~15-26 hours of parallel agent work

## Next Steps

1. Deploy Phase 1 agents (20-24)
2. Wait for completion and test foundation
3. Deploy all remaining agents in parallel
4. Integration testing
5. Merge to main branch
