///! Delegation Event Logger - Writes delegation events to JSONL for UI consumption.
///!
///! This observer writes `DelegationStart` and `DelegationEnd` events to
///! `~/.zeroclaw/state/delegation.jsonl` in append-only JSONL format,
///! enabling the Streamlit UI to visualize delegation trees.
///!
///! Each observer instance is assigned a unique `run_id` (UUID) at creation time,
///! which is written into every JSONL event to allow the UI to filter by run.

use super::traits::{Observer, ObserverEvent, ObserverMetric};
use std::any::Any;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

/// Observer that logs delegation events to JSONL file.
///
/// Only writes `DelegationStart` and `DelegationEnd` events, ignoring
/// all other event types. Events are written in append-only mode with
/// ISO8601 timestamps and a `run_id` for consumption by the Streamlit
/// delegation parser.
///
/// The `run_id` is a UUID generated at observer creation time. All events
/// from a single process invocation share the same `run_id`, allowing the
/// UI to display or filter delegations by run.
///
/// On construction the log file is pruned: if the number of distinct
/// `run_id` values exceeds `max_runs`, the oldest runs are removed so the
/// file never grows unboundedly. Set `max_runs = 0` to disable pruning.
pub struct DelegationEventObserver {
    log_file: PathBuf,
    run_id: String,
    max_runs: usize,
}

impl DelegationEventObserver {
    /// Create a new delegation event logger with the default run limit (100 runs).
    ///
    /// On construction, runs older than the 100 most-recent are pruned from
    /// the log file. Use [`with_max_runs`](Self::with_max_runs) to override
    /// the limit, or set it to `0` to disable pruning entirely.
    ///
    /// # Arguments
    ///
    /// * `log_file` - Path to JSONL log file (created if it doesn't exist)
    pub fn new(log_file: PathBuf) -> Self {
        Self::with_max_runs(log_file, 100)
    }

    /// Create a new delegation event logger with a custom run retention limit.
    ///
    /// Generates a unique `run_id` (UUID v4) for this observer instance.
    /// All delegation events written by this observer will include the same `run_id`.
    ///
    /// If the log file already contains more than `max_runs` distinct run IDs,
    /// the oldest runs (by first-seen order in the file) are removed before
    /// any new events are written. Set `max_runs = 0` to disable pruning.
    ///
    /// # Arguments
    ///
    /// * `log_file`  - Path to JSONL log file (created if it doesn't exist)
    /// * `max_runs`  - Maximum number of distinct runs to retain; `0` disables pruning
    pub fn with_max_runs(log_file: PathBuf, max_runs: usize) -> Self {
        if let Some(parent) = log_file.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        let observer = Self {
            log_file,
            run_id: uuid::Uuid::new_v4().to_string(),
            max_runs,
        };
        observer.prune_old_runs();
        observer
    }

    /// Prune the JSONL log so that at most `max_runs` distinct run IDs are retained.
    ///
    /// Run IDs are ordered by first appearance in the file (oldest first). If the
    /// count exceeds the limit, the oldest entries are dropped and the file is
    /// rewritten atomically. This is a no-op when `max_runs == 0` or the file has
    /// fewer runs than the limit.
    fn prune_old_runs(&self) {
        if self.max_runs == 0 {
            return;
        }

        let content = match std::fs::read_to_string(&self.log_file) {
            Ok(c) if !c.is_empty() => c,
            _ => return,
        };

        // Collect run_ids in first-seen order (oldest run at index 0)
        let mut run_id_order: Vec<String> = Vec::new();
        let mut seen = std::collections::HashSet::new();

        for line in content.lines() {
            if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                if let Some(rid) = event.get("run_id").and_then(|v| v.as_str()) {
                    let rid = rid.to_string();
                    if seen.insert(rid.clone()) {
                        run_id_order.push(rid);
                    }
                }
            }
        }

        if run_id_order.len() <= self.max_runs {
            return; // nothing to prune
        }

        // The oldest runs to remove are at the front of run_id_order
        let drop_count = run_id_order.len() - self.max_runs;
        let to_drop: std::collections::HashSet<String> =
            run_id_order.into_iter().take(drop_count).collect();

        // Rewrite file retaining only events from kept runs
        let kept_lines: Vec<&str> = content
            .lines()
            .filter(|line| {
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(rid) = event.get("run_id").and_then(|v| v.as_str()) {
                        return !to_drop.contains(rid);
                    }
                }
                // Lines without a run_id are kept (e.g. future format extensions)
                true
            })
            .collect();

        let new_content = if kept_lines.is_empty() {
            String::new()
        } else {
            kept_lines.join("\n") + "\n"
        };

        std::fs::write(&self.log_file, new_content).ok();
    }

    /// Return the run_id for this observer instance.
    ///
    /// Used in tests to verify the run_id is stable across events.
    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    /// Write a JSON object to the log file (append-only, one line per event).
    fn write_json(&self, json: &serde_json::Value) {
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_file)
        {
            if let Ok(line) = serde_json::to_string(json) {
                writeln!(file, "{}", line).ok();
            }
        }
    }
}

impl Observer for DelegationEventObserver {
    fn record_event(&self, event: &ObserverEvent) {
        match event {
            ObserverEvent::DelegationStart {
                agent_name,
                provider,
                model,
                depth,
                agentic,
            } => {
                let json = serde_json::json!({
                    "event_type": "DelegationStart",
                    "run_id": self.run_id,
                    "agent_name": agent_name,
                    "provider": provider,
                    "model": model,
                    "depth": depth,
                    "agentic": agentic,
                    "timestamp": chrono::Utc::now().to_rfc3339(),
                });
                self.write_json(&json);
            }
            ObserverEvent::DelegationEnd {
                agent_name,
                provider,
                model,
                depth,
                duration,
                success,
                error_message,
                tokens_used,
                cost_usd,
            } => {
                let json = serde_json::json!({
                    "event_type": "DelegationEnd",
                    "run_id": self.run_id,
                    "agent_name": agent_name,
                    "provider": provider,
                    "model": model,
                    "depth": depth,
                    "duration_ms": duration.as_millis() as u64,
                    "success": success,
                    "error_message": error_message,
                    "tokens_used": tokens_used,
                    "cost_usd": cost_usd,
                    "timestamp": chrono::Utc::now().to_rfc3339(),
                });
                self.write_json(&json);
            }
            // Ignore all other events
            _ => {}
        }
    }

    fn record_metric(&self, _metric: &ObserverMetric) {
        // Delegation logger doesn't record metrics
    }

    fn name(&self) -> &str {
        "delegation-logger"
    }

    fn as_any(&self) -> &dyn Any {
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use tempfile::NamedTempFile;

    #[test]
    fn delegation_logger_name() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());
        assert_eq!(observer.name(), "delegation-logger");
    }

    #[test]
    fn run_id_is_valid_uuid() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());
        // UUID v4 format: 8-4-4-4-12 hex chars separated by hyphens
        let run_id = observer.run_id();
        assert_eq!(run_id.len(), 36);
        assert_eq!(run_id.chars().filter(|&c| c == '-').count(), 4);
        // Verify it parses as a valid UUID
        uuid::Uuid::parse_str(run_id).expect("run_id must be a valid UUID");
    }

    #[test]
    fn run_id_is_stable_across_events() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());
        let run_id = observer.run_id().to_string();

        observer.record_event(&ObserverEvent::DelegationStart {
            agent_name: "agent-a".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            agentic: true,
        });
        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "agent-a".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            duration: Duration::from_millis(100),
            success: true,
            error_message: None,
            tokens_used: None,
            cost_usd: None,
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        // Both events should contain the same run_id
        assert_eq!(
            content.matches(&run_id).count(),
            2,
            "Both events must contain the same run_id"
        );
    }

    #[test]
    fn different_instances_have_different_run_ids() {
        let temp1 = NamedTempFile::new().unwrap();
        let temp2 = NamedTempFile::new().unwrap();
        let obs1 = DelegationEventObserver::new(temp1.path().to_path_buf());
        let obs2 = DelegationEventObserver::new(temp2.path().to_path_buf());
        assert_ne!(
            obs1.run_id(),
            obs2.run_id(),
            "Different observer instances must have different run_ids"
        );
    }

    #[test]
    fn writes_delegation_start_event_with_run_id() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());
        let expected_run_id = observer.run_id().to_string();

        observer.record_event(&ObserverEvent::DelegationStart {
            agent_name: "research".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            agentic: true,
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        assert!(content.contains("\"event_type\":\"DelegationStart\""));
        assert!(content.contains("\"agent_name\":\"research\""));
        assert!(content.contains("\"provider\":\"anthropic\""));
        assert!(content.contains("\"depth\":1"));
        assert!(content.contains("\"agentic\":true"));
        assert!(content.contains(&format!("\"run_id\":\"{}\"", expected_run_id)));
    }

    #[test]
    fn writes_delegation_end_event_with_run_id() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());
        let expected_run_id = observer.run_id().to_string();

        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "research".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            duration: Duration::from_millis(4512),
            success: true,
            error_message: None,
            tokens_used: Some(1234),
            cost_usd: Some(0.0042),
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        assert!(content.contains("\"event_type\":\"DelegationEnd\""));
        assert!(content.contains("\"duration_ms\":4512"));
        assert!(content.contains("\"success\":true"));
        assert!(content.contains(&format!("\"run_id\":\"{}\"", expected_run_id)));
    }

    #[test]
    fn writes_tokens_and_cost_in_delegation_end() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "worker".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            duration: Duration::from_millis(200),
            success: true,
            error_message: None,
            tokens_used: Some(500),
            cost_usd: Some(0.0015),
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(content.trim()).unwrap();
        assert_eq!(parsed["tokens_used"], 500);
        assert!((parsed["cost_usd"].as_f64().unwrap() - 0.0015).abs() < 1e-9);
    }

    #[test]
    fn writes_null_tokens_and_cost_when_absent() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "worker".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            duration: Duration::from_millis(50),
            success: false,
            error_message: Some("timeout".into()),
            tokens_used: None,
            cost_usd: None,
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(content.trim()).unwrap();
        assert!(parsed["tokens_used"].is_null());
        assert!(parsed["cost_usd"].is_null());
    }

    #[test]
    fn ignores_non_delegation_events() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::HeartbeatTick);

        let content = std::fs::read_to_string(temp_file.path()).unwrap_or_default();
        assert!(content.is_empty() || !content.contains("HeartbeatTick"));
    }

    // ── §9 Log rotation helpers ────────────────────────────────────────────

    /// Write a single DelegationStart line with the given run_id directly to path.
    fn write_run_event(path: &std::path::Path, run_id: &str, agent_name: &str) {
        use std::io::Write;
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .unwrap();
        let event = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": run_id,
            "agent_name": agent_name,
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "depth": 0,
            "agentic": true,
            "timestamp": "2026-01-01T00:00:00Z",
        });
        writeln!(file, "{}", serde_json::to_string(&event).unwrap()).unwrap();
    }

    #[test]
    fn prune_is_noop_when_under_limit() {
        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        write_run_event(path, "run-aaa", "agent-a");
        write_run_event(path, "run-bbb", "agent-b");

        // 2 runs, max_runs=10 — nothing should be removed
        let _obs = DelegationEventObserver::with_max_runs(path.to_path_buf(), 10);

        let content = std::fs::read_to_string(path).unwrap();
        assert!(content.contains("run-aaa"), "run-aaa should be preserved");
        assert!(content.contains("run-bbb"), "run-bbb should be preserved");
    }

    #[test]
    fn prune_drops_oldest_run_when_over_limit() {
        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        write_run_event(path, "run-oldest", "agent-a");
        write_run_event(path, "run-middle", "agent-b");
        write_run_event(path, "run-newest", "agent-c");

        // 3 runs, max_runs=2 — oldest must be dropped
        let _obs = DelegationEventObserver::with_max_runs(path.to_path_buf(), 2);

        let content = std::fs::read_to_string(path).unwrap();
        assert!(!content.contains("run-oldest"), "oldest run must be pruned");
        assert!(content.contains("run-middle"), "middle run must be preserved");
        assert!(content.contains("run-newest"), "newest run must be preserved");
    }

    #[test]
    fn prune_drops_multiple_oldest_runs() {
        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        for i in 0..5usize {
            write_run_event(path, &format!("run-{i:03}"), &format!("agent-{i}"));
        }

        // max_runs=2: only run-003 and run-004 (the two newest) should survive
        let _obs = DelegationEventObserver::with_max_runs(path.to_path_buf(), 2);

        let content = std::fs::read_to_string(path).unwrap();
        for i in 0..3usize {
            assert!(
                !content.contains(&format!("run-{i:03}")),
                "run-{i:03} should be pruned"
            );
        }
        for i in 3..5usize {
            assert!(
                content.contains(&format!("run-{i:03}")),
                "run-{i:03} should be preserved"
            );
        }
    }

    #[test]
    fn prune_zero_disables_rotation() {
        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        for i in 0..10usize {
            write_run_event(path, &format!("run-{i:02}"), &format!("agent-{i}"));
        }

        // max_runs=0 means no pruning at all
        let _obs = DelegationEventObserver::with_max_runs(path.to_path_buf(), 0);

        let content = std::fs::read_to_string(path).unwrap();
        for i in 0..10usize {
            assert!(
                content.contains(&format!("run-{i:02}")),
                "run-{i:02} should not be pruned when max_runs=0"
            );
        }
    }

    #[test]
    fn prune_on_empty_file_does_not_panic() {
        let temp_file = NamedTempFile::new().unwrap();
        // Just constructing with max_runs=5 on an empty file must not panic
        let _obs = DelegationEventObserver::with_max_runs(temp_file.path().to_path_buf(), 5);
    }

    #[test]
    fn prune_preserves_event_order_within_kept_runs() {
        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        // run-old has 2 events; run-new has 1 event
        write_run_event(path, "run-old", "agent-first");
        write_run_event(path, "run-old", "agent-second");
        write_run_event(path, "run-new", "agent-third");

        // max_runs=1 — run-old is dropped; run-new and its single event survive
        let _obs = DelegationEventObserver::with_max_runs(path.to_path_buf(), 1);

        let content = std::fs::read_to_string(path).unwrap();
        assert!(!content.contains("run-old"), "run-old must be pruned");
        assert!(content.contains("run-new"), "run-new must be preserved");
        // Only the one remaining line from run-new should be present
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 1, "exactly one line should remain");
    }

    #[test]
    fn appends_multiple_events() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::DelegationStart {
            agent_name: "agent1".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            agentic: true,
        });

        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "agent1".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            duration: Duration::from_millis(100),
            success: true,
            error_message: None,
            tokens_used: None,
            cost_usd: None,
        });

        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 2);
        assert!(lines[0].contains("DelegationStart"));
        assert!(lines[1].contains("DelegationEnd"));
    }
}
