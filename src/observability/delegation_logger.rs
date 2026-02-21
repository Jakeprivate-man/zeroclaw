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
pub struct DelegationEventObserver {
    log_file: PathBuf,
    run_id: String,
}

impl DelegationEventObserver {
    /// Create a new delegation event logger.
    ///
    /// Generates a unique `run_id` (UUID v4) for this observer instance.
    /// All delegation events written by this observer will include the same `run_id`.
    ///
    /// # Arguments
    ///
    /// * `log_file` - Path to JSONL log file (will be created if it doesn't exist)
    ///
    /// # Example
    ///
    /// ```no_run
    /// use std::path::PathBuf;
    /// let observer = DelegationEventObserver::new(
    ///     PathBuf::from(shellexpand::tilde("~/.zeroclaw/state/delegation.jsonl").as_ref())
    /// );
    /// ```
    pub fn new(log_file: PathBuf) -> Self {
        // Ensure parent directory exists
        if let Some(parent) = log_file.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        Self {
            log_file,
            run_id: uuid::Uuid::new_v4().to_string(),
        }
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
