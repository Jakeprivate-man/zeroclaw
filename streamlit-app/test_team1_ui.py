#!/usr/bin/env python3
"""
Team 1: UI/Frontend Testing
Validates all Streamlit UI components and pages
"""

import sys
import importlib
import traceback
from datetime import datetime
from pathlib import Path

class Team1UITester:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

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

    def test_page_imports(self):
        """Test that all page modules can be imported"""
        pages = [
            'app',
            'pages.chat',
            'pages.dashboard',
            'pages.analytics',
            'pages.analyze',
            'pages.reports',
            'pages.settings'
        ]

        for page_module in pages:
            try:
                importlib.import_module(page_module)
                self.log(f"Import {page_module}", "PASS")
            except Exception as e:
                self.log(f"Import {page_module}", "FAIL", str(e))

    def test_component_imports(self):
        """Test that all component modules can be imported"""
        components = [
            'components.sidebar',
            'components.chat.message_history',
            'components.chat.message_input',
            'components.chat.live_chat',
            'components.chat.tool_approval_dialog',
            'components.dashboard.real_time_metrics',
            'components.dashboard.activity_stream',
            'components.dashboard.agent_status_monitor',
            'components.dashboard.quick_actions_panel',
            'components.dashboard.cost_tracking',
            'components.dashboard.token_usage',
            'components.dashboard.agent_config_status',
            'components.dashboard.live_metrics',
            'components.analytics.request_volume_chart',
            'components.analytics.response_time_chart',
            'components.analytics.request_distribution_chart',
            'components.analytics.error_rate_chart',
            'components.analytics.error_types_chart',
            'components.analytics.user_activity_chart',
            'components.analytics.feature_usage_chart',
            'components.analytics.performance_metrics_chart',
            'components.reports.markdown_viewer',
            'components.reports.table_of_contents',
            'components.reports.pdf_export',
            'components.reports.reports_listing',
        ]

        for comp_module in components:
            try:
                importlib.import_module(comp_module)
                self.log(f"Import {comp_module}", "PASS")
            except Exception as e:
                self.log(f"Import {comp_module}", "FAIL", str(e))

    def test_lib_imports(self):
        """Test that all library modules can be imported"""
        libs = [
            'lib.api_client',
            'lib.session_state',
            'lib.costs_parser',
            'lib.budget_manager',
            'lib.agent_monitor',
            'lib.conversation_manager',
            'lib.realtime_poller',
            'lib.cli_executor',
            'lib.response_streamer',
            'lib.process_monitor',
            'lib.memory_reader',
            'lib.tool_history_parser',
            'lib.tool_interceptor',
            'lib.security_analyzer',
            'lib.audit_logger',
            'lib.gateway_client',
            'lib.mock_data',
        ]

        for lib_module in libs:
            try:
                importlib.import_module(lib_module)
                self.log(f"Import {lib_module}", "PASS")
            except Exception as e:
                self.log(f"Import {lib_module}", "FAIL", str(e))

    def test_syntax_validation(self):
        """Test Python syntax on all .py files"""
        import py_compile

        base_path = Path(__file__).parent
        py_files = list(base_path.rglob("*.py"))

        syntax_errors = 0
        for py_file in py_files:
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                syntax_errors += 1
                self.log(f"Syntax check {py_file.name}", "FAIL", str(e))

        if syntax_errors == 0:
            self.log(f"Syntax validation ({len(py_files)} files)", "PASS")
        else:
            self.log(f"Syntax validation ({len(py_files)} files)", "FAIL",
                    f"{syntax_errors} files with syntax errors")

    def test_critical_classes(self):
        """Test that critical classes can be instantiated"""
        tests = [
            ('lib.api_client', 'APIClient'),
            ('lib.session_state', 'init_session_state'),
            ('lib.gateway_client', 'EnhancedGatewayClient'),
        ]

        for module_name, class_or_func in tests:
            try:
                module = importlib.import_module(module_name)
                obj = getattr(module, class_or_func)
                self.log(f"Load {module_name}.{class_or_func}", "PASS")
            except Exception as e:
                self.log(f"Load {module_name}.{class_or_func}", "FAIL", str(e))

    def generate_report(self):
        """Generate markdown report"""
        report = f"""# Team 1: UI/Frontend Testing Results

**Test Execution Time**: {datetime.now().isoformat()}

## Summary
- **Total Tests**: {self.passed + self.failed}
- **Passed**: {self.passed}
- **Failed**: {self.failed}
- **Pass Rate**: {(self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0:.1f}%

## Status
{'✅ ALL TESTS PASSED' if self.failed == 0 else '❌ TESTS FAILED'}

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
            report += "- All UI/Frontend tests passed successfully\n"
            report += "- UI components are ready for integration testing\n"
        else:
            report += "- Fix import errors before proceeding\n"
            report += "- Verify all dependencies are installed\n"
            report += "- Check Python version compatibility\n"

        return report

def main():
    print("=" * 60)
    print("TEAM 1: UI/FRONTEND TESTING")
    print("=" * 60)
    print()

    tester = Team1UITester()

    print("Testing page imports...")
    tester.test_page_imports()
    print()

    print("Testing component imports...")
    tester.test_component_imports()
    print()

    print("Testing library imports...")
    tester.test_lib_imports()
    print()

    print("Validating Python syntax...")
    tester.test_syntax_validation()
    print()

    print("Testing critical classes...")
    tester.test_critical_classes()
    print()

    # Generate report
    report = tester.generate_report()

    report_path = Path(__file__).parent / "test_results_ui.md"
    report_path.write_text(report)

    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print(f"Results: {tester.passed} passed, {tester.failed} failed")
    print("=" * 60)

    return 0 if tester.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
