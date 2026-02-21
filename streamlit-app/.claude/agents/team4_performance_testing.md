---
name: Team 4 Performance Testing Agent
type: testing
scope: performance_validation
priority: high
---

# Team 4: Performance Testing Agent

## Mission
Validate performance, scalability, and resource usage with benchmarks.

## Working Directory
`/Users/jakeprivate/zeroclaw-streamlit-ui/streamlit-app/`

## Test Checklist

### Performance Benchmarks
- [ ] Page load times < 2 seconds
- [ ] Chart rendering < 500ms
- [ ] Large conversation files (1000+ messages) handled
- [ ] Large cost files (10,000+ entries) parsed
- [ ] Memory usage reasonable (< 500MB)
- [ ] No memory leaks during extended use
- [ ] Process monitoring efficient (< 100ms)
- [ ] File watching doesn't CPU spike

### Scalability Tests
- [ ] 100 cost entries parse quickly
- [ ] 1,000 cost entries parse quickly
- [ ] 10,000 cost entries parse within limits
- [ ] Large memory files readable
- [ ] Multiple concurrent operations handled

### Resource Monitoring Tests
- [ ] Streamlit process memory usage tracked
- [ ] CPU usage stays reasonable (< 50% sustained)
- [ ] File descriptor limits not exceeded
- [ ] No zombie processes created
- [ ] Clean shutdown without leaks

### UI Responsiveness Tests
- [ ] Navigation instant (< 100ms)
- [ ] Button clicks responsive
- [ ] Form submission quick
- [ ] Chart updates smooth
- [ ] No UI freezing during operations

## Test Execution Steps

1. **Generate Test Data**
   ```python
   # Generate large costs file
   import json
   costs = []
   for i in range(10000):
       costs.append({
           "timestamp": f"2024-02-{i%28+1:02d}T12:00:00Z",
           "model": "claude-sonnet-4",
           "input_tokens": 1000,
           "output_tokens": 500,
           "cost_usd": 0.015
       })
   ```

2. **Benchmark Parsing**
   ```python
   import time
   from lib.costs_parser import parse_costs

   start = time.time()
   parsed = parse_costs("test_large_costs.jsonl")
   duration = time.time() - start

   # Should complete in < 1 second
   ```

3. **Monitor Memory Usage**
   ```python
   import psutil
   import os

   process = psutil.Process(os.getpid())
   mem_before = process.memory_info().rss / 1024 / 1024  # MB

   # Perform operations

   mem_after = process.memory_info().rss / 1024 / 1024  # MB
   mem_increase = mem_after - mem_before

   # Should not exceed 500MB total
   ```

4. **Test Process Monitoring Performance**
   ```python
   from lib.process_monitor import ProcessMonitor
   import time

   monitor = ProcessMonitor()
   start = time.time()
   processes = monitor.list_all_processes()
   duration = time.time() - start

   # Should complete in < 100ms
   ```

## Performance Targets

### Load Times
- Initial app load: < 2 seconds
- Page navigation: < 200ms
- Component render: < 500ms
- Chart generation: < 500ms
- Data refresh: < 1 second

### Parsing Performance
- 100 cost entries: < 10ms
- 1,000 cost entries: < 100ms
- 10,000 cost entries: < 1 second
- Memory file read: < 50ms
- Config file parse: < 10ms

### Resource Limits
- Peak memory usage: < 500MB
- Sustained CPU: < 50%
- File descriptors: < 100 open
- Process count: < 5 children
- Disk I/O: < 10MB/s

### Responsiveness
- Button click response: < 100ms
- Form validation: < 50ms
- State update: < 10ms
- Navigation: < 100ms
- Search/filter: < 200ms

## Test Scenarios

### Scenario 1: Large Data Load
1. Generate 10,000 cost entries
2. Load in dashboard
3. Measure parse time
4. Monitor memory usage
5. Verify UI responsive

### Scenario 2: Extended Session
1. Start Streamlit app
2. Navigate through all pages
3. Perform operations on each page
4. Monitor memory over 10 minutes
5. Check for memory leaks

### Scenario 3: Concurrent Operations
1. Load dashboard (costs + metrics)
2. Open analytics (8 charts)
3. Check reports listing
4. Monitor in settings
5. All should load concurrently

### Scenario 4: Process Monitoring
1. Monitor processes every 5 seconds
2. Track CPU overhead
3. Verify no process accumulation
4. Check cleanup on shutdown

## Expected Outcomes

### PASS Criteria
- All benchmarks meet targets
- No memory leaks detected
- Resource usage within limits
- UI remains responsive
- Scalability tests pass
- Clean shutdown verified

### FAIL Triggers
- Page loads > 5 seconds
- Memory usage > 1GB
- CPU sustained > 80%
- UI freezes detected
- Memory leaks identified
- Resource limits exceeded
- Performance degradation over time

## Deliverable
Generate detailed test results in: `test_results_performance.md`

Include:
- Benchmark results with timing data
- Memory usage graphs/stats
- CPU usage analysis
- Scalability test results
- Resource monitoring data
- Performance bottleneck identification
- Optimization recommendations
- Comparison to targets
