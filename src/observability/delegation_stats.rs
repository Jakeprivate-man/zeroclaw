/// In-memory delegation statistics observer.
///
/// Accumulates cumulative counters for every `DelegationStart` and
/// `DelegationEnd` event seen during a process lifetime. Thread-safe
/// via an internal `Mutex`; call [`snapshot`](DelegationStatsObserver::snapshot)
/// at any point to get a consistent point-in-time copy.
///
/// Useful for health-check endpoints, CLI summaries, and test assertions
/// that need programmatic access to delegation stats without parsing the
/// JSONL log.

use super::traits::{Observer, ObserverEvent, ObserverMetric};
use std::any::Any;
use std::sync::{Arc, Mutex};

/// Point-in-time snapshot of delegation statistics.
///
/// All fields are cumulative since the observer was created, except
/// `in_flight` which reflects the current number of started-but-not-yet-
/// ended delegations.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct DelegationStatsSnapshot {
    /// Total delegations started (includes completed and in-flight).
    pub total: u64,
    /// Delegations that ended with `success = true`.
    pub successful: u64,
    /// Delegations that ended with `success = false`.
    pub failed: u64,
    /// Delegations currently in-flight (started, not yet ended).
    pub in_flight: u64,
    /// Cumulative tokens across all completed delegations that reported them.
    pub total_tokens: u64,
    /// Cumulative cost (USD) across all completed delegations that reported it.
    pub total_cost_usd: f64,
    /// Maximum delegation depth seen across all `DelegationStart` events.
    pub max_depth: u32,
}

/// Observer that accumulates in-memory delegation statistics.
///
/// Implements the [`Observer`] trait; wire it into a [`MultiObserver`](super::multi::MultiObserver)
/// alongside the primary backend and [`DelegationEventObserver`](super::delegation_logger::DelegationEventObserver)
/// to get live programmatic access to delegation counters.
///
/// # Example
///
/// ```no_run
/// use std::sync::Arc;
/// use zeroclaw::observability::delegation_stats::DelegationStatsObserver;
///
/// let stats = Arc::new(DelegationStatsObserver::new());
/// // ... attach to agent run ...
/// let snap = stats.snapshot();
/// println!("delegations: {}, failed: {}", snap.total, snap.failed);
/// ```
pub struct DelegationStatsObserver {
    inner: Arc<Mutex<DelegationStatsSnapshot>>,
}

impl DelegationStatsObserver {
    /// Create a new observer with all counters at zero.
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(DelegationStatsSnapshot::default())),
        }
    }

    /// Return a consistent point-in-time copy of the current statistics.
    ///
    /// Acquires the internal lock for the duration of the copy only.
    /// Safe to call from any thread at any time.
    pub fn snapshot(&self) -> DelegationStatsSnapshot {
        self.inner
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }
}

impl Default for DelegationStatsObserver {
    fn default() -> Self {
        Self::new()
    }
}

impl Observer for DelegationStatsObserver {
    fn record_event(&self, event: &ObserverEvent) {
        match event {
            ObserverEvent::DelegationStart { depth, .. } => {
                let mut s = self.inner.lock().unwrap_or_else(|e| e.into_inner());
                s.total += 1;
                s.in_flight += 1;
                if *depth > s.max_depth {
                    s.max_depth = *depth;
                }
            }
            ObserverEvent::DelegationEnd {
                success,
                tokens_used,
                cost_usd,
                ..
            } => {
                let mut s = self.inner.lock().unwrap_or_else(|e| e.into_inner());
                s.in_flight = s.in_flight.saturating_sub(1);
                if *success {
                    s.successful += 1;
                } else {
                    s.failed += 1;
                }
                if let Some(t) = tokens_used {
                    s.total_tokens += t;
                }
                if let Some(c) = cost_usd {
                    s.total_cost_usd += c;
                }
            }
            _ => {}
        }
    }

    fn record_metric(&self, _metric: &ObserverMetric) {
        // Delegation stats observer does not track generic metrics
    }

    fn name(&self) -> &str {
        "delegation-stats"
    }

    fn as_any(&self) -> &dyn Any {
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    fn start(agent: &str, depth: u32) -> ObserverEvent {
        ObserverEvent::DelegationStart {
            agent_name: agent.into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4-6".into(),
            depth,
            agentic: true,
        }
    }

    fn end_ok(agent: &str, depth: u32, tokens: Option<u64>, cost: Option<f64>) -> ObserverEvent {
        ObserverEvent::DelegationEnd {
            agent_name: agent.into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4-6".into(),
            depth,
            duration: Duration::from_millis(100),
            success: true,
            error_message: None,
            tokens_used: tokens,
            cost_usd: cost,
        }
    }

    fn end_fail(agent: &str, depth: u32) -> ObserverEvent {
        ObserverEvent::DelegationEnd {
            agent_name: agent.into(),
            provider: "anthropic".into(),
            model: "claude-sonnet-4-6".into(),
            depth,
            duration: Duration::from_millis(50),
            success: false,
            error_message: Some("timeout".into()),
            tokens_used: None,
            cost_usd: None,
        }
    }

    #[test]
    fn new_observer_has_zero_counts() {
        let obs = DelegationStatsObserver::new();
        let snap = obs.snapshot();
        assert_eq!(snap, DelegationStatsSnapshot::default());
    }

    #[test]
    fn delegation_start_increments_total_and_in_flight() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("agent-a", 0));
        let snap = obs.snapshot();
        assert_eq!(snap.total, 1);
        assert_eq!(snap.in_flight, 1);
        assert_eq!(snap.successful, 0);
        assert_eq!(snap.failed, 0);
    }

    #[test]
    fn delegation_end_success_decrements_in_flight_and_increments_successful() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("agent-a", 0));
        obs.record_event(&end_ok("agent-a", 0, None, None));
        let snap = obs.snapshot();
        assert_eq!(snap.total, 1);
        assert_eq!(snap.in_flight, 0);
        assert_eq!(snap.successful, 1);
        assert_eq!(snap.failed, 0);
    }

    #[test]
    fn delegation_end_failure_increments_failed() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("agent-a", 0));
        obs.record_event(&end_fail("agent-a", 0));
        let snap = obs.snapshot();
        assert_eq!(snap.successful, 0);
        assert_eq!(snap.failed, 1);
        assert_eq!(snap.in_flight, 0);
    }

    #[test]
    fn delegation_end_accumulates_tokens_and_cost() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("a", 0));
        obs.record_event(&end_ok("a", 0, Some(500), Some(0.0015)));
        obs.record_event(&start("b", 1));
        obs.record_event(&end_ok("b", 1, Some(300), Some(0.0009)));
        let snap = obs.snapshot();
        assert_eq!(snap.total_tokens, 800);
        assert!((snap.total_cost_usd - 0.0024).abs() < 1e-9);
    }

    #[test]
    fn in_flight_saturates_at_zero_on_unmatched_end() {
        let obs = DelegationStatsObserver::new();
        // End without a matching start — must not underflow
        obs.record_event(&end_ok("orphan", 0, None, None));
        let snap = obs.snapshot();
        assert_eq!(snap.in_flight, 0, "in_flight must not underflow below zero");
    }

    #[test]
    fn max_depth_tracks_maximum_seen() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("root", 0));
        obs.record_event(&start("child", 1));
        obs.record_event(&start("grandchild", 2));
        let snap = obs.snapshot();
        assert_eq!(snap.max_depth, 2);
    }

    #[test]
    fn max_depth_does_not_regress_on_shallower_events() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("deep", 5));
        obs.record_event(&start("shallow", 1));
        let snap = obs.snapshot();
        assert_eq!(snap.max_depth, 5);
    }

    #[test]
    fn ignores_non_delegation_events() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&ObserverEvent::HeartbeatTick);
        obs.record_event(&ObserverEvent::AgentStart {
            provider: "anthropic".into(),
            model: "claude-sonnet-4-6".into(),
        });
        obs.record_event(&ObserverEvent::Error {
            component: "provider".into(),
            message: "timeout".into(),
        });
        assert_eq!(obs.snapshot(), DelegationStatsSnapshot::default());
    }

    #[test]
    fn multiple_concurrent_in_flight_tracked_correctly() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("a", 0));
        obs.record_event(&start("b", 1));
        obs.record_event(&start("c", 2));
        assert_eq!(obs.snapshot().in_flight, 3);
        obs.record_event(&end_ok("c", 2, None, None));
        assert_eq!(obs.snapshot().in_flight, 2);
        obs.record_event(&end_fail("b", 1));
        assert_eq!(obs.snapshot().in_flight, 1);
        obs.record_event(&end_ok("a", 0, Some(100), Some(0.0003)));
        let snap = obs.snapshot();
        assert_eq!(snap.in_flight, 0);
        assert_eq!(snap.total, 3);
        assert_eq!(snap.successful, 2);
        assert_eq!(snap.failed, 1);
        assert_eq!(snap.total_tokens, 100);
    }

    #[test]
    fn tokens_absent_does_not_affect_total() {
        let obs = DelegationStatsObserver::new();
        obs.record_event(&start("a", 0));
        obs.record_event(&end_ok("a", 0, None, None));
        assert_eq!(obs.snapshot().total_tokens, 0);
        assert!((obs.snapshot().total_cost_usd).abs() < 1e-9);
    }

    #[test]
    fn observer_name_is_delegation_stats() {
        assert_eq!(DelegationStatsObserver::new().name(), "delegation-stats");
    }

    #[test]
    fn default_equals_new() {
        let a = DelegationStatsObserver::new();
        let b = DelegationStatsObserver::default();
        assert_eq!(a.snapshot(), b.snapshot());
    }
}
