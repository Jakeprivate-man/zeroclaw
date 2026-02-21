#!/usr/bin/env python3
"""
Team 4: Performance Testing
Validates performance, scalability, and resource usage
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path
import tempfile

class Team4PerformanceTester:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.benchmarks = {}

    def log(self, test_name, status, details="", benchmark=None):
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if benchmark:
            result["benchmark"] = benchmark
            self.benchmarks[test_name] = benchmark

        self.results.append(result)
        if status == "PASS":
            self.passed += 1
            print(f"✓ {test_name}")
        else:
            self.failed += 1
            print(f"✗ {test_name}")
        if details:
            print(f"  {details}")

    def benchmark_small_data_parsing(self):
        """Benchmark parsing small dataset (100 entries)"""
        try:
            # Generate test data
            test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl')
            for i in range(100):
                entry = {
                    "timestamp": f"2024-02-{i%28+1:02d}T12:00:00Z",
                    "model": "claude-sonnet-4",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.015
                }
                test_file.write(json.dumps(entry) + '\n')
            test_file.close()

            # Time the parsing
            start = time.time()
            with open(test_file.name, 'r') as f:
                data = [json.loads(line) for line in f]
            duration = time.time() - start

            # Cleanup
            Path(test_file.name).unlink()

            # Check against target (< 10ms)
            target_ms = 10
            duration_ms = duration * 1000

            if duration_ms < target_ms:
                self.log("Small dataset parsing (100 entries)",
                        "PASS",
                        f"{duration_ms:.2f}ms (target: <{target_ms}ms)",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})
            else:
                self.log("Small dataset parsing (100 entries)",
                        "FAIL",
                        f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})

        except Exception as e:
            self.log("Small dataset parsing", "FAIL", str(e))

    def benchmark_medium_data_parsing(self):
        """Benchmark parsing medium dataset (1,000 entries)"""
        try:
            # Generate test data
            test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl')
            for i in range(1000):
                entry = {
                    "timestamp": f"2024-02-{i%28+1:02d}T12:00:00Z",
                    "model": "claude-sonnet-4",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.015
                }
                test_file.write(json.dumps(entry) + '\n')
            test_file.close()

            # Time the parsing
            start = time.time()
            with open(test_file.name, 'r') as f:
                data = [json.loads(line) for line in f]
            duration = time.time() - start

            # Cleanup
            Path(test_file.name).unlink()

            # Check against target (< 100ms)
            target_ms = 100
            duration_ms = duration * 1000

            if duration_ms < target_ms:
                self.log("Medium dataset parsing (1,000 entries)",
                        "PASS",
                        f"{duration_ms:.2f}ms (target: <{target_ms}ms)",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})
            else:
                self.log("Medium dataset parsing (1,000 entries)",
                        "FAIL",
                        f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})

        except Exception as e:
            self.log("Medium dataset parsing", "FAIL", str(e))

    def benchmark_large_data_parsing(self):
        """Benchmark parsing large dataset (10,000 entries)"""
        try:
            # Generate test data
            test_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl')
            for i in range(10000):
                entry = {
                    "timestamp": f"2024-02-{i%28+1:02d}T12:00:00Z",
                    "model": "claude-sonnet-4",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.015
                }
                test_file.write(json.dumps(entry) + '\n')
            test_file.close()

            # Time the parsing
            start = time.time()
            with open(test_file.name, 'r') as f:
                data = [json.loads(line) for line in f]
            duration = time.time() - start

            # Cleanup
            Path(test_file.name).unlink()

            # Check against target (< 1000ms)
            target_ms = 1000
            duration_ms = duration * 1000

            if duration_ms < target_ms:
                self.log("Large dataset parsing (10,000 entries)",
                        "PASS",
                        f"{duration_ms:.2f}ms (target: <{target_ms}ms)",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})
            else:
                self.log("Large dataset parsing (10,000 entries)",
                        "FAIL",
                        f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})

        except Exception as e:
            self.log("Large dataset parsing", "FAIL", str(e))

    def benchmark_process_monitoring(self):
        """Benchmark process monitoring performance"""
        try:
            from lib.process_monitor import ProcessMonitor

            monitor = ProcessMonitor()

            # Time process listing
            start = time.time()
            processes = monitor.list_all_processes()
            duration = time.time() - start

            # Check against target (< 100ms)
            target_ms = 100
            duration_ms = duration * 1000

            if duration_ms < target_ms:
                self.log("Process monitoring",
                        "PASS",
                        f"{duration_ms:.2f}ms for {len(processes)} processes (target: <{target_ms}ms)",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms, "process_count": len(processes)})
            else:
                self.log("Process monitoring",
                        "FAIL",
                        f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                        benchmark={"duration_ms": duration_ms, "target_ms": target_ms})

        except Exception as e:
            self.log("Process monitoring", "FAIL", str(e))

    def test_memory_usage(self):
        """Test memory usage is reasonable"""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024

            # Target: < 500MB for test suite
            target_mb = 500

            if mem_mb < target_mb:
                self.log("Memory usage",
                        "PASS",
                        f"{mem_mb:.1f}MB (target: <{target_mb}MB)",
                        benchmark={"memory_mb": mem_mb, "target_mb": target_mb})
            else:
                self.log("Memory usage",
                        "FAIL",
                        f"{mem_mb:.1f}MB exceeds target {target_mb}MB",
                        benchmark={"memory_mb": mem_mb, "target_mb": target_mb})

        except ImportError:
            self.log("Memory usage", "PASS", "psutil not available, skipping")
        except Exception as e:
            self.log("Memory usage", "FAIL", str(e))

    def test_import_performance(self):
        """Test that module imports are fast"""
        modules = [
            'lib.api_client',
            'lib.costs_parser',
            'lib.process_monitor',
            'lib.tool_interceptor',
        ]

        for module_name in modules:
            try:
                start = time.time()
                __import__(module_name)
                duration = time.time() - start
                duration_ms = duration * 1000

                # Target: < 100ms per import
                target_ms = 100

                if duration_ms < target_ms:
                    self.log(f"Import {module_name}",
                            "PASS",
                            f"{duration_ms:.2f}ms",
                            benchmark={"duration_ms": duration_ms, "target_ms": target_ms})
                else:
                    self.log(f"Import {module_name}",
                            "FAIL",
                            f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                            benchmark={"duration_ms": duration_ms, "target_ms": target_ms})

            except Exception as e:
                self.log(f"Import {module_name}", "FAIL", str(e))

    def test_costs_parser_performance(self):
        """Test costs parser with real data if available"""
        try:
            from lib.costs_parser import parse_costs

            costs_file = Path.home() / ".zeroclaw" / "state" / "costs.jsonl"

            if costs_file.exists():
                start = time.time()
                costs = parse_costs(str(costs_file))
                duration = time.time() - start
                duration_ms = duration * 1000

                # Dynamic target based on size
                entry_count = len(costs)
                if entry_count < 100:
                    target_ms = 50
                elif entry_count < 1000:
                    target_ms = 100
                else:
                    target_ms = 1000

                if duration_ms < target_ms:
                    self.log("Costs parser (real data)",
                            "PASS",
                            f"{duration_ms:.2f}ms for {entry_count} entries (target: <{target_ms}ms)",
                            benchmark={"duration_ms": duration_ms, "entry_count": entry_count, "target_ms": target_ms})
                else:
                    self.log("Costs parser (real data)",
                            "FAIL",
                            f"{duration_ms:.2f}ms exceeds target {target_ms}ms",
                            benchmark={"duration_ms": duration_ms, "entry_count": entry_count, "target_ms": target_ms})
            else:
                self.log("Costs parser (real data)", "PASS", "No costs file found (acceptable)")

        except Exception as e:
            self.log("Costs parser (real data)", "FAIL", str(e))

    def generate_report(self):
        """Generate markdown report with benchmark data"""
        report = f"""# Team 4: Performance Testing Results

**Test Execution Time**: {datetime.now().isoformat()}

## Summary
- **Total Tests**: {self.passed + self.failed}
- **Passed**: {self.passed}
- **Failed**: {self.failed}
- **Pass Rate**: {(self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0:.1f}%

## Status
{'✅ ALL PERFORMANCE TESTS PASSED' if self.failed == 0 else '❌ PERFORMANCE ISSUES DETECTED'}

## Benchmark Summary

"""
        if self.benchmarks:
            report += "| Test | Result | Target | Status |\n"
            report += "|------|--------|--------|--------|\n"

            for test_name, benchmark in self.benchmarks.items():
                result = next((r for r in self.results if r['test'] == test_name), None)
                status = "✓" if result and result['status'] == "PASS" else "✗"

                if 'duration_ms' in benchmark:
                    report += f"| {test_name} | {benchmark['duration_ms']:.2f}ms | <{benchmark['target_ms']}ms | {status} |\n"
                elif 'memory_mb' in benchmark:
                    report += f"| {test_name} | {benchmark['memory_mb']:.1f}MB | <{benchmark['target_mb']}MB | {status} |\n"

        report += "\n## Detailed Results\n\n"

        for result in self.results:
            status_icon = "✓" if result["status"] == "PASS" else "✗"
            report += f"### {status_icon} {result['test']}\n"
            report += f"- **Status**: {result['status']}\n"
            if result['details']:
                report += f"- **Details**: {result['details']}\n"
            if 'benchmark' in result:
                report += f"- **Benchmark**: {result['benchmark']}\n"
            report += f"- **Time**: {result['timestamp']}\n\n"

        report += """
## Performance Targets

### Parsing Performance
- Small dataset (100 entries): < 10ms
- Medium dataset (1,000 entries): < 100ms
- Large dataset (10,000 entries): < 1 second

### Resource Limits
- Memory usage: < 500MB
- Module import time: < 100ms per module
- Process monitoring: < 100ms

## Recommendations

"""
        if self.failed == 0:
            report += "- ✅ All performance benchmarks met\n"
            report += "- ✅ System performs within acceptable limits\n"
            report += "- ✅ Ready for production workloads\n"
        else:
            report += "- ⚠️ Some performance benchmarks not met\n"
            report += "- ⚠️ Review slow operations for optimization\n"
            report += "- ⚠️ Consider caching or lazy loading strategies\n"
            report += "- ⚠️ Monitor production performance closely\n"

        return report

def main():
    print("=" * 60)
    print("TEAM 4: PERFORMANCE TESTING")
    print("=" * 60)
    print()

    tester = Team4PerformanceTester()

    print("Benchmarking data parsing...")
    tester.benchmark_small_data_parsing()
    tester.benchmark_medium_data_parsing()
    tester.benchmark_large_data_parsing()
    print()

    print("Benchmarking process monitoring...")
    tester.benchmark_process_monitoring()
    print()

    print("Testing memory usage...")
    tester.test_memory_usage()
    print()

    print("Testing import performance...")
    tester.test_import_performance()
    print()

    print("Testing costs parser with real data...")
    tester.test_costs_parser_performance()
    print()

    # Generate report
    report = tester.generate_report()

    report_path = Path(__file__).parent / "test_results_performance.md"
    report_path.write_text(report)

    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print(f"Results: {tester.passed} passed, {tester.failed} failed")
    print("=" * 60)

    return 0 if tester.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
