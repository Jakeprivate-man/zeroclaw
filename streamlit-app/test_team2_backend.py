#!/usr/bin/env python3
"""
Team 2: Backend Integration Testing
Validates ZeroClaw CLI, filesystem, and process integration
"""

import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
import json

class Team2BackendTester:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.zeroclaw_binary = Path.home() / "zeroclaw/target/release/zeroclaw"
        self.zeroclaw_dir = Path.home() / ".zeroclaw"

    def log(self, test_name, status, details=""):
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        if status == "PASS":
            self.passed += 1
            print(f"✓ {test_name}")
        else:
            self.failed += 1
            print(f"✗ {test_name}")
            if details:
                print(f"  Details: {details}")

    def test_binary_exists(self):
        """Test that ZeroClaw binary exists and is executable"""
        if self.zeroclaw_binary.exists():
            if os.access(self.zeroclaw_binary, os.X_OK):
                self.log("ZeroClaw binary exists and executable", "PASS", str(self.zeroclaw_binary))
            else:
                self.log("ZeroClaw binary exists and executable", "FAIL",
                        f"Binary not executable: {self.zeroclaw_binary}")
        else:
            self.log("ZeroClaw binary exists and executable", "FAIL",
                    f"Binary not found at: {self.zeroclaw_binary}")

    def test_binary_version(self):
        """Test that ZeroClaw binary responds to --version"""
        try:
            result = subprocess.run(
                [str(self.zeroclaw_binary), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log("ZeroClaw --version command", "PASS", f"Version: {version}")
            else:
                self.log("ZeroClaw --version command", "FAIL",
                        f"Exit code: {result.returncode}, stderr: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.log("ZeroClaw --version command", "FAIL", "Command timed out after 5 seconds")
        except Exception as e:
            self.log("ZeroClaw --version command", "FAIL", str(e))

    def test_binary_help(self):
        """Test that ZeroClaw binary responds to --help"""
        try:
            result = subprocess.run(
                [str(self.zeroclaw_binary), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and "Usage:" in result.stdout:
                self.log("ZeroClaw --help command", "PASS")
            else:
                self.log("ZeroClaw --help command", "FAIL",
                        f"Unexpected output or exit code: {result.returncode}")
        except Exception as e:
            self.log("ZeroClaw --help command", "FAIL", str(e))

    def test_filesystem_structure(self):
        """Test that ZeroClaw filesystem structure exists"""
        paths_to_check = [
            ("ZeroClaw directory", self.zeroclaw_dir),
            ("Config file", self.zeroclaw_dir / "config.toml"),
            ("State directory", self.zeroclaw_dir / "state"),
            ("Costs file", self.zeroclaw_dir / "state" / "costs.jsonl"),
        ]

        for name, path in paths_to_check:
            if path.exists():
                self.log(f"{name} exists", "PASS", str(path))
            else:
                self.log(f"{name} exists", "FAIL", f"Not found: {path}")

    def test_file_readability(self):
        """Test that critical files are readable"""
        files_to_read = [
            ("Config file", self.zeroclaw_dir / "config.toml"),
            ("Costs file", self.zeroclaw_dir / "state" / "costs.jsonl"),
        ]

        for name, path in files_to_read:
            if path.exists():
                try:
                    content = path.read_text()
                    if len(content) > 0:
                        self.log(f"{name} readable", "PASS", f"Size: {len(content)} bytes")
                    else:
                        self.log(f"{name} readable", "PASS", "File exists but empty")
                except Exception as e:
                    self.log(f"{name} readable", "FAIL", str(e))
            else:
                self.log(f"{name} readable", "FAIL", f"File not found: {path}")

    def test_library_imports(self):
        """Test that backend library modules can be imported"""
        modules = [
            'lib.cli_executor',
            'lib.process_monitor',
            'lib.memory_reader',
            'lib.costs_parser',
            'lib.budget_manager',
            'lib.agent_monitor',
            'lib.conversation_manager',
            'lib.tool_history_parser',
        ]

        for module_name in modules:
            try:
                __import__(module_name)
                self.log(f"Import {module_name}", "PASS")
            except Exception as e:
                self.log(f"Import {module_name}", "FAIL", str(e))

    def test_process_monitor(self):
        """Test process monitoring functionality"""
        try:
            from lib.process_monitor import ProcessMonitor

            monitor = ProcessMonitor()
            processes = monitor.list_all_processes()

            if isinstance(processes, list):
                self.log("Process monitoring functional", "PASS",
                        f"Found {len(processes)} processes")
            else:
                self.log("Process monitoring functional", "FAIL",
                        "list_all_processes() did not return a list")
        except Exception as e:
            self.log("Process monitoring functional", "FAIL", str(e))

    def test_costs_parser(self):
        """Test costs file parsing"""
        try:
            from lib.costs_parser import parse_costs

            costs_file = self.zeroclaw_dir / "state" / "costs.jsonl"
            if costs_file.exists():
                costs = parse_costs(str(costs_file))
                if isinstance(costs, list):
                    self.log("Costs file parsing", "PASS", f"Parsed {len(costs)} entries")
                else:
                    self.log("Costs file parsing", "FAIL", "parse_costs() did not return a list")
            else:
                self.log("Costs file parsing", "PASS", "Costs file not found (acceptable)")
        except Exception as e:
            self.log("Costs file parsing", "FAIL", str(e))

    def test_streamlit_process(self):
        """Test that Streamlit process is running"""
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True
            )
            if "streamlit run app.py" in result.stdout:
                self.log("Streamlit process running", "PASS")
            else:
                self.log("Streamlit process running", "FAIL",
                        "Streamlit process not detected")
        except Exception as e:
            self.log("Streamlit process running", "FAIL", str(e))

    def generate_report(self):
        """Generate markdown report"""
        report = f"""# Team 2: Backend Integration Testing Results

**Test Execution Time**: {datetime.now().isoformat()}

## Summary
- **Total Tests**: {self.passed + self.failed}
- **Passed**: {self.passed}
- **Failed**: {self.failed}
- **Pass Rate**: {(self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0:.1f}%

## Status
{'✅ ALL TESTS PASSED' if self.failed == 0 else '❌ TESTS FAILED'}

## Environment
- **ZeroClaw Binary**: {self.zeroclaw_binary}
- **ZeroClaw Directory**: {self.zeroclaw_dir}

## Detailed Results

"""
        for result in self.results:
            status_icon = "✓" if result["status"] == "PASS" else "✗"
            report += f"### {status_icon} {result['test']}\n"
            report += f"- **Status**: {result['status']}\n"
            if result['details']:
                report += f"- **Details**: {result['details']}\n"
            report += f"- **Time**: {result['timestamp']}\n\n"

        report += f"""
## Recommendations

"""
        if self.failed == 0:
            report += "- All backend integration tests passed successfully\n"
            report += "- ZeroClaw CLI integration is functional\n"
            report += "- File system operations are working\n"
        else:
            report += "- Verify ZeroClaw binary is built and accessible\n"
            report += "- Check that ZeroClaw directory structure is initialized\n"
            report += "- Ensure all backend library dependencies are installed\n"

        return report

def main():
    print("=" * 60)
    print("TEAM 2: BACKEND INTEGRATION TESTING")
    print("=" * 60)
    print()

    tester = Team2BackendTester()

    print("Testing ZeroClaw binary...")
    tester.test_binary_exists()
    tester.test_binary_version()
    tester.test_binary_help()
    print()

    print("Testing filesystem structure...")
    tester.test_filesystem_structure()
    tester.test_file_readability()
    print()

    print("Testing library imports...")
    tester.test_library_imports()
    print()

    print("Testing backend functionality...")
    tester.test_process_monitor()
    tester.test_costs_parser()
    tester.test_streamlit_process()
    print()

    # Generate report
    report = tester.generate_report()

    report_path = Path(__file__).parent / "test_results_backend.md"
    report_path.write_text(report)

    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print(f"Results: {tester.passed} passed, {tester.failed} failed")
    print("=" * 60)

    return 0 if tester.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
