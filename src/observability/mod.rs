pub mod delegation_logger;
pub mod delegation_report;
pub mod delegation_stats;
pub mod log;
pub mod multi;
pub mod noop;
pub mod otel;
pub mod prometheus;
pub mod traits;
pub mod verbose;

pub use delegation_logger::DelegationEventObserver;
#[allow(unused_imports)]
pub use delegation_stats::{DelegationStatsObserver, DelegationStatsSnapshot};
#[allow(unused_imports)]
pub use self::log::LogObserver;
#[allow(unused_imports)]
pub use self::multi::MultiObserver;
pub use noop::NoopObserver;
pub use otel::OtelObserver;
pub use prometheus::PrometheusObserver;
pub use traits::{Observer, ObserverEvent};
#[allow(unused_imports)]
pub use verbose::VerboseObserver;

use crate::config::ObservabilityConfig;
use std::path::PathBuf;

/// Factory: create the right observer from config.
///
/// `delegation_log` is the path where delegation events are written (e.g.
/// `config.delegation_log_path()`). Callers own path computation so the log
/// location stays consistent with the rest of the zeroclaw state directory.
pub fn create_observer(config: &ObservabilityConfig, delegation_log: PathBuf) -> Box<dyn Observer> {
    // Create primary observer based on config
    let primary: Box<dyn Observer> = match config.backend.as_str() {
        "log" => Box::new(LogObserver::new()),
        "prometheus" => Box::new(PrometheusObserver::new()),
        "otel" | "opentelemetry" | "otlp" => {
            match OtelObserver::new(
                config.otel_endpoint.as_deref(),
                config.otel_service_name.as_deref(),
            ) {
                Ok(obs) => {
                    tracing::info!(
                        endpoint = config
                            .otel_endpoint
                            .as_deref()
                            .unwrap_or("http://localhost:4318"),
                        "OpenTelemetry observer initialized"
                    );
                    Box::new(obs)
                }
                Err(e) => {
                    tracing::error!("Failed to create OTel observer: {e}. Falling back to noop.");
                    Box::new(NoopObserver)
                }
            }
        }
        "none" | "noop" => Box::new(NoopObserver),
        _ => {
            tracing::warn!(
                "Unknown observability backend '{}', falling back to noop",
                config.backend
            );
            Box::new(NoopObserver)
        }
    };

    // Add delegation event logger (writes to the caller-supplied path).
    let delegation_logger: Box<dyn Observer> = Box::new(DelegationEventObserver::new(delegation_log));

    // Combine both observers using MultiObserver
    Box::new(MultiObserver::new(vec![primary, delegation_logger]))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_log() -> PathBuf {
        std::env::temp_dir().join("zeroclaw_test_delegation.jsonl")
    }

    #[test]
    fn factory_none_returns_multi() {
        let cfg = ObservabilityConfig {
            backend: "none".into(),
            ..ObservabilityConfig::default()
        };
        // Factory now returns MultiObserver wrapping primary + delegation logger
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_noop_returns_multi() {
        let cfg = ObservabilityConfig {
            backend: "noop".into(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_log_returns_multi() {
        let cfg = ObservabilityConfig {
            backend: "log".into(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_prometheus_returns_multi() {
        let cfg = ObservabilityConfig {
            backend: "prometheus".into(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_otel_returns_multi() {
        let cfg = ObservabilityConfig {
            backend: "otel".into(),
            otel_endpoint: Some("http://127.0.0.1:19999".into()),
            otel_service_name: Some("test".into()),
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_opentelemetry_alias() {
        let cfg = ObservabilityConfig {
            backend: "opentelemetry".into(),
            otel_endpoint: Some("http://127.0.0.1:19999".into()),
            otel_service_name: Some("test".into()),
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_otlp_alias() {
        let cfg = ObservabilityConfig {
            backend: "otlp".into(),
            otel_endpoint: Some("http://127.0.0.1:19999".into()),
            otel_service_name: Some("test".into()),
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_unknown_falls_back_to_multi() {
        let cfg = ObservabilityConfig {
            backend: "xyzzy_unknown".into(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_empty_string_falls_back_to_multi() {
        let cfg = ObservabilityConfig {
            backend: String::new(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }

    #[test]
    fn factory_garbage_falls_back_to_multi() {
        let cfg = ObservabilityConfig {
            backend: "xyzzy_garbage_123".into(),
            ..ObservabilityConfig::default()
        };
        assert_eq!(create_observer(&cfg, test_log()).name(), "multi");
    }
}
