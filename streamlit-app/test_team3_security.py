#!/usr/bin/env python3
"""
Team 3: Security Testing
Validates tool approval system and security boundaries (CRITICAL)
"""

import sys
import os
from datetime import datetime
from pathlib import Path

class Team3SecurityTester:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.critical_failures = []

    def log(self, test_name, status, details="", critical=False):
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "critical": critical,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        if status == "PASS":
            self.passed += 1
            print(f"✓ {test_name}")
        else:
            self.failed += 1
            if critical:
                self.critical_failures.append(test_name)
                print(f"✗ [CRITICAL] {test_name}")
            else:
                print(f"✗ {test_name}")
            if details:
                print(f"  Details: {details}")

    def test_security_module_imports(self):
        """Test that security modules can be imported"""
        modules = [
            ('lib.tool_interceptor', True),
            ('lib.security_analyzer', True),
            ('lib.audit_logger', True),
        ]

        for module_name, critical in modules:
            try:
                __import__(module_name)
                self.log(f"Import {module_name}", "PASS", critical=critical)
            except Exception as e:
                self.log(f"Import {module_name}", "FAIL", str(e), critical=critical)

    def test_tool_interceptor(self):
        """Test tool interceptor functionality"""
        try:
            from lib.tool_interceptor import ToolInterceptor, ToolDangerLevel

            interceptor = ToolInterceptor()

            # Test initialization
            if hasattr(interceptor, 'pending_calls'):
                self.log("ToolInterceptor initialization", "PASS")
            else:
                self.log("ToolInterceptor initialization", "FAIL",
                        "Missing pending_calls attribute", critical=True)
                return

            # Test safe tool interception
            try:
                tool_call = interceptor.intercept('memory_recall', {'query': 'test'})
                if tool_call.danger_level == ToolDangerLevel.SAFE:
                    self.log("Safe tool classification", "PASS")
                else:
                    self.log("Safe tool classification", "FAIL",
                            f"Expected SAFE, got {tool_call.danger_level}")
            except Exception as e:
                self.log("Safe tool classification", "FAIL", str(e))

            # Test dangerous tool interception
            try:
                tool_call = interceptor.intercept('shell', {'command': 'ls'})
                if tool_call.danger_level in [ToolDangerLevel.HIGH, ToolDangerLevel.CRITICAL]:
                    self.log("Dangerous tool classification", "PASS",
                            f"Classified as {tool_call.danger_level}")
                else:
                    self.log("Dangerous tool classification", "FAIL",
                            f"Shell should be HIGH/CRITICAL, got {tool_call.danger_level}",
                            critical=True)
            except Exception as e:
                self.log("Dangerous tool classification", "FAIL", str(e), critical=True)

            # Test critical command detection
            try:
                tool_call = interceptor.intercept('shell', {'command': 'rm -rf /'})
                if tool_call.danger_level == ToolDangerLevel.CRITICAL:
                    self.log("Critical command detection", "PASS")
                else:
                    self.log("Critical command detection", "FAIL",
                            f"rm -rf should be CRITICAL, got {tool_call.danger_level}",
                            critical=True)
            except Exception as e:
                self.log("Critical command detection", "FAIL", str(e), critical=True)

        except Exception as e:
            self.log("Tool interceptor tests", "FAIL", str(e), critical=True)

    def test_approval_rejection_flow(self):
        """Test tool approval and rejection workflow"""
        try:
            from lib.tool_interceptor import ToolInterceptor

            interceptor = ToolInterceptor()

            # Test approval flow
            tool_call = interceptor.intercept('shell', {'command': 'ls'})
            call_id = tool_call.id

            success = interceptor.approve(call_id, approver='test_user')

            if success and call_id in interceptor.approved_calls:
                self.log("Tool approval flow", "PASS")
            else:
                self.log("Tool approval flow", "FAIL",
                        "Approval did not work correctly", critical=True)

            # Test rejection flow
            tool_call2 = interceptor.intercept('shell', {'command': 'rm -rf /'})
            call_id2 = tool_call2.id

            success2 = interceptor.reject(call_id2, approver='test_user', reason='Dangerous')

            if success2 and call_id2 in interceptor.rejected_calls:
                self.log("Tool rejection flow", "PASS")
            else:
                self.log("Tool rejection flow", "FAIL",
                        "Rejection did not work correctly", critical=True)

        except Exception as e:
            self.log("Approval/rejection flow tests", "FAIL", str(e), critical=True)

    def test_security_analyzer(self):
        """Test security analysis functionality"""
        try:
            from lib.security_analyzer import SecurityAnalyzer

            analyzer = SecurityAnalyzer()

            # Test dangerous command analysis
            assessment = analyzer.analyze('shell', {'command': 'rm -rf /'})

            if assessment.risk_score > 50:
                self.log("High risk detection", "PASS",
                        f"Risk score: {assessment.risk_score}")
            else:
                self.log("High risk detection", "FAIL",
                        f"Expected high risk score, got {assessment.risk_score}",
                        critical=True)

            if not assessment.allow_execution:
                self.log("Dangerous command blocking", "PASS")
            else:
                self.log("Dangerous command blocking", "FAIL",
                        "Dangerous command was allowed to execute", critical=True)

            # Test safe command analysis
            assessment_safe = analyzer.analyze('memory_recall', {'query': 'test'})

            if assessment_safe.risk_score < assessment.risk_score:
                self.log("Safe vs dangerous risk scoring", "PASS")
            else:
                self.log("Safe vs dangerous risk scoring", "FAIL",
                        "Safe command has higher risk than dangerous command")

        except Exception as e:
            self.log("Security analyzer tests", "FAIL", str(e), critical=True)

    def test_audit_logger(self):
        """Test audit logging functionality"""
        try:
            from lib.audit_logger import AuditLogger
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
                temp_log = f.name

            try:
                logger = AuditLogger(log_file=temp_log)

                # Test logging approval
                logger.log_approval(
                    tool_name='shell',
                    parameters={'command': 'ls'},
                    approver='test_user',
                    approved=True
                )

                # Verify log file was written
                log_path = Path(temp_log)
                if log_path.exists() and log_path.stat().st_size > 0:
                    self.log("Audit logging functionality", "PASS")
                else:
                    self.log("Audit logging functionality", "FAIL",
                            "Log file not created or empty", critical=True)
            finally:
                # Cleanup
                if Path(temp_log).exists():
                    Path(temp_log).unlink()

        except Exception as e:
            self.log("Audit logger tests", "FAIL", str(e), critical=True)

    def test_credential_scrubbing(self):
        """Test that credentials are scrubbed from logs"""
        try:
            from lib.audit_logger import AuditLogger
            import tempfile
            import json

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
                temp_log = f.name

            try:
                logger = AuditLogger(log_file=temp_log)

                # Log something with a credential-like parameter
                logger.log_approval(
                    tool_name='api_call',
                    parameters={'api_key': 'sk-super-secret-key-12345', 'query': 'test'},
                    approver='test_user',
                    approved=True
                )

                # Read log and check for scrubbing
                with open(temp_log, 'r') as f:
                    log_content = f.read()

                # Credential should NOT be in plain text
                if 'sk-super-secret-key-12345' not in log_content:
                    self.log("Credential scrubbing", "PASS", "API key properly redacted")
                else:
                    self.log("Credential scrubbing", "FAIL",
                            "Credential found in log file (security leak!)", critical=True)
            finally:
                if Path(temp_log).exists():
                    Path(temp_log).unlink()

        except Exception as e:
            self.log("Credential scrubbing test", "FAIL", str(e), critical=True)

    def test_danger_levels_consistent(self):
        """Test that danger levels are consistent across modules"""
        try:
            from lib.tool_interceptor import ToolDangerLevel as InterceptorDanger
            from lib.tool_history_parser import ToolDangerLevel as ParserDanger

            # Check all levels exist in both
            levels = ['SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

            missing_interceptor = [l for l in levels if not hasattr(InterceptorDanger, l)]
            missing_parser = [l for l in levels if not hasattr(ParserDanger, l)]

            if not missing_interceptor and not missing_parser:
                self.log("Danger level consistency", "PASS")
            else:
                details = ""
                if missing_interceptor:
                    details += f"Missing in ToolInterceptor: {missing_interceptor}. "
                if missing_parser:
                    details += f"Missing in ToolHistoryParser: {missing_parser}."
                self.log("Danger level consistency", "FAIL", details)

        except Exception as e:
            self.log("Danger level consistency test", "FAIL", str(e))

    def generate_report(self):
        """Generate markdown report"""
        report = f"""# Team 3: Security Testing Results

**Test Execution Time**: {datetime.now().isoformat()}

## ⚠️ CRITICAL STATUS
{'🔴 CRITICAL FAILURES DETECTED' if self.critical_failures else '✅ NO CRITICAL FAILURES'}

## Summary
- **Total Tests**: {self.passed + self.failed}
- **Passed**: {self.passed}
- **Failed**: {self.failed}
- **Critical Failures**: {len(self.critical_failures)}
- **Pass Rate**: {(self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0:.1f}%

## Overall Status
{'❌ SECURITY VALIDATION FAILED' if self.failed > 0 else '✅ ALL SECURITY TESTS PASSED'}

"""
        if self.critical_failures:
            report += f"""
## 🔴 Critical Failures
The following critical security issues were detected:

"""
            for failure in self.critical_failures:
                report += f"- **{failure}**\n"

            report += "\n⚠️ **THESE MUST BE FIXED BEFORE PRODUCTION DEPLOYMENT**\n\n"

        report += """
## Detailed Results

"""
        for result in self.results:
            status_icon = "✓" if result["status"] == "PASS" else "✗"
            critical_marker = " [CRITICAL]" if result.get("critical") else ""
            report += f"### {status_icon} {result['test']}{critical_marker}\n"
            report += f"- **Status**: {result['status']}\n"
            if result['details']:
                report += f"- **Details**: {result['details']}\n"
            if result.get("critical"):
                report += f"- **Severity**: CRITICAL\n"
            report += f"- **Time**: {result['timestamp']}\n\n"

        report += f"""
## Recommendations

"""
        if self.failed == 0:
            report += "- ✅ All security tests passed successfully\n"
            report += "- ✅ Tool approval system is functional\n"
            report += "- ✅ Security boundaries are enforced\n"
            report += "- ✅ Audit logging is working correctly\n"
            report += "- ✅ Credentials are properly scrubbed\n"
        else:
            report += "- ❌ Fix all critical security issues immediately\n"
            report += "- ❌ Do NOT deploy to production until security tests pass\n"
            report += "- ❌ Review security module implementations\n"
            report += "- ❌ Verify credential scrubbing is working\n"
            report += "- ❌ Test dangerous tool blocking thoroughly\n"

        return report

def main():
    print("=" * 60)
    print("TEAM 3: SECURITY TESTING (CRITICAL)")
    print("=" * 60)
    print()

    tester = Team3SecurityTester()

    print("Testing security module imports...")
    tester.test_security_module_imports()
    print()

    print("Testing tool interceptor...")
    tester.test_tool_interceptor()
    print()

    print("Testing approval/rejection flow...")
    tester.test_approval_rejection_flow()
    print()

    print("Testing security analyzer...")
    tester.test_security_analyzer()
    print()

    print("Testing audit logger...")
    tester.test_audit_logger()
    print()

    print("Testing credential scrubbing...")
    tester.test_credential_scrubbing()
    print()

    print("Testing danger level consistency...")
    tester.test_danger_levels_consistent()
    print()

    # Generate report
    report = tester.generate_report()

    report_path = Path(__file__).parent / "test_results_security.md"
    report_path.write_text(report)

    print("=" * 60)
    print(f"Report saved to: {report_path}")
    print(f"Results: {tester.passed} passed, {tester.failed} failed")
    if tester.critical_failures:
        print(f"🔴 CRITICAL FAILURES: {len(tester.critical_failures)}")
        for failure in tester.critical_failures:
            print(f"  - {failure}")
    print("=" * 60)

    return 0 if tester.failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
