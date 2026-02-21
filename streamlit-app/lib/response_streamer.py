"""ZeroClaw Response Streamer - Team 1: Real Agent Chat

Parses and streams CLI output in real-time.
Handles different output formats (text, tool calls, errors).
"""

import re
import json
from typing import Optional, Dict, Any, List, Iterator
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OutputType(Enum):
    """Types of output from ZeroClaw CLI."""
    TEXT = "text"           # Regular text response
    TOOL_CALL = "tool_call" # Tool execution
    ERROR = "error"         # Error message
    STATUS = "status"       # Status update
    THINKING = "thinking"   # Agent thinking indicator


@dataclass
class ParsedOutput:
    """Parsed output chunk from ZeroClaw."""
    type: OutputType
    content: str
    metadata: Dict[str, Any]


class ResponseStreamer:
    """Streams and parses ZeroClaw CLI output."""

    def __init__(self):
        """Initialize response streamer."""
        self.buffer = ""
        self.tool_call_pattern = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)
        self.thinking_pattern = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
        self.error_pattern = re.compile(r'Error: (.*?)(?:\n|$)')

    def parse_line(self, line: str) -> List[ParsedOutput]:
        """Parse a line of output from ZeroClaw.

        Args:
            line: Raw output line

        Returns:
            List of parsed output chunks (may be empty)
        """
        outputs = []

        # Add to buffer
        self.buffer += line

        # Try to parse tool calls
        tool_calls = self.tool_call_pattern.findall(self.buffer)
        if tool_calls:
            for call in tool_calls:
                try:
                    # Try to parse as JSON
                    tool_data = json.loads(call)
                    outputs.append(ParsedOutput(
                        type=OutputType.TOOL_CALL,
                        content=call,
                        metadata={"tool_data": tool_data}
                    ))
                except json.JSONDecodeError:
                    # Not JSON, treat as raw text
                    outputs.append(ParsedOutput(
                        type=OutputType.TOOL_CALL,
                        content=call,
                        metadata={}
                    ))
            # Remove parsed tool calls from buffer
            self.buffer = self.tool_call_pattern.sub('', self.buffer)

        # Try to parse thinking sections
        thinking = self.thinking_pattern.findall(self.buffer)
        if thinking:
            for thought in thinking:
                outputs.append(ParsedOutput(
                    type=OutputType.THINKING,
                    content=thought.strip(),
                    metadata={}
                ))
            # Remove parsed thinking from buffer
            self.buffer = self.thinking_pattern.sub('', self.buffer)

        # Try to parse errors
        errors = self.error_pattern.findall(self.buffer)
        if errors:
            for error in errors:
                outputs.append(ParsedOutput(
                    type=OutputType.ERROR,
                    content=error.strip(),
                    metadata={}
                ))
            # Remove parsed errors from buffer
            self.buffer = self.error_pattern.sub('', self.buffer)

        # If buffer has regular text, emit it
        if self.buffer.strip() and not outputs:
            # Check for status indicators
            if self.buffer.strip().startswith('['):
                outputs.append(ParsedOutput(
                    type=OutputType.STATUS,
                    content=self.buffer.strip(),
                    metadata={}
                ))
            else:
                outputs.append(ParsedOutput(
                    type=OutputType.TEXT,
                    content=self.buffer.strip(),
                    metadata={}
                ))
            self.buffer = ""

        return outputs

    def parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse a tool call from content.

        Args:
            content: Tool call content (XML or JSON)

        Returns:
            Dict with tool_name, parameters, or None if parse fails
        """
        # Try JSON first
        try:
            data = json.loads(content)
            if isinstance(data, dict) and 'name' in data:
                return {
                    "tool_name": data.get('name'),
                    "parameters": data.get('parameters', {}),
                    "raw": content
                }
        except json.JSONDecodeError:
            pass

        # Try XML-style parsing
        name_match = re.search(r'<name>(.*?)</name>', content)
        params_match = re.search(r'<parameters>(.*?)</parameters>', content, re.DOTALL)

        if name_match:
            tool_name = name_match.group(1).strip()
            parameters = {}

            if params_match:
                params_text = params_match.group(1).strip()
                # Try to parse as JSON
                try:
                    parameters = json.loads(params_text)
                except json.JSONDecodeError:
                    # Parse as key-value pairs
                    for line in params_text.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            parameters[key.strip()] = value.strip()

            return {
                "tool_name": tool_name,
                "parameters": parameters,
                "raw": content
            }

        return None

    def format_for_display(self, parsed: ParsedOutput) -> str:
        """Format parsed output for UI display.

        Args:
            parsed: Parsed output chunk

        Returns:
            Formatted string for display
        """
        if parsed.type == OutputType.TEXT:
            return parsed.content

        elif parsed.type == OutputType.TOOL_CALL:
            tool_data = parsed.metadata.get('tool_data')
            if tool_data:
                tool_name = tool_data.get('name', 'unknown')
                return f"[Tool: {tool_name}]"
            else:
                return "[Tool execution]"

        elif parsed.type == OutputType.THINKING:
            return f"💭 {parsed.content}"

        elif parsed.type == OutputType.ERROR:
            return f"❌ Error: {parsed.content}"

        elif parsed.type == OutputType.STATUS:
            return f"ℹ️ {parsed.content}"

        return parsed.content

    def stream_lines(self, lines: Iterator[str]) -> Iterator[ParsedOutput]:
        """Stream and parse lines of output.

        Args:
            lines: Iterator of raw output lines

        Yields:
            Parsed output chunks
        """
        for line in lines:
            parsed_chunks = self.parse_line(line)
            for chunk in parsed_chunks:
                yield chunk

    def reset(self):
        """Reset internal buffer."""
        self.buffer = ""


class ToolCallExtractor:
    """Extracts tool calls from agent output for approval workflow."""

    def __init__(self):
        """Initialize tool call extractor."""
        self.streamer = ResponseStreamer()

    def extract_tool_calls(self, output: str) -> List[Dict[str, Any]]:
        """Extract all tool calls from output.

        Args:
            output: Raw CLI output

        Returns:
            List of tool call dicts with tool_name, parameters
        """
        tool_calls = []

        # Parse all lines
        for line in output.split('\n'):
            parsed = self.streamer.parse_line(line)
            for chunk in parsed:
                if chunk.type == OutputType.TOOL_CALL:
                    tool_data = self.streamer.parse_tool_call(chunk.content)
                    if tool_data:
                        tool_calls.append(tool_data)

        return tool_calls

    def has_dangerous_tools(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """Check if any tool calls are dangerous.

        Args:
            tool_calls: List of tool call dicts

        Returns:
            True if any dangerous tools present
        """
        DANGEROUS_TOOLS = {
            'shell', 'file_write', 'file_delete',
            'browser', 'system', 'execute'
        }

        for call in tool_calls:
            tool_name = call.get('tool_name', '').lower()
            if any(dangerous in tool_name for dangerous in DANGEROUS_TOOLS):
                return True

        return False


# Singleton instances
response_streamer = ResponseStreamer()
tool_extractor = ToolCallExtractor()
