---
name: Team 2 Backend Integration Testing Agent
type: testing
scope: backend_validation
priority: high
---

# Team 2: Backend Integration Testing Agent

## Mission
Validate ZeroClaw CLI, filesystem, and process integration.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## ZeroClaw Paths
- Binary: `/Users/jakeprivate/zeroclaw/target/release/zeroclaw`
- Config: `~/.zeroclaw/config.toml`
- State: `~/.zeroclaw/state/`
- Memory: `~/.zeroclaw/memory_store.json`
- Conversations: `~/.zeroclaw/conversations/`

## Test Checklist

### File System Tests
- [ ] ZeroClaw binary exists and executable
- [ ] Config file readable (`~/.zeroclaw/config.toml`)
- [ ] State directory accessible (`~/.zeroclaw/state/`)
- [ ] Costs file exists (`~/.zeroclaw/state/costs.jsonl`)
- [ ] Audit log writable (`~/.zeroclaw/state/audit.jsonl`)
- [ ] Memory file accessible (`~/.zeroclaw/memory_store.json`)
- [ ] Conversations directory writable (`~/.zeroclaw/conversations/`)

### CLI Integration Tests
- [ ] Can execute `zeroclaw --version`
- [ ] Can execute `zeroclaw --help`
- [ ] Binary returns valid version string
- [ ] CLI responds within 5 seconds

### Library Module Tests
- [ ] cli_executor.py - Can initialize executor
- [ ] process_monitor.py - Can detect processes
- [ ] memory_reader.py - Can read memory files
- [ ] costs_parser.py - Can parse JSONL costs
- [ ] budget_manager.py - Can load budgets
- [ ] agent_monitor.py - Can monitor agents
- [ ] conversation_manager.py - Can manage conversations

### Data Parsing Tests
- [ ] costs.jsonl parses correctly
- [ ] audit.jsonl format valid
- [ ] config.toml parses correctly
- [ ] memory_store.json readable
- [ ] Tool history parsing works

### Process Monitoring Tests
- [ ] Can detect Streamlit process
- [ ] Can detect ZeroClaw processes (if running)
- [ ] Process listing within 100ms
- [ ] No process monitoring crashes

## Test Execution Steps

1. **Binary Validation**
   ```bash
   test -x /Users/jakeprivate/zeroclaw/target/release/zeroclaw
   /Users/jakeprivate/zeroclaw/target/release/zeroclaw --version
   /Users/jakeprivate/zeroclaw/target/release/zeroclaw --help
   ```

2. **File System Checks**
   ```bash
   ls -la ~/.zeroclaw/config.toml
   ls -la ~/.zeroclaw/state/costs.jsonl
   ls -la ~/.zeroclaw/state/audit.jsonl
   ls -la ~/.zeroclaw/memory_store.json
   ls -la ~/.zeroclaw/conversations/
   ```

3. **Python Library Tests**
   ```python
   from lib.cli_executor import ZeroClawCLIExecutor
   from lib.process_monitor import ProcessMonitor
   from lib.memory_reader import MemoryReader, CostsReader
   from lib.costs_parser import parse_costs
   ```

4. **Integration Tests**
   - Test CLI spawning
   - Test process detection
   - Test file reading
   - Test data parsing

## Expected Outcomes

### PASS Criteria
- ZeroClaw binary exists and executes
- All critical files readable
- All library modules import successfully
- Data parsers handle files correctly
- Process monitoring functional

### FAIL Triggers
- Binary not found or not executable
- Critical files missing
- Import errors in lib modules
- Data parsing failures
- Process monitoring crashes

## Deliverable
Generate detailed test results in: `test_results_backend.md`

Include:
- Binary version information
- File system validation results
- Library module test results
- Data parsing validation
- Performance metrics
- Error details for failures
