"""Process Monitor - Team 2: Live Dashboard Data

Monitors running ZeroClaw processes and system resources.
Provides real-time process information for dashboard display.
"""

import psutil
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    name: str
    status: str  # running, sleeping, zombie, etc.
    cpu_percent: float
    memory_mb: float
    cmdline: List[str]
    created: datetime
    is_zeroclaw: bool


class ProcessMonitor:
    """Monitors ZeroClaw and related processes."""

    def __init__(self):
        """Initialize process monitor."""
        self.known_processes: Dict[int, ProcessInfo] = {}

    def list_all_processes(self) -> List[ProcessInfo]:
        """List all ZeroClaw-related processes.

        Returns:
            List of ProcessInfo for ZeroClaw processes
        """
        zeroclaw_processes = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent',
                                            'memory_info', 'cmdline', 'create_time']):
                try:
                    info = proc.info
                    cmdline = info.get('cmdline', [])

                    # Check if this is a ZeroClaw process
                    is_zeroclaw = self._is_zeroclaw_process(cmdline, info.get('name', ''))

                    if is_zeroclaw:
                        memory_mb = info['memory_info'].rss / (1024 * 1024) if info.get('memory_info') else 0

                        process_info = ProcessInfo(
                            pid=info['pid'],
                            name=info.get('name', 'unknown'),
                            status=info.get('status', 'unknown'),
                            cpu_percent=info.get('cpu_percent', 0.0),
                            memory_mb=memory_mb,
                            cmdline=cmdline,
                            created=datetime.fromtimestamp(info.get('create_time', 0)),
                            is_zeroclaw=True
                        )

                        zeroclaw_processes.append(process_info)
                        self.known_processes[info['pid']] = process_info

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            logger.error(f"Error listing processes: {e}")

        return zeroclaw_processes

    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        """Get information about a specific process.

        Args:
            pid: Process ID

        Returns:
            ProcessInfo or None if not found
        """
        try:
            proc = psutil.Process(pid)
            info = proc.as_dict(['name', 'status', 'cpu_percent', 'memory_info',
                                'cmdline', 'create_time'])

            memory_mb = info['memory_info'].rss / (1024 * 1024) if info.get('memory_info') else 0

            return ProcessInfo(
                pid=pid,
                name=info.get('name', 'unknown'),
                status=info.get('status', 'unknown'),
                cpu_percent=info.get('cpu_percent', 0.0),
                memory_mb=memory_mb,
                cmdline=info.get('cmdline', []),
                created=datetime.fromtimestamp(info.get('create_time', 0)),
                is_zeroclaw=self._is_zeroclaw_process(info.get('cmdline', []), info.get('name', ''))
            )

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def is_process_running(self, pid: int) -> bool:
        """Check if a process is running.

        Args:
            pid: Process ID

        Returns:
            True if process exists and is running
        """
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process.

        Args:
            pid: Process ID
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            True if process was killed successfully
        """
        try:
            proc = psutil.Process(pid)

            if force:
                proc.kill()  # SIGKILL
            else:
                proc.terminate()  # SIGTERM

            # Wait for process to die
            proc.wait(timeout=5)
            return True

        except psutil.TimeoutExpired:
            # Try force kill
            try:
                proc.kill()
                proc.wait(timeout=2)
                return True
            except:
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system statistics.

        Returns:
            Dict with CPU, memory, disk usage
        """
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024 ** 3),
                'memory_total_gb': memory.total / (1024 ** 3),
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / (1024 ** 3),
                'disk_total_gb': disk.total / (1024 ** 3)
            }

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    def _is_zeroclaw_process(self, cmdline: List[str], name: str) -> bool:
        """Check if process is related to ZeroClaw.

        Args:
            cmdline: Command line arguments
            name: Process name

        Returns:
            True if this is a ZeroClaw process
        """
        if not cmdline:
            return 'zeroclaw' in name.lower()

        cmdline_str = ' '.join(cmdline).lower()

        # Check for zeroclaw binary or related components
        zeroclaw_indicators = [
            'zeroclaw',
            'target/release/zeroclaw',
            'target/debug/zeroclaw',
            '.zeroclaw',
            'zeroclaw-gateway',
            'zeroclaw-streamlit'
        ]

        return any(indicator in cmdline_str for indicator in zeroclaw_indicators)


# Singleton instance
process_monitor = ProcessMonitor()
