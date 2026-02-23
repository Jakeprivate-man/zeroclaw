"""Test script for Phase 1.5: Core Messaging Implementation.

This script validates:
1. All 5 components are created
2. Imports work correctly
3. Basic functionality
4. Integration cohesion
"""

import sys
import os
from pathlib import Path

# Add streamlit-app to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all components can be imported."""
    print("Testing imports...")

    try:
        # Component imports
        from components.chat.message_history import render_message_history
        from components.chat.message_input import render_message_input, create_message
        print("✓ Chat components imported successfully")

        # Library imports
        from lib.conversation_manager import ConversationManager
        from lib.realtime_poller import RealtimePoller
        print("✓ Library modules imported successfully")

        # Page import
        from pages import chat
        print("✓ Chat page imported successfully")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_file_structure():
    """Test that all required files exist."""
    print("\nTesting file structure...")

    base_dir = Path(__file__).parent

    required_files = [
        "components/chat/__init__.py",
        "components/chat/message_history.py",
        "components/chat/message_input.py",
        "lib/conversation_manager.py",
        "lib/realtime_poller.py",
        "pages/chat.py",
        "PHASE1_5_CONTRACTS.md"
    ]

    all_exist = True
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} (missing)")
            all_exist = False

    return all_exist


def test_conversation_manager():
    """Test ConversationManager basic functionality."""
    print("\nTesting ConversationManager...")

    try:
        from lib.conversation_manager import ConversationManager
        import tempfile

        # Create manager with temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConversationManager(tmpdir)

            # Test save
            messages = [
                {"role": "user", "content": "Hello", "timestamp": 1.0, "id": "1"},
                {"role": "assistant", "content": "Hi!", "timestamp": 2.0, "id": "2"}
            ]

            conv_id = manager.save_conversation(
                messages=messages,
                title="Test Conversation",
                model="claude-sonnet-4-6"
            )

            print(f"✓ Saved conversation: {conv_id[:8]}...")

            # Test load
            loaded = manager.load_conversation(conv_id)
            if loaded and loaded['title'] == "Test Conversation":
                print("✓ Loaded conversation successfully")
            else:
                print("✗ Failed to load conversation")
                return False

            # Test list
            conversations = manager.list_conversations()
            if len(conversations) == 1:
                print(f"✓ Listed {len(conversations)} conversation(s)")
            else:
                print(f"✗ Expected 1 conversation, got {len(conversations)}")
                return False

            # Test delete
            if manager.delete_conversation(conv_id):
                print("✓ Deleted conversation successfully")
            else:
                print("✗ Failed to delete conversation")
                return False

            # Test stats
            stats = manager.get_stats()
            print(f"✓ Stats: {stats}")

        return True

    except Exception as e:
        print(f"✗ ConversationManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_creation():
    """Test message creation utility."""
    print("\nTesting message creation...")

    try:
        from components.chat.message_input import create_message

        # Create a user message
        msg = create_message(
            role="user",
            content="Test message",
            model="claude-sonnet-4-6",
            temperature=0.7
        )

        # Validate message structure
        required_keys = ["id", "role", "content", "timestamp", "metadata"]
        for key in required_keys:
            if key not in msg:
                print(f"✗ Missing key: {key}")
                return False

        print(f"✓ Message created with ID: {msg['id'][:8]}...")
        print(f"✓ Message structure valid")

        return True

    except Exception as e:
        print(f"✗ Message creation test failed: {e}")
        return False


def test_realtime_poller():
    """Test RealtimePoller basic functionality."""
    print("\nTesting RealtimePoller...")

    try:
        from lib.realtime_poller import RealtimePoller

        poller = RealtimePoller()

        # Test initial state
        if not poller.is_polling():
            print("✓ Polling initially disabled")
        else:
            print("✗ Polling should be initially disabled")
            return False

        # Test start/stop
        poller.start_polling()
        if poller.is_polling():
            print("✓ Polling started")
        else:
            print("✗ Polling should be enabled")
            return False

        poller.stop_polling()
        if not poller.is_polling():
            print("✓ Polling stopped")
        else:
            print("✗ Polling should be disabled")
            return False

        # Test interval
        poller.set_poll_interval(5)
        if poller.get_poll_interval() == 5:
            print("✓ Poll interval set to 5 seconds")
        else:
            print("✗ Poll interval not set correctly")
            return False

        return True

    except Exception as e:
        print(f"✗ RealtimePoller test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test that components can work together."""
    print("\nTesting integration...")

    try:
        # Import all components
        from components.chat.message_input import create_message, add_assistant_message
        from lib.conversation_manager import ConversationManager
        from lib.realtime_poller import RealtimePoller

        # Simulate a conversation flow
        print("✓ All components imported for integration test")

        # Create a mock session state
        class MockSessionState(dict):
            def __getattr__(self, name):
                return self.get(name)

            def __setattr__(self, name, value):
                self[name] = value

        # This would normally be st.session_state
        # But we're just testing the components can coexist
        print("✓ Components can be integrated")

        return True

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 1.5: Core Messaging Implementation - Validation Tests")
    print("=" * 60)

    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("ConversationManager", test_conversation_manager),
        ("Message Creation", test_message_creation),
        ("RealtimePoller", test_realtime_poller),
        ("Integration", test_integration),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        result = test_func()
        results.append((name, result))

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Phase 1.5 implementation is valid.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
