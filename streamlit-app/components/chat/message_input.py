"""Message Input Component - Text input with send controls.

This component provides:
- Text area for message input
- Send button
- Character counter
- Model selector
- Temperature slider
"""

import streamlit as st
import time
from typing import Optional, Dict, Any


def render_message_input() -> Optional[str]:
    """Render message input controls and handle submission.

    Reads from session state:
        - chat_model: str (selected model)
        - chat_temperature: float (model temperature)

    Writes to session state:
        - chat_messages: List[Dict] (appends new message)
        - chat_model: str (if changed)
        - chat_temperature: float (if changed)

    Returns:
        Message text if sent, None otherwise
    """
    # Initialize session state if needed
    if 'chat_model' not in st.session_state:
        st.session_state.chat_model = "glm-5"

    if 'chat_temperature' not in st.session_state:
        st.session_state.chat_temperature = 0.7

    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []

    # Header
    st.markdown("### ⚙️ Message Controls")

    # Model selector
    model_options = [
        "glm-5",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku"
    ]

    selected_model = st.selectbox(
        "Model:",
        options=model_options,
        index=model_options.index(st.session_state.chat_model) if st.session_state.chat_model in model_options else 0,
        key="model_selector"
    )

    # Update model if changed
    if selected_model != st.session_state.chat_model:
        st.session_state.chat_model = selected_model

    # Temperature slider
    temperature = st.slider(
        "Temperature:",
        min_value=0.0,
        max_value=2.0,
        value=st.session_state.chat_temperature,
        step=0.1,
        key="temperature_slider",
        help="Lower = more focused, Higher = more creative"
    )

    # Update temperature if changed
    if temperature != st.session_state.chat_temperature:
        st.session_state.chat_temperature = temperature

    st.divider()

    # Message input area
    st.markdown("### ✍️ Your Message")

    message_text = st.text_area(
        "Type your message:",
        height=200,
        placeholder="Ask the agent anything...",
        key="message_input_area",
        label_visibility="collapsed"
    )

    # Character counter
    char_count = len(message_text)
    max_chars = 4000  # Reasonable limit

    # Color code the counter
    if char_count > max_chars:
        counter_color = "#FF5555"  # Red
    elif char_count > max_chars * 0.8:
        counter_color = "#F1FA8C"  # Yellow
    else:
        counter_color = "#87D7AF"  # Green

    st.markdown(f"""
    <div style="text-align: right; color: {counter_color}; font-size: 0.85em; margin-top: -8px; margin-bottom: 8px;">
        {char_count} / {max_chars} characters
    </div>
    """, unsafe_allow_html=True)

    # Send button
    col1, col2 = st.columns([3, 1])

    with col2:
        send_clicked = st.button(
            "Send 📨",
            type="primary",
            use_container_width=True,
            disabled=(char_count == 0 or char_count > max_chars)
        )

    with col1:
        if st.button("Clear", use_container_width=True):
            st.session_state.message_input_area = ""
            st.rerun()

    # Handle send
    if send_clicked and message_text.strip():
        # Create message object
        message = create_message(
            role="user",
            content=message_text.strip(),
            model=st.session_state.chat_model,
            temperature=st.session_state.chat_temperature
        )

        # Add to session state
        st.session_state.chat_messages.append(message)

        # Clear input
        st.session_state.message_input_area = ""

        # Return message for processing
        return message_text.strip()

    return None


def create_message(
    role: str,
    content: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    tokens: Optional[int] = None,
    cost: Optional[float] = None
) -> Dict[str, Any]:
    """Create a properly formatted message object.

    Args:
        role: "user" | "assistant" | "system"
        content: Message text
        model: Model name (optional)
        temperature: Model temperature (optional)
        tokens: Token count (optional)
        cost: Cost in USD (optional)

    Returns:
        Formatted message dict
    """
    import uuid

    message = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": time.time(),
        "metadata": {}
    }

    # Add metadata if provided
    if model:
        message["metadata"]["model"] = model

    if temperature is not None:
        message["metadata"]["temperature"] = temperature

    if tokens is not None:
        message["metadata"]["tokens"] = tokens

    if cost is not None:
        message["metadata"]["cost"] = cost

    return message


def add_assistant_message(
    content: str,
    model: Optional[str] = None,
    tokens: Optional[int] = None,
    cost: Optional[float] = None
) -> None:
    """Add an assistant message to the conversation.

    Helper function for adding agent responses.

    Args:
        content: Message text
        model: Model used
        tokens: Token count
        cost: Cost in USD
    """
    message = create_message(
        role="assistant",
        content=content,
        model=model,
        tokens=tokens,
        cost=cost
    )

    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []

    st.session_state.chat_messages.append(message)


def get_conversation_context() -> str:
    """Get the full conversation context as a formatted string.

    Returns:
        Formatted conversation string for agent context
    """
    messages = st.session_state.get('chat_messages', [])

    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        lines.append(f"{role.upper()}: {content}")

    return "\n\n".join(lines)
