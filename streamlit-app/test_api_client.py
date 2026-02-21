"""Test script for ZeroClaw API Client.

This script demonstrates basic usage and error handling of the API client.
"""

import sys
from lib.api_client import api


def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    try:
        health = api.get_health()
        print(f"  Status: {health.get('status')}")
        if 'uptime' in health:
            print(f"  Uptime: {health['uptime']}s")
        if 'version' in health:
            print(f"  Version: {health['version']}")
        if 'error' in health:
            print(f"  Error: {health['error']}")
        return health.get('status') == 'ok'
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_reports():
    """Test reports endpoint."""
    print("\nTesting reports endpoint...")
    try:
        reports = api.get_reports()
        print(f"  Found {len(reports)} reports:")
        for report in reports[:5]:  # Show first 5
            name = report.get('name', 'Unknown')
            size = report.get('size', 0)
            print(f"    - {name}: {size:,} bytes")
        if len(reports) > 5:
            print(f"    ... and {len(reports) - 5} more")
        return True
    except ConnectionError as e:
        print(f"  Connection Error: {e}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_report_content():
    """Test getting specific report content."""
    print("\nTesting report content endpoint...")
    try:
        reports = api.get_reports()
        if not reports:
            print("  No reports available to test")
            return True

        # Get first report
        first_report = reports[0]['name']
        print(f"  Fetching content for: {first_report}")

        content = api.get_report_content(first_report)
        preview = content[:200] if len(content) > 200 else content
        print(f"  Content preview ({len(content)} total chars):")
        print(f"    {preview}...")
        return True
    except FileNotFoundError as e:
        print(f"  File Not Found: {e}")
        return False
    except ConnectionError as e:
        print(f"  Connection Error: {e}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("ZeroClaw API Client Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Health
    results.append(("Health Check", test_health()))

    # Test 2: List Reports
    results.append(("List Reports", test_reports()))

    # Test 3: Get Report Content
    results.append(("Get Report Content", test_report_content()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
