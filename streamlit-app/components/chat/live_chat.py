"""Live Chat Component - Team 1: Real Agent Chat

Real chat interface that executes ZeroClaw CLI and streams responses.
Replaces simulated responses with actual agent execution.
"""

import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from lib.cli_executor import ZeroClawCLIExecutor
from lib.response_streamer import response_streamer, OutputType

logger = logging.getLogger(__name__)


class LiveChat:
    """Live chat interface with real ZeroClaw execution."""

    def __init__(self):
        """Initialize live chat."""
        self.executor = ZeroClawCLIExecutor()

    def render(self):
        """Render the live chat interface."""
        st.subheader("Live Chat with ZeroClaw")

        # Initialize session state
        if 'chat_messages' not in st.session_state:
            st.session_state.chat_messages = []
        if 'chat_process_running' not in st.session_state:
            st.session_state.chat_process_running = False

        # Display chat history
        self._render_chat_history()

        # Input area
        self._render_input_area()

        # Status bar
        self._render_status_bar()

    def _render_chat_history(self):
        """Render chat message history."""
        for message in st.session_state.chat_messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            timestamp = message.get('timestamp', '')

            if role == 'user':
                with st.chat_message("user"):
                    st.write(content)
                    if timestamp:
                        st.caption(f"🕒 {timestamp}")
            elif role == 'assistant':
                with st.chat_message("assistant"):
                    st.write(content)
                    if timestamp:
                        st.caption(f"🕒 {timestamp}")
            elif role == 'system':
                with st.chat_message("system"):
                    st.info(content)

    def _render_input_area(self):
        """Render message input area."""
        col1, col2, col3 = st.columns([6, 1, 1])

        with col1:
            user_input = st.text_area(
                "Your message:",
                key="chat_input",
                height=100,
                placeholder="Type your message here..."
            )

        with col2:
            send_clicked = st.button("Send", type="primary", use_container_width=True)

        with col3:
            clear_clicked = st.button("Clear", use_container_width=True)

        # Handle send
        if send_clicked and user_input.strip():
            self._send_message(user_input.strip())

        # Handle clear
        if clear_clicked:
            st.session_state.chat_messages = []
            st.rerun()

    def _send_message(self, message: str):
        """Send a message to ZeroClaw.

        Args:
            message: User message to send
        """
        # Add user message to history
        st.session_state.chat_messages.append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })

        # Execute ZeroClaw
        try:
            with st.spinner("Thinking..."):
                response = self._execute_chat(message)

            # Add assistant response
            st.session_state.chat_messages.append({
                'role': 'assistant',
                'content': response,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })

        except Exception as e:
            logger.error(f"Chat error: {e}")
            st.session_state.chat_messages.append({
                'role': 'system',
                'content': f"Error: {str(e)}",
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })

        # Clear input
        st.session_state.chat_input = ""
        st.rerun()

    def _execute_chat(self, message: str) -> str:
        """Execute ZeroClaw CLI with message.

        Args:
            message: User message

        Returns:
            Agent response
        """
        # Get model from settings (default to claude-sonnet-4)
        model = st.session_state.get('selected_model', 'anthropic/claude-sonnet-4')

        # Execute one-shot command
        result = self.executor.execute_oneshot(
            message=message,
            model=model,
            timeout=120
        )

        if result['success']:
            # Parse output
            output = result['output']

            # Stream parse the output
            response_parts = []
            for line in output.split('\n'):
                parsed_chunks = response_streamer.parse_line(line)
                for chunk in parsed_chunks:
                    if chunk.type == OutputType.TEXT:
                        response_parts.append(chunk.content)
                    elif chunk.type == OutputType.THINKING:
                        response_parts.append(f"💭 {chunk.content}")
                    elif chunk.type == OutputType.TOOL_CALL:
                        response_parts.append(f"🔧 [Tool executed]")

            return "\n".join(response_parts) if response_parts else output
        else:
            raise RuntimeError(result['error'] or "Command failed")

    def _render_status_bar(self):
        """Render status information."""
        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Messages", len(st.session_state.chat_messages))

        with col2:
            model = st.session_state.get('selected_model', 'anthropic/claude-sonnet-4')
            st.metric("Model", model.split('/')[-1])

        with col3:
            if self.executor.is_running():
                st.success("🟢 Active")
            else:
                st.info("⚪ Ready")


def render_live_chat():
    """Render the live chat component (convenience function)."""
    chat = LiveChat()
    chat.render()


def render_streaming_chat():
    """Render streaming chat with real-time output."""
    st.subheader("Streaming Chat")

    # Initialize session state
    if 'streaming_messages' not in st.session_state:
        st.session_state.streaming_messages = []
    if 'streaming_executor' not in st.session_state:
        st.session_state.streaming_executor = None

    # Display messages
    for msg in st.session_state.streaming_messages:
        with st.chat_message(msg['role']):
            st.write(msg['content'])

    # Input
    if prompt := st.chat_input("Message"):
        # Add user message
        st.session_state.streaming_messages.append({
            'role': 'user',
            'content': prompt
        })

        # Create executor if needed
        if st.session_state.streaming_executor is None:
            st.session_state.streaming_executor = ZeroClawCLIExecutor()

        # Execute with streaming
        executor = st.session_state.streaming_executor
        model = st.session_state.get('selected_model', 'anthropic/claude-sonnet-4')

        # Create container for streaming output
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            def stream_callback(line: str):
                """Callback for streaming output."""
                nonlocal full_response
                parsed = response_streamer.parse_line(line)
                for chunk in parsed:
                    display_text = response_streamer.format_for_display(chunk)
                    full_response += display_text + "\n"
                    message_placeholder.markdown(full_response + "▌")

            try:
                # Start streaming chat
                executor.start_chat(prompt, model, stream_callback)

                # Wait for completion (simplified - real impl would stream)
                import time
                while executor.is_running():
                    time.sleep(0.1)
                    # Get accumulated output
                    output = executor.get_all_output()
                    if output:
                        message_placeholder.markdown(output)

                # Get final output
                final_output = executor.get_all_output()
                message_placeholder.markdown(final_output or full_response)

                # Add to messages
                st.session_state.streaming_messages.append({
                    'role': 'assistant',
                    'content': final_output or full_response
                })

            except Exception as e:
                st.error(f"Error: {e}")

            finally:
                executor.stop()

        st.rerun()
