#!/usr/bin/env python3
"""
Master Test Orchestrator
Runs all 5 testing teams in parallel and generates master report
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import threading
import queue

class TestOrchestrator:
    def __init__(self):
        self.teams = [
            {
                'name': 'Team 1: UI/Frontend Testing',
                'script': 'test_team1_ui.py',
                'report': 'test_results_ui.md',
                'critical': False
            },
            {
                'name': 'Team 2: Backend Integration Testing',
                'script': 'test_team2_backend.py',
                'report': 'test_results_backend.md',
                'critical': False
            },
            {
                'name': 'Team 3: Security Testing',
                'script': 'test_team3_security.py',
                'report': 'test_results_security.md',
                'critical': True  # Security is critical
            },
            {
                'name': 'Team 4: Performance Testing',
                'script': 'test_team4_performance.py',
                'report': 'test_results_performance.md',
                'critical': False
            },
            {
                'name': 'Team 5: End-to-End Workflow Testing',
                'script': 'test_team5_e2e.py',
                'report': 'test_results_e2e.md',
                'critical': True  # E2E is critical
            }
        ]
        self.results = {}
        self.start_time = None
        self.end_time = None

    def run_team(self, team, result_queue):
        """Run a single team's tests"""
        print(f"\n{'='*60}")
        print(f"LAUNCHING: {team['name']}")
        print(f"{'='*60}\n")

        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, team['script']],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per team
            )

            duration = time.time() - start

            result_data = {
                'team': team['name'],
                'script': team['script'],
                'report': team['report'],
                'critical': team['critical'],
                'exit_code': result.returncode,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }

            result_queue.put(result_data)

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            result_queue.put({
                'team': team['name'],
                'script': team['script'],
                'report': team['report'],
                'critical': team['critical'],
                'exit_code': -1,
                'duration': duration,
                'stdout': '',
                'stderr': 'Test timed out after 5 minutes',
                'success': False
            })
        except Exception as e:
            duration = time.time() - start
            result_queue.put({
                'team': team['name'],
                'script': team['script'],
                'report': team['report'],
                'critical': team['critical'],
                'exit_code': -1,
                'duration': duration,
                'stdout': '',
                'stderr': str(e),
                'success': False
            })

    def run_all_teams(self):
        """Run all teams in parallel"""
        print("\n" + "="*60)
        print("ZEROCLAW STREAMLIT UI - MASTER TEST ORCHESTRATOR")
        print("="*60)
        print(f"Start Time: {datetime.now().isoformat()}")
        print(f"Teams: {len(self.teams)}")
        print("="*60)

        self.start_time = time.time()

        # Create result queue and threads
        result_queue = queue.Queue()
        threads = []

        # Launch all teams concurrently
        for team in self.teams:
            thread = threading.Thread(target=self.run_team, args=(team, result_queue))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Collect results
        while not result_queue.empty():
            result = result_queue.get()
            self.results[result['team']] = result

        self.end_time = time.time()

    def analyze_results(self):
        """Analyze all results and determine pass/fail"""
        total_teams = len(self.results)
        passed_teams = sum(1 for r in self.results.values() if r['success'])
        failed_teams = total_teams - passed_teams

        critical_failures = [
            r for r in self.results.values()
            if r['critical'] and not r['success']
        ]

        return {
            'total_teams': total_teams,
            'passed_teams': passed_teams,
            'failed_teams': failed_teams,
            'critical_failures': critical_failures,
            'overall_pass': failed_teams == 0,
            'critical_pass': len(critical_failures) == 0,
            'duration': self.end_time - self.start_time
        }

    def generate_master_report(self):
        """Generate master test report"""
        analysis = self.analyze_results()

        report = f"""# ZeroClaw Streamlit UI - Master Test Report

**Test Execution Time**: {datetime.now().isoformat()}
**Total Duration**: {analysis['duration']:.2f} seconds

## Executive Summary

### Overall Status
{'✅ ALL TESTS PASSED' if analysis['overall_pass'] else '❌ TESTS FAILED'}

### Critical Status
{'✅ NO CRITICAL FAILURES' if analysis['critical_pass'] else '🔴 CRITICAL FAILURES DETECTED'}

### Team Results
- **Total Teams**: {analysis['total_teams']}
- **Passed**: {analysis['passed_teams']}
- **Failed**: {analysis['failed_teams']}
- **Success Rate**: {(analysis['passed_teams'] / analysis['total_teams'] * 100):.1f}%

"""

        if analysis['critical_failures']:
            report += """
## 🔴 CRITICAL FAILURES

The following critical test suites failed and MUST be fixed before deployment:

"""
            for failure in analysis['critical_failures']:
                report += f"- **{failure['team']}**\n"
                report += f"  - Exit Code: {failure['exit_code']}\n"
                report += f"  - Duration: {failure['duration']:.2f}s\n"
                if failure['stderr']:
                    report += f"  - Error: {failure['stderr'][:200]}...\n"
                report += "\n"

        report += """
## Team Summaries

"""

        for team_name, result in sorted(self.results.items()):
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            critical = " [CRITICAL]" if result['critical'] else ""

            report += f"### {status} {team_name}{critical}\n\n"
            report += f"- **Script**: `{result['script']}`\n"
            report += f"- **Report**: `{result['report']}`\n"
            report += f"- **Duration**: {result['duration']:.2f}s\n"
            report += f"- **Exit Code**: {result['exit_code']}\n"

            # Try to read team report and extract summary
            report_path = Path(__file__).parent / result['report']
            if report_path.exists():
                try:
                    team_report = report_path.read_text()
                    # Extract summary section
                    if "## Summary" in team_report:
                        summary_start = team_report.find("## Summary")
                        summary_end = team_report.find("##", summary_start + 11)
                        if summary_end > 0:
                            summary = team_report[summary_start:summary_end].strip()
                            report += f"\n{summary}\n"
                except:
                    pass

            report += "\n"

        report += """
## Detailed Reports

Each team has generated a detailed report:

"""
        for team_name, result in sorted(self.results.items()):
            report += f"- [{team_name}]({result['report']})\n"

        report += """

## Test Coverage

### UI/Frontend Testing (Team 1)
- ✓ Page imports (7 pages)
- ✓ Component imports (24+ components)
- ✓ Library imports (17+ modules)
- ✓ Python syntax validation
- ✓ Critical class instantiation

### Backend Integration Testing (Team 2)
- ✓ ZeroClaw binary validation
- ✓ Filesystem structure verification
- ✓ CLI command execution
- ✓ Data file parsing
- ✓ Process monitoring
- ✓ Library module functionality

### Security Testing (Team 3)
- ✓ Security module imports
- ✓ Tool interception
- ✓ Risk scoring accuracy
- ✓ Approval/rejection workflow
- ✓ Audit logging
- ✓ Credential scrubbing
- ✓ Danger level consistency

### Performance Testing (Team 4)
- ✓ Data parsing benchmarks (100/1K/10K entries)
- ✓ Process monitoring performance
- ✓ Memory usage validation
- ✓ Import performance
- ✓ Real data parsing

### End-to-End Workflow Testing (Team 5)
- ✓ Streamlit server accessibility
- ✓ Page accessibility (7 pages)
- ✓ Chat workflow
- ✓ Dashboard workflow
- ✓ Analytics workflow (8 charts)
- ✓ Tool approval workflow
- ✓ Gateway integration
- ✓ Reports workflow
- ✓ Session state management
- ✓ Data flow integration
- ✓ Error handling

## Deployment Decision

"""

        if analysis['overall_pass'] and analysis['critical_pass']:
            report += """
### ✅ GO FOR DEPLOYMENT

All test suites passed successfully, including critical security and E2E tests.
The system is ready for production deployment.

**Recommended Next Steps:**
1. Deploy to staging environment
2. Perform user acceptance testing
3. Monitor production metrics closely
4. Keep test suites running in CI/CD

"""
        elif analysis['critical_pass'] and not analysis['overall_pass']:
            report += """
### ⚠️ CONDITIONAL GO

Critical tests passed, but some non-critical tests failed.
System can be deployed with caution.

**Required Actions:**
1. Review non-critical test failures
2. Create tickets for failed test fixes
3. Deploy with monitoring
4. Fix failures in next sprint

"""
        else:
            report += """
### 🔴 NO-GO FOR DEPLOYMENT

Critical test failures detected. DO NOT DEPLOY to production.

**Required Actions:**
1. Fix all critical test failures immediately
2. Re-run full test suite
3. Conduct security review if Team 3 failed
4. Verify E2E workflows if Team 5 failed
5. Only deploy after all tests pass

"""

        report += f"""
## Bug Summary

"""
        bugs = []
        for team_name, result in self.results.items():
            if not result['success']:
                bugs.append({
                    'team': team_name,
                    'severity': 'CRITICAL' if result['critical'] else 'HIGH',
                    'description': f"{team_name} failed",
                    'error': result['stderr'][:200] if result['stderr'] else 'Unknown error'
                })

        if bugs:
            report += f"**Total Bugs Found**: {len(bugs)}\n\n"
            for i, bug in enumerate(bugs, 1):
                report += f"{i}. **{bug['severity']}**: {bug['description']}\n"
                report += f"   - Error: {bug['error']}\n\n"
        else:
            report += "**No bugs detected** - All tests passed!\n\n"

        report += """
---

**Test Orchestrator Version**: 1.0
**Generated**: {datetime.now().isoformat()}
"""

        return report

    def print_summary(self):
        """Print summary to console"""
        analysis = self.analyze_results()

        print("\n" + "="*60)
        print("TEST EXECUTION COMPLETE")
        print("="*60)
        print(f"Duration: {analysis['duration']:.2f} seconds")
        print(f"Teams Passed: {analysis['passed_teams']}/{analysis['total_teams']}")
        print()

        for team_name, result in sorted(self.results.items()):
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            critical = " [CRITICAL]" if result['critical'] else ""
            print(f"{status} {team_name}{critical} ({result['duration']:.2f}s)")

        print()
        print("="*60)

        if analysis['overall_pass']:
            print("✅ RESULT: ALL TESTS PASSED")
        else:
            print("❌ RESULT: TESTS FAILED")

        if analysis['critical_failures']:
            print("🔴 CRITICAL FAILURES DETECTED - DO NOT DEPLOY")
        else:
            print("✅ NO CRITICAL FAILURES")

        print("="*60)

def main():
    orchestrator = TestOrchestrator()

    # Run all teams
    orchestrator.run_all_teams()

    # Print summary
    orchestrator.print_summary()

    # Generate master report
    report = orchestrator.generate_master_report()
    report_path = Path(__file__).parent / "TEST_REPORT_MASTER.md"
    report_path.write_text(report)

    print(f"\n📄 Master report saved to: {report_path}")

    # Return exit code
    analysis = orchestrator.analyze_results()
    return 0 if analysis['overall_pass'] else 1

if __name__ == "__main__":
    sys.exit(main())
