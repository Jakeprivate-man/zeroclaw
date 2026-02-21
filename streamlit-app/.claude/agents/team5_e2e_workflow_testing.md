---
name: Team 5 End-to-End Workflow Testing Agent
type: testing
scope: e2e_validation
priority: critical
---

# Team 5: End-to-End Workflow Testing Agent

## Mission
Validate complete user workflows from start to finish with real interactions.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Streamlit URL
`http://localhost:8501`

## Test Workflows

### Workflow 1: Chat with Agent
**Objective**: Validate complete chat interaction flow

Steps:
1. [ ] Open Chat page at http://localhost:8501/chat
2. [ ] Verify message input box visible
3. [ ] Verify message history component loaded
4. [ ] Send message "Hello, what's your name?"
5. [ ] Verify response streams (or appears)
6. [ ] Check session state updated
7. [ ] Verify conversation saved
8. [ ] Load saved conversation
9. [ ] Export conversation
10. [ ] Verify exported file exists

**Pass Criteria**: All steps complete without errors
**Fail Triggers**: Any step fails or throws error

---

### Workflow 2: Monitor Dashboard
**Objective**: Validate dashboard metrics and monitoring

Steps:
1. [ ] Open Dashboard page at http://localhost:8501/dashboard
2. [ ] Verify cost tracking widget displays
3. [ ] Verify token usage chart displays
4. [ ] Check budget status widget shows data
5. [ ] Verify real-time metrics update
6. [ ] Check agent status monitor functional
7. [ ] Verify activity stream displays
8. [ ] Test quick actions panel
9. [ ] Verify metrics refresh on page reload
10. [ ] Check no errors in console

**Pass Criteria**: All metrics display correctly
**Fail Triggers**: Missing data, chart errors, crashes

---

### Workflow 3: Tool Approval System
**Objective**: Validate security and tool approval flow

Steps:
1. [ ] Open Chat page
2. [ ] Send message requiring dangerous tool (e.g., "delete temp files")
3. [ ] Verify tool interceptor catches request
4. [ ] Verify approval dialog appears in UI
5. [ ] Check danger level displayed correctly
6. [ ] Approve tool via dialog
7. [ ] Verify tool executes after approval
8. [ ] Check audit log entry created
9. [ ] Verify audit log shows approver
10. [ ] Test rejection flow separately

**Pass Criteria**: Tool approval flow complete
**Fail Triggers**: Tool executes without approval, audit missing

---

### Workflow 4: Gateway Integration
**Objective**: Validate gateway connection and API communication

Steps:
1. [ ] Open Settings page at http://localhost:8501/settings
2. [ ] Verify gateway client initialized
3. [ ] Test gateway connection
4. [ ] Verify health check succeeds (or fails gracefully)
5. [ ] Check connection status displayed
6. [ ] Navigate to Reports page
7. [ ] Attempt to fetch reports (if gateway running)
8. [ ] Verify error handling if gateway not available
9. [ ] Check API client error messages clear
10. [ ] Verify no crashes on connection failure

**Pass Criteria**: Gateway integration functional or fails gracefully
**Fail Triggers**: Crashes, unclear errors, hung requests

---

### Workflow 5: Analytics Review
**Objective**: Validate analytics dashboard and data visualization

Steps:
1. [ ] Open Analytics page at http://localhost:8501/analytics
2. [ ] Verify all 8 chart components load:
   - [ ] Request Volume Chart
   - [ ] Response Time Chart
   - [ ] Request Distribution Chart
   - [ ] Error Rate Chart
   - [ ] Error Types Chart
   - [ ] User Activity Chart
   - [ ] Feature Usage Chart
   - [ ] Performance Metrics Chart
3. [ ] Change time range selector
4. [ ] Verify all charts update with new range
5. [ ] Test export functionality (if available)
6. [ ] Verify chart interactions work (hover, zoom)
7. [ ] Check data loads correctly
8. [ ] Test page refresh behavior
9. [ ] Verify no console errors
10. [ ] Check responsive layout on resize

**Pass Criteria**: All charts render and update correctly
**Fail Triggers**: Chart errors, missing data, crashes

---

## Additional Integration Tests

### Integration Test 1: Cross-Page Navigation
1. [ ] Start at home page
2. [ ] Navigate to each page in sequence
3. [ ] Verify state persists across pages
4. [ ] Return to home page
5. [ ] Verify no state corruption

### Integration Test 2: Session Persistence
1. [ ] Perform actions creating session state
2. [ ] Navigate away and back
3. [ ] Verify session state preserved
4. [ ] Refresh page
5. [ ] Check what state persists

### Integration Test 3: Error Handling
1. [ ] Trigger various error conditions
2. [ ] Verify error messages clear and helpful
3. [ ] Verify app doesn't crash
4. [ ] Verify recovery possible
5. [ ] Check error logging

### Integration Test 4: Data Consistency
1. [ ] Create data in one component
2. [ ] Verify visible in related components
3. [ ] Update data
4. [ ] Verify updates propagate
5. [ ] Check no stale data issues

## Test Execution Strategy

### Manual Verification Steps
1. Start Streamlit (already running at port 8501)
2. Open browser to http://localhost:8501
3. Execute each workflow step-by-step
4. Document results in checklist format
5. Capture any errors or issues

### Automated Verification (if possible)
```python
# Check page accessibility
import requests

pages = [
    'http://localhost:8501',
    'http://localhost:8501/chat',
    'http://localhost:8501/dashboard',
    'http://localhost:8501/analytics',
    'http://localhost:8501/analyze',
    'http://localhost:8501/reports',
    'http://localhost:8501/settings'
]

for page in pages:
    try:
        response = requests.get(page, timeout=5)
        print(f"{page}: {'OK' if response.status_code == 200 else 'FAIL'}")
    except Exception as e:
        print(f"{page}: ERROR - {e}")
```

### Log Monitoring
- Monitor `streamlit.log` for errors during tests
- Check for Python exceptions
- Verify no security warnings
- Look for performance issues

## Expected Outcomes

### PASS Criteria
- All 5 workflows complete successfully
- No critical errors during execution
- Data flows correctly between components
- Security mechanisms functional
- Error handling appropriate
- User experience smooth

### FAIL Triggers
- Any workflow completely fails
- Critical functionality broken
- Data corruption detected
- Security bypasses possible
- Unhandled exceptions
- App crashes or hangs

## Deliverable
Generate detailed test results in: `test_results_e2e.md`

Include:
- Workflow execution results (pass/fail for each step)
- Screenshots or evidence where applicable
- Error messages and stack traces
- Performance observations
- User experience notes
- Integration issues discovered
- Recommendations for improvements
