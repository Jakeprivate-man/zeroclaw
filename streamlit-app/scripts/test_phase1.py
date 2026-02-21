#!/usr/bin/env python3
"""Integration test for Phase 1 cost tracking features.

This script tests all Phase 1 libraries and verifies they work correctly
with the sample data.

Usage:
    python scripts/test_phase1.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.costs_parser import costs_parser
from lib.budget_manager import budget_manager, BudgetStatus
from lib.agent_monitor import agent_monitor


def test_costs_parser():
    """Test costs_parser functionality."""
    print("=" * 60)
    print("Testing costs_parser.py")
    print("=" * 60)

    # Check file exists
    if not costs_parser.file_exists():
        print("❌ FAIL: costs.jsonl file not found")
        print("   Run: python scripts/generate_sample_costs.py")
        return False

    print("✅ costs.jsonl file exists")

    # Get summary
    summary = costs_parser.get_cost_summary()
    print(f"\n📊 Cost Summary:")
    print(f"  Session cost:  ${summary['session_cost_usd']:.4f}")
    print(f"  Daily cost:    ${summary['daily_cost_usd']:.4f}")
    print(f"  Monthly cost:  ${summary['monthly_cost_usd']:.4f}")
    print(f"  Total tokens:  {summary['total_tokens']:,}")
    print(f"  Requests:      {summary['request_count']}")

    # Check models
    if summary['by_model']:
        print(f"\n📈 Models Used ({len(summary['by_model'])}):")
        for model, stats in summary['by_model'].items():
            print(f"  - {model}: ${stats['cost_usd']:.4f} ({stats['tokens']:,} tokens)")
    else:
        print("⚠️ No model breakdown available")

    # Get recent costs
    recent = costs_parser.get_recent_costs(hours=24, limit=10)
    print(f"\n🕐 Recent Costs (last 24h): {len(recent)} records")

    # Get token history
    history = costs_parser.get_token_history(hours=24)
    print(f"📊 Token History (last 24h): {len(history)} data points")

    print("\n✅ costs_parser tests PASSED\n")
    return True


def test_budget_manager():
    """Test budget_manager functionality."""
    print("=" * 60)
    print("Testing budget_manager.py")
    print("=" * 60)

    # Check if enabled
    enabled = budget_manager.is_enabled()
    print(f"📊 Cost tracking enabled: {enabled}")

    if not enabled:
        print("⚠️ Cost tracking is disabled")
        print("   Enable in ~/.zeroclaw/config.toml: [cost] enabled = true")

    # Get limits
    limits = budget_manager.get_limits()
    print(f"\n💰 Budget Limits:")
    print(f"  Daily:         ${limits['daily_limit_usd']:.2f}")
    print(f"  Monthly:       ${limits['monthly_limit_usd']:.2f}")
    print(f"  Warning at:    {limits['warn_at_percent']:.0f}%")

    # Check budgets
    daily_check = budget_manager.check_budget("daily")
    monthly_check = budget_manager.check_budget("monthly")

    print(f"\n📊 Daily Budget Check:")
    print(f"  Status:        {daily_check['status']}")
    print(f"  Current:       ${daily_check['current_usd']:.4f}")
    print(f"  Limit:         ${daily_check['limit_usd']:.2f}")
    print(f"  Percent used:  {daily_check['percent_used']:.1f}%")
    print(f"  Message:       {daily_check['message']}")

    print(f"\n📊 Monthly Budget Check:")
    print(f"  Status:        {monthly_check['status']}")
    print(f"  Current:       ${monthly_check['current_usd']:.4f}")
    print(f"  Limit:         ${monthly_check['limit_usd']:.2f}")
    print(f"  Percent used:  {monthly_check['percent_used']:.1f}%")
    print(f"  Message:       {monthly_check['message']}")

    # Test alerts
    daily_alert = budget_manager.format_budget_alert("daily")
    monthly_alert = budget_manager.format_budget_alert("monthly")

    if daily_alert:
        print(f"\n🚨 Daily Alert: {daily_alert}")
    if monthly_alert:
        print(f"🚨 Monthly Alert: {monthly_alert}")

    # Get full summary
    summary = budget_manager.get_budget_summary()
    print(f"\n📈 Session Stats:")
    print(f"  Cost:     ${summary['session']['cost_usd']:.4f}")
    print(f"  Tokens:   {summary['session']['tokens']:,}")
    print(f"  Requests: {summary['session']['requests']}")

    print("\n✅ budget_manager tests PASSED\n")
    return True


def test_agent_monitor():
    """Test agent_monitor functionality."""
    print("=" * 60)
    print("Testing agent_monitor.py")
    print("=" * 60)

    # Get default agent
    default = agent_monitor.get_default_agent()
    print(f"🤖 Default Agent:")
    print(f"  Name:        {default['name']}")
    print(f"  Provider:    {default['provider']}")
    print(f"  Model:       {default['model']}")
    print(f"  Temperature: {default['temperature']}")
    print(f"  Status:      {default['status']}")

    # Get configured agents
    configured = agent_monitor.get_configured_agents()
    print(f"\n📋 Configured Agents: {len(configured)}")
    for agent in configured:
        print(f"  - {agent['name']}: {agent['model']} ({agent['provider']})")

    # Get all agents
    all_agents = agent_monitor.get_all_agents()
    print(f"\n📊 Total Agents: {len(all_agents)}")

    # Provider summary
    providers = agent_monitor.get_provider_summary()
    print(f"\n🌐 Provider Summary:")
    for provider, count in providers.items():
        print(f"  - {provider}: {count} agents")

    # Model summary
    models = agent_monitor.get_model_summary()
    print(f"\n🧠 Model Summary:")
    for model, count in models.items():
        print(f"  - {model}: {count} agents")

    # Full status
    status = agent_monitor.get_agent_status_summary()
    print(f"\n⚙️ Autonomy Level: {status['autonomy_level']}")
    print(f"🛠️ Tools Enabled: {status['tools_enabled']}")

    # Test display name formatting
    for agent in all_agents:
        display = agent_monitor.format_agent_display_name(agent)
        print(f"\n📝 Display name: {display}")

    print("\n✅ agent_monitor tests PASSED\n")
    return True


def main():
    """Run all Phase 1 tests."""
    print("\n" + "=" * 60)
    print("PHASE 1 INTEGRATION TESTS")
    print("=" * 60 + "\n")

    results = []

    # Test costs_parser
    results.append(("costs_parser", test_costs_parser()))

    # Test budget_manager
    results.append(("budget_manager", test_budget_manager()))

    # Test agent_monitor
    results.append(("agent_monitor", test_agent_monitor()))

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name:20s} {status}")

    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 60 + "\n")

    if passed == total:
        print("🎉 All Phase 1 tests PASSED!")
        print("\nNext steps:")
        print("  1. Run: streamlit run app.py")
        print("  2. Navigate to Dashboard page")
        print("  3. Verify all Phase 1 components display correctly")
        return 0
    else:
        print("❌ Some tests FAILED")
        print("\nTroubleshooting:")
        print("  - Ensure sample data generated: python scripts/generate_sample_costs.py")
        print("  - Check config.toml: [cost] enabled = true")
        print("  - Verify file paths: ~/.zeroclaw/state/costs.jsonl")
        return 1


if __name__ == "__main__":
    sys.exit(main())
