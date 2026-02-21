# Phase 1 Verification Checklist

This document provides a step-by-step verification checklist to confirm all Phase 1 features are working correctly in the Streamlit UI.

## Pre-Verification Setup

### 1. Ensure Cost Tracking is Enabled

```bash
# Check config
grep -A 5 '^\[cost\]' ~/.zeroclaw/config.toml

# Should show:
# [cost]
# enabled = true
# daily_limit_usd = 10.0
# monthly_limit_usd = 100.0
```

If `enabled = false`, enable it:
```bash
sed -i.bak 's/^enabled = false/enabled = true/' ~/.zeroclaw/config.toml
```

### 2. Generate Sample Data

```bash
cd /Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app
python scripts/generate_sample_costs.py
```

Expected output:
```
Generated 50 cost records
Output: ~/.zeroclaw/state/costs.jsonl

Summary:
  Total cost: $X.XXXX
  Total tokens: XXX,XXX
  Sessions: 3
  Models used: 4
```

### 3. Run Integration Tests

```bash
python scripts/test_phase1.py
```

Expected output:
```
============================================================
TOTAL: 3/3 tests passed
============================================================

🎉 All Phase 1 tests PASSED!
```

## Start Streamlit UI

```bash
cd /Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app
streamlit run app.py
```

Navigate to: http://localhost:8501

## Visual Verification Checklist

### Feature 1: Cost Tracking Display

**Component:** `components/dashboard/cost_tracking.py`

**Location:** Dashboard page, after "Quick Actions Panel"

#### Visual Elements

- [ ] Section header "💰 Cost Tracking" is visible
- [ ] If cost tracking disabled: Shows info message with instructions
- [ ] If costs.jsonl missing: Shows warning message
- [ ] If data available:

##### Cost Metrics (3 columns)
- [ ] **Column 1 - Session Cost**
  - [ ] Label: "Session Cost"
  - [ ] Value: Displays as `$X.XXXX`
  - [ ] Help text: "Cost for the current session"

- [ ] **Column 2 - Daily Cost**
  - [ ] Label: "Daily Cost"
  - [ ] Value: Displays as `$X.XXXX`
  - [ ] Delta: Shows `XX% of $XX.XX`
  - [ ] Color: Green (normal) or off (warning/exceeded)

- [ ] **Column 3 - Monthly Cost**
  - [ ] Label: "Monthly Cost"
  - [ ] Value: Displays as `$X.XXXX`
  - [ ] Delta: Shows `XX% of $XXX.XX`
  - [ ] Color: Green (normal) or off (warning/exceeded)

##### Budget Alerts
- [ ] Warning alert (🟡) displays if budget 80-100%
- [ ] Error alert (🔴) displays if budget ≥100%
- [ ] Alerts show clear messages

##### Cost Breakdown
- [ ] Divider appears above breakdown
- [ ] Header: "Cost Breakdown by Model"
- [ ] Pie chart displays with:
  - [ ] Model names (shortened)
  - [ ] Percentages
  - [ ] Hover shows cost in USD
  - [ ] Matrix green color palette
  - [ ] Donut chart style (hole in center)

- [ ] "View Detailed Breakdown" expander works
  - [ ] Shows model, cost, tokens, requests
  - [ ] Data aligned in 3 columns

### Feature 2: Token Usage Monitoring

**Component:** `components/dashboard/token_usage.py`

**Location:** Dashboard page, after "Cost Tracking"

#### Visual Elements

- [ ] Section header "🔢 Token Usage" is visible
- [ ] If cost tracking disabled: Shows info message
- [ ] If costs.jsonl missing: Shows warning message
- [ ] If data available:

##### Token Metrics (3 columns)
- [ ] **Column 1 - Total Tokens (Session)**
  - [ ] Label: "Total Tokens (Session)"
  - [ ] Value: Displays with comma separator (e.g., `106,062`)
  - [ ] Help text: "Total tokens used in the current session"

- [ ] **Column 2 - Avg Tokens/Request**
  - [ ] Label: "Avg Tokens/Request"
  - [ ] Value: Displays with comma separator
  - [ ] Help text: "Average tokens per API request"

- [ ] **Column 3 - Requests**
  - [ ] Label: "Requests"
  - [ ] Value: Displays count
  - [ ] Help text: "Number of API requests in this session"

##### Token Timeline
- [ ] Divider appears
- [ ] Header: "Token Usage Timeline (Last 24 Hours)"
- [ ] Stacked area chart displays:
  - [ ] X-axis: Timestamps
  - [ ] Y-axis: Token counts
  - [ ] Two layers: Input (bottom), Output (top)
  - [ ] Matrix green colors with transparency
  - [ ] Hover shows token counts
  - [ ] No mode bar

##### Input/Output Breakdown
- [ ] Divider appears
- [ ] Header: "Input vs Output Tokens by Model"
- [ ] Left column shows:
  - [ ] "Input Tokens" label
  - [ ] Count with comma separator
  - [ ] "Output Tokens" label
  - [ ] Count with comma separator

- [ ] Right column shows:
  - [ ] Horizontal stacked bar chart
  - [ ] Two segments: Input (sea green), Output (mint green)
  - [ ] Counts displayed inside bars
  - [ ] Legend at top

- [ ] Info box displays:
  - [ ] "Token Efficiency" header
  - [ ] Input/Output ratio
  - [ ] Average tokens per request

### Feature 3: Budget Status Display

**Library:** `lib/budget_manager.py`

**Verification:** Integrated into Cost Tracking component

#### Functionality Checks

- [ ] Budget calculation from config.toml works
- [ ] Daily limit correctly read
- [ ] Monthly limit correctly read
- [ ] Warning threshold (80%) respected
- [ ] Percentage calculations accurate
- [ ] Status levels work:
  - [ ] ALLOWED: < 80%
  - [ ] WARNING: 80-100%
  - [ ] EXCEEDED: ≥ 100%
  - [ ] DISABLED: tracking off

### Feature 4: Budget Enforcement UI

**Component:** Integrated into `cost_tracking.py`

**Location:** Dashboard page, Cost Tracking section

#### Alert Behavior

Test by modifying config.toml limits:

**Test Case 1: Normal (< 80%)**
```toml
daily_limit_usd = 10.0
```
- [ ] No alerts display
- [ ] Delta color is green/normal
- [ ] Metrics show percentage < 80%

**Test Case 2: Warning (80-100%)**
```toml
daily_limit_usd = 0.01  # Set low to trigger warning
```
- [ ] ⚠️ Warning alert displays
- [ ] Alert shows: "Daily budget warning: XX% used ($X.XX / $X.XX)"
- [ ] Delta color is off (no color)

**Test Case 3: Exceeded (≥ 100%)**
```toml
daily_limit_usd = 0.001  # Set very low to trigger exceeded
```
- [ ] 🚨 Error alert displays
- [ ] Alert shows: "Daily budget exceeded: $X.XX / $X.XX"
- [ ] Delta color is off (no color)

**Test Case 4: Disabled**
```toml
[cost]
enabled = false
```
- [ ] Info message displays
- [ ] Message: "Cost tracking is currently disabled"
- [ ] Instructions to enable in config.toml

### Feature 5: Agent Status Monitor

**Component:** `components/dashboard/agent_config_status.py`

**Location:** Dashboard page, after "Token Usage"

#### Visual Elements

- [ ] Section header "🤖 Agent Configuration" is visible
- [ ] If config error: Shows error message

##### Agent Metrics (3 columns)
- [ ] **Column 1 - Total Agents**
  - [ ] Label: "Total Agents"
  - [ ] Value: Displays count (including default)
  - [ ] Help text: "Number of configured agents (including default)"

- [ ] **Column 2 - Autonomy Level**
  - [ ] Label: "Autonomy Level"
  - [ ] Value: Shows icon + level (e.g., "👀 Supervised")
  - [ ] Icons: 🔒 Restricted, 👀 Supervised, 🚀 Autonomous
  - [ ] Help text: "Agent autonomy level from config"

- [ ] **Column 3 - Providers**
  - [ ] Label: "Providers"
  - [ ] Value: Count of unique providers
  - [ ] Help text: "Number of unique providers configured"

##### Default Agent Card
- [ ] Divider appears
- [ ] Header: "Default Agent"
- [ ] Agent card displays:
  - [ ] Agent name with model (e.g., "default (claude-sonnet-4.6) ⭐")
  - [ ] Provider and temperature (e.g., "Provider: openrouter • Temperature: 0.7")
  - [ ] Status badge on right (e.g., "CONFIGURED")
  - [ ] Status color: mint green

##### Configured Agents
- [ ] If no configured agents:
  - [ ] Info message displays
  - [ ] Message: "No additional agents configured"
  - [ ] Instructions to add agents in config.toml

- [ ] If configured agents exist:
  - [ ] Divider appears
  - [ ] Header: "Configured Agents"
  - [ ] Each agent shows card similar to default
  - [ ] No star icon (⭐) for non-default agents

##### Provider Distribution
- [ ] If multiple providers:
  - [ ] Divider appears
  - [ ] Header: "Provider Distribution"
  - [ ] Progress bars display for each provider
  - [ ] Format: "provider: X agents (XX%)"
  - [ ] Bars fill proportionally

## Integration Verification

### Dashboard Layout
- [ ] All Phase 1 components appear in correct order:
  1. Real-Time Metrics
  2. Quick Actions Panel
  3. **Cost Tracking** (Phase 1)
  4. **Token Usage** (Phase 1)
  5. **Agent Configuration** (Phase 1)
  6. Activity Stream / Agent Status Monitor

- [ ] Dividers separate sections clearly
- [ ] No layout breaks or overlapping elements
- [ ] Responsive design works (resize browser)

### Theme Consistency
- [ ] All components use Matrix green colors
- [ ] Charts use green palette
- [ ] Warning/error colors preserved (yellow/red)
- [ ] Text is readable on dark background
- [ ] Consistent spacing and padding

### Error Handling
- [ ] No crashes when costs.jsonl missing
- [ ] No crashes when cost tracking disabled
- [ ] No crashes on invalid JSON in costs.jsonl
- [ ] No crashes when config.toml has errors
- [ ] Helpful error messages displayed

## Performance Verification

- [ ] Page loads in < 3 seconds
- [ ] Charts render without lag
- [ ] Scrolling is smooth
- [ ] No console errors in browser (F12)
- [ ] Components render on first load

## Browser Compatibility

Test in:
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (if on macOS)

## Final Acceptance

- [ ] All 5 Phase 1 features working
- [ ] All visual elements present
- [ ] All metrics display correctly
- [ ] Budget alerts functional
- [ ] Agent configuration displays
- [ ] No errors or crashes
- [ ] Theme consistent
- [ ] Performance acceptable

## Rollback Procedure (if needed)

If issues found, revert with:

```bash
cd /Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app

# Revert dashboard.py
git checkout HEAD -- pages/dashboard.py

# Remove Phase 1 files
rm lib/costs_parser.py
rm lib/budget_manager.py
rm lib/agent_monitor.py
rm components/dashboard/cost_tracking.py
rm components/dashboard/token_usage.py
rm components/dashboard/agent_config_status.py

# Restart Streamlit
# Original dashboard will load without Phase 1 components
```

## Sign-off

- [ ] All checklist items verified
- [ ] Phase 1 implementation complete and working
- [ ] Ready for user testing

**Verified by:** _________________
**Date:** _________________
**Signature:** _________________

---

**Document Version:** 1.0
**Last Updated:** 2026-02-21
**Status:** Ready for verification
