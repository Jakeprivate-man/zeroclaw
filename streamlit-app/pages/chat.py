"""Chat Page - Main chat interface for ZeroClaw agent interaction.

This page integrates all chat components:
- Message history display
- Message input with controls
- Conversation management
- Realtime polling
"""

import streamlit as st
from components.chat.message_history import (
    render_message_history,
    clear_message_history,
    export_conversation_text
)
from components.chat.message_input import (
    render_message_input,
    add_assistant_message,
    create_message
)
from lib.conversation_manager import ConversationManager
from lib.cli_executor import ZeroClawCLIExecutor
from lib.realtime_poller import (
    RealtimePoller,
    auto_poll_in_background,
    start_waiting_for_response
)


def render() -> None:
    """Render the chat page.

    Layout:
        - Header with title and controls
        - Two-column layout:
            - Left (60%): Message history
            - Right (40%): Message input and controls
        - Sidebar: Conversation management and polling controls
    """
    # Auto-poll for updates in background
    auto_poll_in_background()

    # Page header
    st.title("💬 Chat Interface")
    st.markdown("Real-time conversation with ZeroClaw agent")

    # Initialize components
    conv_manager = ConversationManager()
    poller = RealtimePoller()

    # Render sidebar controls
    render_sidebar_controls(conv_manager, poller)

    # Main layout: Two columns
    col1, col2 = st.columns([6, 4])

    # Left column: Message history
    with col1:
        render_message_history()

    # Right column: Message input
    with col2:
        message = render_message_input()

        # Handle new message
        if message:
            handle_message_sent(message, poller)

    # Footer actions
    st.divider()
    render_footer_actions(conv_manager)


def render_sidebar_controls(
    conv_manager: ConversationManager,
    poller: RealtimePoller
) -> None:
    """Render sidebar controls for conversation management and polling.

    Args:
        conv_manager: Conversation manager instance
        poller: Realtime poller instance
    """
    with st.sidebar:
        st.markdown("## 🛠️ Chat Controls")

        # Polling controls
        poller.render_poll_controls()

        st.divider()

        # Conversation management
        st.markdown("### 💾 Conversations")

        # Save current conversation
        if st.button("💾 Save Conversation", use_container_width=True):
            save_current_conversation(conv_manager)

        # Load conversation
        render_conversation_loader(conv_manager)

        # New conversation
        if st.button("🆕 New Conversation", use_container_width=True):
            start_new_conversation()

        st.divider()

        # Statistics
        render_conversation_stats(conv_manager)


def save_current_conversation(conv_manager: ConversationManager) -> None:
    """Save the current conversation to disk.

    Args:
        conv_manager: Conversation manager instance
    """
    messages = st.session_state.get('chat_messages', [])

    if not messages:
        st.warning("No messages to save!")
        return

    # Prompt for title
    title = st.session_state.get('conversation_title', None)

    if not title:
        st.session_state.conversation_title_prompt = True
        st.rerun()
        return

    # Save conversation
    try:
        model = st.session_state.get('chat_model', 'unknown')
        conv_id = conv_manager.save_conversation(
            messages=messages,
            title=title,
            model=model
        )

        st.session_state.current_conversation_id = conv_id
        st.success(f"Conversation saved! ID: {conv_id[:8]}...")

        # Clear title prompt flag
        st.session_state.conversation_title_prompt = False

    except Exception as e:
        st.error(f"Error saving conversation: {e}")


def render_conversation_loader(conv_manager: ConversationManager) -> None:
    """Render conversation loader dropdown.

    Args:
        conv_manager: Conversation manager instance
    """
    conversations = conv_manager.list_conversations(limit=20)

    if not conversations:
        st.info("No saved conversations yet.")
        return

    # Create options for selectbox
    options = {
        f"{conv['title'][:30]}... ({conv['message_count']} msgs)": conv['id']
        for conv in conversations
    }

    selected_label = st.selectbox(
        "Load conversation:",
        options=["Select..."] + list(options.keys()),
        key="conversation_selector"
    )

    if selected_label != "Select..." and selected_label in options:
        conv_id = options[selected_label]

        if st.button("📂 Load", key="load_button"):
            load_conversation(conv_manager, conv_id)


def load_conversation(conv_manager: ConversationManager, conv_id: str) -> None:
    """Load a conversation into the current session.

    Args:
        conv_manager: Conversation manager instance
        conv_id: Conversation ID to load
    """
    try:
        conversation = conv_manager.load_conversation(conv_id)

        if not conversation:
            st.error("Conversation not found!")
            return

        # Load messages into session state
        st.session_state.chat_messages = conversation.get('messages', [])
        st.session_state.current_conversation_id = conv_id
        st.session_state.chat_model = conversation.get('model', 'claude-sonnet-4-6')

        st.success(f"Loaded: {conversation.get('title', 'Untitled')}")
        st.rerun()

    except Exception as e:
        st.error(f"Error loading conversation: {e}")


def start_new_conversation() -> None:
    """Start a new conversation (clear current messages)."""
    st.session_state.chat_messages = []
    st.session_state.current_conversation_id = None
    st.success("Started new conversation!")
    st.rerun()


def render_conversation_stats(conv_manager: ConversationManager) -> None:
    """Render conversation statistics.

    Args:
        conv_manager: Conversation manager instance
    """
    stats = conv_manager.get_stats()

    st.markdown("### 📊 Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Conversations",
            stats.get('total_conversations', 0)
        )

    with col2:
        st.metric(
            "Messages",
            stats.get('total_messages', 0)
        )

    # Current conversation info
    messages = st.session_state.get('chat_messages', [])
    if messages:
        st.caption(f"Current: {len(messages)} messages")


def handle_message_sent(message: str, poller: RealtimePoller) -> None:
    """Handle a sent message by executing the ZeroClaw CLI.

    Args:
        message: Message text
        poller: Realtime poller instance
    """
    model = st.session_state.get('chat_model', 'claude-sonnet-4-6')

    with st.spinner("Running agent..."):
        try:
            executor = ZeroClawCLIExecutor()
            result = executor.execute_oneshot(message=message, model=model)

            if result['success']:
                output = result['output'].strip() or "(no output)"
                add_assistant_message(content=output, model=model)
            else:
                error_text = result.get('error', 'Unknown error').strip()
                add_assistant_message(
                    content=f"Agent error: {error_text}",
                    model=model
                )
        except FileNotFoundError:
            add_assistant_message(
                content="ZeroClaw binary not found. Build it with: cargo build --release",
                model=model
            )
        except Exception as e:
            add_assistant_message(
                content=f"Execution error: {e}",
                model=model
            )

    # Rerun to show new message
    st.rerun()


def render_footer_actions(conv_manager: ConversationManager) -> None:
    """Render footer action buttons.

    Args:
        conv_manager: Conversation manager instance
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🗑️ Clear History", use_container_width=True):
            if st.session_state.get('chat_messages'):
                clear_message_history()

    with col2:
        if st.button("📥 Export (Text)", use_container_width=True):
            export_text = export_conversation_text()
            st.download_button(
                label="Download",
                data=export_text,
                file_name="conversation.txt",
                mime="text/plain",
                use_container_width=True
            )

    with col3:
        if st.button("📥 Export (JSON)", use_container_width=True):
            conv_id = st.session_state.get('current_conversation_id')
            if conv_id:
                export_json = conv_manager.export_conversation(conv_id, format="json")
                if export_json:
                    st.download_button(
                        label="Download",
                        data=export_json,
                        file_name="conversation.json",
                        mime="application/json",
                        use_container_width=True
                    )

    with col4:
        messages = st.session_state.get('chat_messages', [])
        if messages:
            st.metric("Messages", len(messages))


# Handle conversation title input prompt
if st.session_state.get('conversation_title_prompt'):
    with st.sidebar:
        st.markdown("### 💬 Conversation Title")
        title = st.text_input(
            "Enter a title:",
            key="title_input",
            placeholder="My Conversation"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save", use_container_width=True):
                if title:
                    st.session_state.conversation_title = title
                    st.rerun()

        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.conversation_title_prompt = False
                st.rerun()
