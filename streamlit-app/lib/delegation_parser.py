"""Delegation Event Parser - Parse delegation tree from logs/events.

Reads DelegationStart and DelegationEnd events from the observer system
to build a tree visualization of nested agent delegations.
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DelegationNode:
    """A node in the delegation tree."""
    agent_name: str
    provider: str
    model: str
    depth: int
    agentic: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    run_id: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    children: List['DelegationNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

    @property
    def is_complete(self) -> bool:
        """Check if delegation has completed."""
        return self.end_time is not None

    @property
    def status(self) -> str:
        """Get status string for display."""
        if not self.is_complete:
            return "🟡 Running"
        elif self.success:
            return "✅ Success"
        else:
            return "❌ Failed"


@dataclass
class RunSummary:
    """Summary of a single ZeroClaw process invocation."""
    run_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_delegations: int = 0

    @property
    def label(self) -> str:
        """Human-readable label for UI display."""
        ts = self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else "unknown"
        short_id = self.run_id[:8]
        return f"{ts} [{short_id}] ({self.total_delegations} delegations)"


class DelegationParser:
    """Parse delegation events from ZeroClaw logs."""

    def __init__(self, log_file: str = "~/.zeroclaw/state/delegation.jsonl"):
        """Initialize delegation parser.

        Args:
            log_file: Path to delegation events log file
        """
        self.log_file = os.path.expanduser(log_file)

    def _read_events(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read events from the JSONL log file, optionally filtering by run_id."""
        if not os.path.exists(self.log_file):
            return []
        events = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if run_id is None or event.get('run_id') == run_id:
                            events.append(event)
        except Exception as e:
            logger.error(f"Error reading delegation log: {e}")
        return events

    def list_runs(self) -> List['RunSummary']:
        """Return one RunSummary per distinct run_id, sorted newest-first."""
        if not os.path.exists(self.log_file):
            return []

        runs: Dict[str, RunSummary] = {}
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    rid = event.get('run_id')
                    if not rid:
                        continue
                    ts = self._parse_timestamp(event.get('timestamp'))
                    if rid not in runs:
                        runs[rid] = RunSummary(run_id=rid, start_time=ts)
                    summary = runs[rid]
                    if ts and (summary.start_time is None or ts < summary.start_time):
                        summary.start_time = ts
                    if ts and (summary.end_time is None or ts > summary.end_time):
                        summary.end_time = ts
                    if event.get('event_type') == 'DelegationStart':
                        summary.total_delegations += 1
        except Exception as e:
            logger.error(f"Error listing runs: {e}")

        return sorted(runs.values(), key=lambda r: r.start_time or datetime.min, reverse=True)

    def parse_delegation_tree(self, run_id: Optional[str] = None) -> List[DelegationNode]:
        """Parse delegation events into a tree structure.

        Args:
            run_id: Optional run ID to filter by (UUID from DelegationEventObserver)

        Returns:
            List of root delegation nodes (trees can have multiple roots)
        """
        if not os.path.exists(self.log_file):
            logger.warning(f"Delegation log file not found: {self.log_file}")
            return []

        events = self._read_events(run_id)
        if not events:
            return []

        # Build tree from events
        return self._build_tree(events)

    def _build_tree(self, events: List[Dict[str, Any]]) -> List[DelegationNode]:
        """Build delegation tree from events.

        Algorithm:
        1. Group events by agent_name and depth
        2. Match DelegationStart with DelegationEnd
        3. Build parent-child relationships based on depth

        Args:
            events: List of delegation events

        Returns:
            List of root nodes
        """
        # Separate start and end events
        starts = [e for e in events if e.get('event_type') == 'DelegationStart']
        ends = [e for e in events if e.get('event_type') == 'DelegationEnd']

        # Create nodes from start events
        nodes_by_key = {}
        for start in starts:
            key = (start['agent_name'], start['depth'], start.get('timestamp'))
            node = DelegationNode(
                agent_name=start['agent_name'],
                provider=start['provider'],
                model=start['model'],
                depth=start['depth'],
                agentic=start.get('agentic', True),
                start_time=self._parse_timestamp(start.get('timestamp')),
                run_id=start.get('run_id'),
            )
            nodes_by_key[key] = node

        # Match with end events
        for end in ends:
            # Find matching start event
            matching_keys = [
                k for k in nodes_by_key.keys()
                if k[0] == end['agent_name'] and k[1] == end['depth']
            ]
            if matching_keys:
                # Take the most recent matching start
                key = max(matching_keys, key=lambda k: k[2] if k[2] else '')
                node = nodes_by_key[key]
                node.end_time = self._parse_timestamp(end.get('timestamp'))
                node.duration_ms = end.get('duration_ms')
                node.success = end.get('success')
                node.error_message = end.get('error_message')
                node.tokens_used = end.get('tokens_used')
                node.cost_usd = end.get('cost_usd')

        # Build parent-child relationships
        all_nodes = list(nodes_by_key.values())
        roots = []

        for node in all_nodes:
            if node.depth == 0:
                roots.append(node)
            else:
                # Find parent (depth-1)
                parents = [n for n in all_nodes if n.depth == node.depth - 1]
                if parents:
                    # Assign to most recent parent before this node's start time
                    parent = None
                    for p in sorted(parents, key=lambda n: n.start_time or datetime.min, reverse=True):
                        if not node.start_time or not p.start_time or p.start_time < node.start_time:
                            parent = p
                            break
                    if parent:
                        parent.children.append(node)
                    else:
                        # No valid parent found, treat as root
                        roots.append(node)
                else:
                    # No parent at depth-1, treat as root
                    roots.append(node)

        return roots

    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except:
                return None
        return None

    def get_mock_tree(self) -> List[DelegationNode]:
        """Generate mock delegation tree for demo purposes.

        Returns a sample tree showing:
        - Root agent delegating to research agent
        - Research agent delegating to multiple analyzers
        """
        root = DelegationNode(
            agent_name="main",
            provider="anthropic",
            model="claude-sonnet-4",
            depth=0,
            agentic=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=5234,
            success=True,
            tokens_used=3800,
            cost_usd=0.0114,
        )

        research = DelegationNode(
            agent_name="research",
            provider="anthropic",
            model="claude-sonnet-4",
            depth=1,
            agentic=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=4512,
            success=True,
            tokens_used=2400,
            cost_usd=0.0072,
        )
        root.children.append(research)

        analyzer1 = DelegationNode(
            agent_name="codebase_analyzer",
            provider="anthropic",
            model="claude-haiku-4",
            depth=2,
            agentic=False,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=1234,
            success=True,
            tokens_used=800,
            cost_usd=0.0008,
        )
        research.children.append(analyzer1)

        analyzer2 = DelegationNode(
            agent_name="doc_analyzer",
            provider="anthropic",
            model="claude-haiku-4",
            depth=2,
            agentic=False,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=987,
            success=True,
            tokens_used=600,
            cost_usd=0.0006,
        )
        research.children.append(analyzer2)

        return [root]
