///! Delegation Event Logger - Writes delegation events to JSONL for UI consumption.
///!
///! This observer writes `DelegationStart` and `DelegationEnd` events to
///! `~/.zeroclaw/state/delegation.jsonl` in append-only JSONL format,
///! enabling the Streamlit UI to visualize delegation trees.

use super::traits::{Observer, ObserverEvent, ObserverMetric};
use std::any::Any;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

/// Observer that logs delegation events to JSONL file.
///
/// Only writes `DelegationStart` and `DelegationEnd` events, ignoring
/// all other event types. Events are written in append-only mode with
/// ISO8601 timestamps for consumption by the Streamlit delegation parser.
pub struct DelegationEventObserver {
    log_file: PathBuf,
}

impl DelegationEventObserver {
    /// Create a new delegation event logger.
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
        Self { log_file }
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
            } => {
                let json = serde_json::json!({
                    "event_type": "DelegationEnd",
                    "agent_name": agent_name,
                    "provider": provider,
                    "model": model,
                    "depth": depth,
                    "duration_ms": duration.as_millis() as u64,
                    "success": success,
                    "error_message": error_message,
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
    fn writes_delegation_start_event() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::DelegationStart {
            agent_name: "research".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            agentic: true,
        });

        // Read file and verify JSON
        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        assert!(content.contains("\"event_type\":\"DelegationStart\""));
        assert!(content.contains("\"agent_name\":\"research\""));
        assert!(content.contains("\"provider\":\"anthropic\""));
        assert!(content.contains("\"depth\":1"));
        assert!(content.contains("\"agentic\":true"));
    }

    #[test]
    fn writes_delegation_end_event() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "research".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 1,
            duration: Duration::from_millis(4512),
            success: true,
            error_message: None,
        });

        // Read file and verify JSON
        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        assert!(content.contains("\"event_type\":\"DelegationEnd\""));
        assert!(content.contains("\"duration_ms\":4512"));
        assert!(content.contains("\"success\":true"));
    }

    #[test]
    fn ignores_non_delegation_events() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        // Record a non-delegation event
        observer.record_event(&ObserverEvent::HeartbeatTick);

        // File should be empty or not exist
        let content = std::fs::read_to_string(temp_file.path()).unwrap_or_default();
        assert!(content.is_empty() || !content.contains("HeartbeatTick"));
    }

    #[test]
    fn appends_multiple_events() {
        let temp_file = NamedTempFile::new().unwrap();
        let observer = DelegationEventObserver::new(temp_file.path().to_path_buf());

        // Write start event
        observer.record_event(&ObserverEvent::DelegationStart {
            agent_name: "agent1".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            agentic: true,
        });

        // Write end event
        observer.record_event(&ObserverEvent::DelegationEnd {
            agent_name: "agent1".into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4".into(),
            depth: 0,
            duration: Duration::from_millis(100),
            success: true,
            error_message: None,
        });

        // Verify both events in file
        let content = std::fs::read_to_string(temp_file.path()).unwrap();
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 2);
        assert!(lines[0].contains("DelegationStart"));
        assert!(lines[1].contains("DelegationEnd"));
    }
}
