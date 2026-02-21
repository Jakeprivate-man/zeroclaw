"""Message History Component - Display conversation messages.

This component renders the conversation history with:
- User/assistant message differentiation
- Matrix Green themed styling
- Scrollable container
- Timestamps
- Metadata display (model, tokens, cost)
"""

import streamlit as st
from datetime import datetime
from typing import List, Dict, Any


def render_message_history() -> None:
    """Render the message history display.

    Reads from session state:
        - chat_messages: List[Dict] - Conversation messages

    Display styling:
        - User messages: Light green background
        - Assistant messages: Sea green background
        - Scrollable container
        - Timestamps and metadata
    """
    # Get messages from session state
    messages = st.session_state.get('chat_messages', [])

    # Container for message history
    st.markdown("### 💬 Conversation")

    if not messages:
        st.info("No messages yet. Start a conversation using the input panel.")
        return

    # Scrollable message container
    with st.container():
        for msg in messages:
            render_single_message(msg)


def render_single_message(message: Dict[str, Any]) -> None:
    """Render a single message with appropriate styling.

    Args:
        message: Message dict with keys:
            - role: "user" | "assistant" | "system"
            - content: str (message text)
            - timestamp: float (unix timestamp)
            - id: str (unique message ID)
            - metadata: dict (model, tokens, cost, etc.)
    """
    role = message.get('role', 'user')
    content = message.get('content', '')
    timestamp = message.get('timestamp', 0)
    metadata = message.get('metadata', {})

    # Format timestamp
    if timestamp:
        dt = datetime.fromtimestamp(timestamp)
        time_str = dt.strftime("%H:%M:%S")
    else:
        time_str = "Unknown"

    # Choose styling based on role
    if role == "user":
        bg_color = "rgba(95, 175, 135, 0.1)"  # Light green
        icon = "👤"
        role_label = "You"
    elif role == "assistant":
        bg_color = "rgba(135, 215, 175, 0.1)"  # Sea green
        icon = "🤖"
        role_label = "Agent"
    else:
        bg_color = "rgba(135, 215, 175, 0.05)"  # Very light
        icon = "ℹ️"
        role_label = "System"

    # Render message card
    st.markdown(f"""
    <div style="
        background-color: {bg_color};
        border: 1px solid #2d5f4f;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    ">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="color: #5FAF87; font-weight: bold;">
                {icon} {role_label}
            </span>
            <span style="color: #87D7AF; font-size: 0.85em;">
                {time_str}
            </span>
        </div>
        <div style="color: #87D7AF; line-height: 1.6; white-space: pre-wrap;">
{content}
        </div>
        {render_metadata_line(metadata)}
    </div>
    """, unsafe_allow_html=True)


def render_metadata_line(metadata: Dict[str, Any]) -> str:
    """Generate metadata HTML line if metadata exists.

    Args:
        metadata: Dict with optional keys (model, tokens, cost)

    Returns:
        HTML string for metadata line (or empty string)
    """
    if not metadata:
        return ""

    parts = []

    if 'model' in metadata:
        parts.append(f"Model: {metadata['model']}")

    if 'tokens' in metadata:
        parts.append(f"Tokens: {metadata['tokens']}")

    if 'cost' in metadata:
        cost = metadata['cost']
        parts.append(f"Cost: ${cost:.4f}")

    if parts:
        metadata_str = " | ".join(parts)
        return f"""
        <div style="
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(135, 215, 175, 0.2);
            color: #5FAF87;
            font-size: 0.8em;
        ">
            {metadata_str}
        </div>
        """

    return ""


def clear_message_history() -> None:
    """Clear all messages from the current conversation.

    Writes to session state:
        - chat_messages: Reset to empty list
    """
    st.session_state.chat_messages = []
    st.success("Conversation cleared!")
    st.rerun()


def export_conversation_text() -> str:
    """Export conversation as plain text.

    Returns:
        Plain text representation of conversation
    """
    messages = st.session_state.get('chat_messages', [])

    if not messages:
        return "No messages to export."

    lines = ["# ZeroClaw Conversation Export\n"]

    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', 0)

        if timestamp:
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Unknown time"

        lines.append(f"\n## [{time_str}] {role.upper()}\n")
        lines.append(content)
        lines.append("\n---\n")

    return "\n".join(lines)
