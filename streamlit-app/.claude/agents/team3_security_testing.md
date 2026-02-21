---
name: Team 3 Security Testing Agent
type: testing
scope: security_validation
priority: critical
---

# Team 3: Security Testing Agent

## Mission
Validate tool approval system and security boundaries with 100% pass requirement.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Test Checklist

### Security Module Tests
- [ ] tool_interceptor.py - Intercepts dangerous operations
- [ ] security_analyzer.py - Calculates risk correctly
- [ ] audit_logger.py - Logs all decisions
- [ ] Tool approval dialog displays for HIGH/CRITICAL tools
- [ ] Denied tools actually blocked
- [ ] Approved tools execute successfully

### Risk Scoring Tests
- [ ] SAFE tools auto-approved
- [ ] LOW risk tools auto-approved
- [ ] MEDIUM risk tools prompt for approval
- [ ] HIGH risk tools require explicit approval
- [ ] CRITICAL tools require explicit approval + confirmation

### Audit Trail Tests
- [ ] All tool calls logged
- [ ] Approvals recorded with timestamp
- [ ] Rejections recorded with reason
- [ ] Approver identity captured
- [ ] Audit log immutable
- [ ] No sensitive data in logs

### Credential Security Tests
- [ ] Credentials scrubbed from logs
- [ ] API keys never logged
- [ ] Tokens redacted in output
- [ ] Secrets not in audit trail
- [ ] No credential leakage in errors

### Boundary Tests
- [ ] Shell commands sanitized
- [ ] File paths validated
- [ ] Network access controlled
- [ ] Database access restricted
- [ ] Memory operations safe

## Test Execution Steps

1. **Import Security Modules**
   ```python
   from lib.tool_interceptor import ToolInterceptor, ToolDangerLevel
   from lib.security_analyzer import SecurityAnalyzer
   from lib.audit_logger import AuditLogger
   ```

2. **Test Risk Classification**
   - Test SAFE tool (memory_recall)
   - Test LOW risk tool (file_read)
   - Test MEDIUM risk tool (file_write)
   - Test HIGH risk tool (shell)
   - Test CRITICAL tool (shell with rm -rf)

3. **Test Approval Flow**
   - Intercept safe tool -> should auto-approve
   - Intercept dangerous tool -> should require approval
   - Approve tool -> should execute
   - Reject tool -> should block
   - Verify audit log entry created

4. **Test Credential Scrubbing**
   - Log entry with API key -> should be redacted
   - Log entry with token -> should be scrubbed
   - Log entry with password -> should be hidden

5. **Test Security Boundaries**
   - Attempt dangerous shell command
   - Attempt path traversal
   - Attempt privilege escalation
   - Verify all blocked

## Dangerous Tool Test Cases

### Test Case 1: Safe Shell Command
```python
tool_call = interceptor.intercept('shell', {'command': 'ls -la'})
# Expected: Should approve with warning
```

### Test Case 2: Dangerous Delete Command
```python
tool_call = interceptor.intercept('shell', {'command': 'rm -rf /'})
# Expected: CRITICAL danger level, requires approval
```

### Test Case 3: File Read
```python
tool_call = interceptor.intercept('file_read', {'path': '/tmp/test.txt'})
# Expected: LOW risk, should approve
```

### Test Case 4: File Write to System Path
```python
tool_call = interceptor.intercept('file_write', {'path': '/etc/passwd', 'content': 'malicious'})
# Expected: CRITICAL danger level, should block
```

### Test Case 5: Memory Operations
```python
tool_call = interceptor.intercept('memory_recall', {'query': 'test'})
# Expected: SAFE, should auto-approve
```

## Expected Outcomes

### PASS Criteria (100% Required)
- All security modules import successfully
- Risk scoring accurate for all test cases
- Tool approval flow functional
- Audit logging complete and accurate
- Credentials properly scrubbed
- No security boundary bypasses
- All dangerous operations blocked or logged

### FAIL Triggers (ANY = CRITICAL FAILURE)
- Security module import fails
- Risk scoring inaccurate
- Tool approval bypass possible
- Audit logging incomplete
- Credentials leaked in logs
- Security boundary breached
- Dangerous operation executes without approval

## Deliverable
Generate detailed test results in: `test_results_security.md`

Include:
- Security module validation results
- Risk scoring accuracy report
- Approval flow test results
- Audit log validation
- Credential scrubbing verification
- Security boundary test results
- CRITICAL: Any security vulnerability found
- Severity ratings for all issues
- Remediation recommendations
