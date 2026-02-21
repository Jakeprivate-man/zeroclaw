"""ZeroClaw CLI Executor - Team 1: Real Agent Chat

This module manages subprocess execution of the ZeroClaw CLI binary.
Handles process lifecycle, output streaming, and error management.
"""

import subprocess
import os
import threading
import queue
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running ZeroClaw process."""
    pid: int
    started: datetime
    command: str
    status: str  # running, stopped, error


class ZeroClawCLIExecutor:
    """Manages execution of ZeroClaw CLI commands."""

    def __init__(self, binary_path: str = "/Users/jakeprivate/zeroclaw/target/release/zeroclaw"):
        """Initialize CLI executor.

        Args:
            binary_path: Path to zeroclaw binary
        """
        if not os.path.exists(binary_path):
            raise FileNotFoundError(f"ZeroClaw binary not found at {binary_path}")

        self.binary_path = binary_path
        self.process: Optional[subprocess.Popen] = None
        self.output_queue: queue.Queue = queue.Queue()
        self.error_queue: queue.Queue = queue.Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self.is_streaming = False

    def start_chat(self, message: str, model: str = "anthropic/claude-sonnet-4",
                   stream_callback: Optional[Callable[[str], None]] = None) -> ProcessInfo:
        """Start a chat session with ZeroClaw CLI.

        Args:
            message: Initial message to send
            model: Model to use (default: claude-sonnet-4)
            stream_callback: Optional callback for streaming output

        Returns:
            ProcessInfo with process details

        Raises:
            RuntimeError: If process fails to start
        """
        if self.process and self.process.poll() is None:
            raise RuntimeError("Chat process already running")

        # Build command
        cmd = [
            self.binary_path,
            "chat",
            message,
            "--model", model
        ]

        try:
            # Start process with output piping
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Start output reader thread
            self.is_streaming = True
            self.reader_thread = threading.Thread(
                target=self._read_output,
                args=(stream_callback,),
                daemon=True
            )
            self.reader_thread.start()

            logger.info(f"Started ZeroClaw chat process: PID {self.process.pid}")

            return ProcessInfo(
                pid=self.process.pid,
                started=datetime.now(),
                command=" ".join(cmd),
                status="running"
            )

        except Exception as e:
            logger.error(f"Failed to start chat process: {e}")
            raise RuntimeError(f"Failed to start ZeroClaw: {e}")

    def send_message(self, message: str) -> None:
        """Send a message to the running chat process.

        Args:
            message: Message to send

        Raises:
            RuntimeError: If no process is running
        """
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("No active chat process")

        try:
            self.process.stdin.write(message + "\n")
            self.process.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise RuntimeError(f"Failed to send message: {e}")

    def stop(self) -> None:
        """Stop the running chat process."""
        self.is_streaming = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

            logger.info(f"Stopped ZeroClaw process PID {self.process.pid}")
            self.process = None

        if self.reader_thread:
            self.reader_thread.join(timeout=2)
            self.reader_thread = None

    def get_output(self) -> Optional[str]:
        """Get next output line from queue.

        Returns:
            Output line or None if queue empty
        """
        try:
            return self.output_queue.get_nowait()
        except queue.Empty:
            return None

    def get_error(self) -> Optional[str]:
        """Get next error line from queue.

        Returns:
            Error line or None if queue empty
        """
        try:
            return self.error_queue.get_nowait()
        except queue.Empty:
            return None

    def get_all_output(self) -> str:
        """Get all accumulated output.

        Returns:
            All output lines joined
        """
        lines = []
        while True:
            line = self.get_output()
            if line is None:
                break
            lines.append(line)
        return "".join(lines)

    def is_running(self) -> bool:
        """Check if process is running.

        Returns:
            True if process is active
        """
        return self.process is not None and self.process.poll() is None

    def get_process_info(self) -> Optional[ProcessInfo]:
        """Get information about the current process.

        Returns:
            ProcessInfo or None if no process
        """
        if not self.process:
            return None

        status = "running" if self.process.poll() is None else "stopped"

        return ProcessInfo(
            pid=self.process.pid,
            started=datetime.now(),  # TODO: Track actual start time
            command=self.binary_path,
            status=status
        )

    def _read_output(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Read output from process in background thread.

        Args:
            callback: Optional function to call with each output line
        """
        if not self.process:
            return

        try:
            while self.is_streaming and self.process:
                # Read stdout
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
                    if callback:
                        callback(line)

                # Read stderr
                if self.process.stderr:
                    try:
                        # Non-blocking read would be better, but this is simple
                        err_line = self.process.stderr.readline()
                        if err_line:
                            self.error_queue.put(err_line)
                            logger.warning(f"ZeroClaw stderr: {err_line.strip()}")
                    except:
                        pass

                # Check if process ended
                if self.process.poll() is not None:
                    break

        except Exception as e:
            logger.error(f"Error reading output: {e}")
            self.error_queue.put(f"Error reading output: {e}")

    def execute_oneshot(self, message: str, model: str = "anthropic/claude-sonnet-4",
                        timeout: int = 120) -> Dict[str, Any]:
        """Execute a single message and wait for response.

        Args:
            message: Message to send
            model: Model to use
            timeout: Timeout in seconds

        Returns:
            Dict with 'output', 'error', and 'success' keys
        """
        cmd = [
            self.binary_path,
            "chat",
            message,
            "--model", model
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "output": result.stdout,
                "error": result.stderr,
                "success": result.returncode == 0,
                "returncode": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "output": "",
                "error": f"Command timed out after {timeout} seconds",
                "success": False,
                "returncode": -1
            }
        except Exception as e:
            return {
                "output": "",
                "error": str(e),
                "success": False,
                "returncode": -1
            }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
