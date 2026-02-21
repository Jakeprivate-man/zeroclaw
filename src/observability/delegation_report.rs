//! CLI-facing delegation log reporter.
//!
//! Three public entry points used by `zeroclaw delegations [list|show]`:
//! - [`print_summary`]: overall totals across all stored runs.
//! - [`print_runs`]: table of runs, newest first.
//! - [`print_tree`]: indented delegation tree for one run.
//!
//! All parsing is done via `serde_json::Value` — no new dependencies.

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde_json::Value;
use std::collections::HashMap;
use std::path::Path;

// ─── Internal types ───────────────────────────────────────────────────────────

struct RunInfo {
    run_id: String,
    start_time: Option<DateTime<Utc>>,
    delegation_count: usize,
    total_tokens: u64,
    total_cost_usd: f64,
}

struct ReportNode {
    agent_name: String,
    model: String,
    depth: u32,
    duration_ms: Option<u64>,
    tokens_used: Option<u64>,
    cost_usd: Option<f64>,
    success: Option<bool>,
    start_ts: Option<DateTime<Utc>>,
}

// ─── File I/O ─────────────────────────────────────────────────────────────────

fn read_all_events(log_path: &Path) -> Result<Vec<Value>> {
    if !log_path.exists() {
        return Ok(vec![]);
    }
    let content = std::fs::read_to_string(log_path)?;
    let mut out = Vec::new();
    for line in content.lines() {
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(v) = serde_json::from_str::<Value>(line) {
            out.push(v);
        }
    }
    Ok(out)
}

fn parse_ts(val: &Value) -> Option<DateTime<Utc>> {
    val.as_str()
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|dt| dt.with_timezone(&Utc))
}

// ─── Run aggregation ──────────────────────────────────────────────────────────

fn collect_runs(events: &[Value]) -> Vec<RunInfo> {
    let mut map: HashMap<String, RunInfo> = HashMap::new();
    for ev in events {
        let Some(rid) = ev.get("run_id").and_then(|x| x.as_str()) else {
            continue;
        };
        let ts = ev.get("timestamp").and_then(parse_ts);
        let entry = map.entry(rid.to_owned()).or_insert_with(|| RunInfo {
            run_id: rid.to_owned(),
            start_time: None,
            delegation_count: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        });
        if let Some(ts) = ts {
            if entry.start_time.map_or(true, |s| ts < s) {
                entry.start_time = Some(ts);
            }
        }
        match ev.get("event_type").and_then(|x| x.as_str()) {
            Some("DelegationStart") => entry.delegation_count += 1,
            Some("DelegationEnd") => {
                if let Some(tok) = ev.get("tokens_used").and_then(|x| x.as_u64()) {
                    entry.total_tokens += tok;
                }
                if let Some(cost) = ev.get("cost_usd").and_then(|x| x.as_f64()) {
                    entry.total_cost_usd += cost;
                }
            }
            _ => {}
        }
    }
    let mut runs: Vec<RunInfo> = map.into_values().collect();
    // newest first
    runs.sort_by(|a, b| b.start_time.cmp(&a.start_time));
    runs
}

// ─── Node matching ────────────────────────────────────────────────────────────

fn build_nodes(events: &[Value]) -> Vec<ReportNode> {
    let starts: Vec<&Value> = events
        .iter()
        .filter(|e| e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationStart"))
        .collect();
    let ends: Vec<&Value> = events
        .iter()
        .filter(|e| e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd"))
        .collect();

    let mut nodes: Vec<ReportNode> = starts
        .iter()
        .map(|s| ReportNode {
            agent_name: s
                .get("agent_name")
                .and_then(|x| x.as_str())
                .unwrap_or("?")
                .to_owned(),
            model: s
                .get("model")
                .and_then(|x| x.as_str())
                .unwrap_or("?")
                .to_owned(),
            depth: s
                .get("depth")
                .and_then(|x| x.as_u64())
                .and_then(|d| u32::try_from(d).ok())
                .unwrap_or(0),
            duration_ms: None,
            tokens_used: None,
            cost_usd: None,
            success: None,
            start_ts: s.get("timestamp").and_then(parse_ts),
        })
        .collect();

    // Match each end event to the first unresolved node with the same name+depth.
    for end in &ends {
        let name = end.get("agent_name").and_then(|x| x.as_str()).unwrap_or("");
        let depth = end
            .get("depth")
            .and_then(|x| x.as_u64())
            .and_then(|d| u32::try_from(d).ok())
            .unwrap_or(0);
        if let Some(node) = nodes
            .iter_mut()
            .find(|n| n.agent_name == name && n.depth == depth && n.success.is_none())
        {
            node.duration_ms = end.get("duration_ms").and_then(|x| x.as_u64());
            node.tokens_used = end.get("tokens_used").and_then(|x| x.as_u64());
            node.cost_usd = end.get("cost_usd").and_then(|x| x.as_f64());
            node.success = end.get("success").and_then(|x| x.as_bool());
        }
    }

    // Sort by start timestamp so the order matches run sequence.
    nodes.sort_by_key(|n| n.start_ts);
    nodes
}

// ─── Formatting helpers ───────────────────────────────────────────────────────

fn fmt_duration(ms: u64) -> String {
    if ms < 1000 {
        format!("{ms}ms")
    } else {
        format!("{:.2}s", ms as f64 / 1000.0)
    }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/// Print a one-line summary of all stored delegation runs to stdout.
pub fn print_summary(log_path: &Path) -> Result<()> {
    let events = read_all_events(log_path)?;
    if events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }
    let runs = collect_runs(&events);
    let total_delegations: usize = runs.iter().map(|r| r.delegation_count).sum();
    let total_tokens: u64 = runs.iter().map(|r| r.total_tokens).sum();
    let total_cost: f64 = runs.iter().map(|r| r.total_cost_usd).sum();

    println!("Delegation Log: {}", log_path.display());
    println!();
    println!("  Runs stored:      {}", runs.len());
    println!("  Delegations:      {}", total_delegations);
    println!(
        "  Total tokens:     {}",
        if total_tokens > 0 {
            total_tokens.to_string()
        } else {
            "—".to_owned()
        }
    );
    println!(
        "  Total cost:       {}",
        if total_cost > 0.0 {
            format!("${total_cost:.4}")
        } else {
            "—".to_owned()
        }
    );
    if let Some(newest) = runs.first() {
        let ts = newest
            .start_time
            .map(|t| t.format("%Y-%m-%d %H:%M:%S UTC").to_string())
            .unwrap_or_else(|| "unknown".to_owned());
        println!("  Latest run:       {ts}");
    }
    println!();
    println!("Use `zeroclaw delegations list` to see all runs.");
    println!("Use `zeroclaw delegations show` to inspect the most recent run.");
    Ok(())
}

/// Print a table of all stored runs to stdout, newest first.
pub fn print_runs(log_path: &Path) -> Result<()> {
    let events = read_all_events(log_path)?;
    if events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        return Ok(());
    }
    let runs = collect_runs(&events);
    println!(
        "{:<4} {:<23} {:>11} {:>10} {:>10}  run_id",
        "#", "start (UTC)", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(78));
    for (i, run) in runs.iter().enumerate() {
        let ts = run
            .start_time
            .map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
            .unwrap_or_else(|| "unknown".to_owned());
        let tok = if run.total_tokens > 0 {
            run.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if run.total_cost_usd > 0.0 {
            format!("${:.4}", run.total_cost_usd)
        } else {
            "—".to_owned()
        };
        println!(
            "{:<4} {:<23} {:>11} {:>10} {:>10}  {}",
            i + 1,
            ts,
            run.delegation_count,
            tok,
            cost,
            run.run_id
        );
    }
    Ok(())
}

/// Print the delegation tree for a run to stdout.
///
/// Defaults to the most recent run when `run_id` is `None`.
pub fn print_tree(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        return Ok(());
    }

    // Resolve run_id to most recent when not specified.
    let resolved = if let Some(rid) = run_id {
        rid.to_owned()
    } else {
        let runs = collect_runs(&all_events);
        match runs.into_iter().next() {
            Some(r) => r.run_id,
            None => {
                println!("No runs found.");
                return Ok(());
            }
        }
    };

    let run_events: Vec<Value> = all_events
        .into_iter()
        .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(resolved.as_str()))
        .collect();

    if run_events.is_empty() {
        println!("No events found for run: {resolved}");
        return Ok(());
    }

    let nodes = build_nodes(&run_events);

    println!("Run: {resolved}");
    println!("{}", "─".repeat(78));
    println!(
        "{:<42} {:>8} {:>8} {:>10}  status",
        "agent (model)", "dur", "tokens", "cost"
    );
    println!("{}", "─".repeat(78));

    for node in &nodes {
        let indent = "  ".repeat(node.depth as usize);
        let label = format!("{}{}  [{}]", indent, node.agent_name, node.model);
        let dur = node
            .duration_ms
            .map(fmt_duration)
            .unwrap_or_else(|| "…".to_owned());
        let tok = node
            .tokens_used
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = node
            .cost_usd
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let status = match node.success {
            Some(true) => "OK",
            Some(false) => "FAIL",
            None => "running",
        };
        println!("{:<42} {:>8} {:>8} {:>10}  {}", label, dur, tok, cost, status);
    }

    println!("{}", "─".repeat(78));
    let total_tokens: u64 = nodes.iter().filter_map(|n| n.tokens_used).sum();
    let total_cost: f64 = nodes.iter().filter_map(|n| n.cost_usd).sum();
    println!(
        "Total: {} delegations  |  {} tokens  |  ${:.4}",
        nodes.len(),
        if total_tokens > 0 {
            total_tokens.to_string()
        } else {
            "—".to_owned()
        },
        total_cost
    );
    Ok(())
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_start(run_id: &str, agent: &str, depth: u32, ts: &str) -> Value {
        serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": run_id,
            "agent_name": agent,
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "depth": depth,
            "agentic": true,
            "timestamp": ts
        })
    }

    fn make_end(
        run_id: &str,
        agent: &str,
        depth: u32,
        ts: &str,
        tokens: u64,
        cost: f64,
        success: bool,
    ) -> Value {
        serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": agent,
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "depth": depth,
            "duration_ms": 1000u64,
            "success": success,
            "tokens_used": tokens,
            "cost_usd": cost,
            "timestamp": ts
        })
    }

    #[test]
    fn collect_runs_aggregates_tokens_and_cost() {
        let events = vec![
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
            make_end("run-aaa", "main", 0, "2026-01-01T10:00:05Z", 1000, 0.003, true),
            make_start("run-bbb", "main", 0, "2026-01-01T11:00:00Z"),
            make_end("run-bbb", "main", 0, "2026-01-01T11:00:05Z", 2000, 0.006, true),
        ];
        let runs = collect_runs(&events);
        assert_eq!(runs.len(), 2);
        // Newest first: run-bbb
        assert_eq!(runs[0].run_id, "run-bbb");
        assert_eq!(runs[0].total_tokens, 2000);
        assert_eq!(runs[1].run_id, "run-aaa");
        assert_eq!(runs[1].total_tokens, 1000);
    }

    #[test]
    fn collect_runs_counts_delegations_from_starts_only() {
        let events = vec![
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
            make_start("run-aaa", "sub", 1, "2026-01-01T10:00:01Z"),
            make_end("run-aaa", "sub", 1, "2026-01-01T10:00:03Z", 500, 0.001, true),
            make_end("run-aaa", "main", 0, "2026-01-01T10:00:05Z", 1000, 0.003, true),
        ];
        let runs = collect_runs(&events);
        assert_eq!(runs.len(), 1);
        assert_eq!(runs[0].delegation_count, 2); // two DelegationStart events
        assert_eq!(runs[0].total_tokens, 1500);  // 500 + 1000 from DelegationEnd events
    }

    #[test]
    fn build_nodes_matches_start_and_end() {
        let events = vec![
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
            make_end("run-aaa", "main", 0, "2026-01-01T10:00:05Z", 1234, 0.0037, true),
        ];
        let nodes = build_nodes(&events);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].agent_name, "main");
        assert_eq!(nodes[0].tokens_used, Some(1234));
        assert_eq!(nodes[0].success, Some(true));
    }

    #[test]
    fn build_nodes_marks_unmatched_as_in_flight() {
        let events = vec![
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
        ];
        let nodes = build_nodes(&events);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].success, None); // no end event yet
        assert_eq!(nodes[0].tokens_used, None);
    }

    #[test]
    fn build_nodes_orders_by_start_ts() {
        let events = vec![
            make_start("run-aaa", "sub", 1, "2026-01-01T10:00:01Z"),
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
        ];
        let nodes = build_nodes(&events);
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].agent_name, "main");
        assert_eq!(nodes[1].agent_name, "sub");
    }

    #[test]
    fn print_summary_on_empty_log_succeeds() {
        let dir = std::env::temp_dir();
        let path = dir.join("zeroclaw_test_report_empty.jsonl");
        // Ensure file does not exist
        let _ = std::fs::remove_file(&path);
        let result = print_summary(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_runs_on_populated_log_succeeds() {
        let dir = std::env::temp_dir();
        let path = dir.join("zeroclaw_test_report_runs.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-test", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-test", "main", 0, "2026-01-01T10:00:05Z", 500, 0.001, true)).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_runs(&path);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_tree_defaults_to_most_recent_run() {
        let dir = std::env::temp_dir();
        let path = dir.join("zeroclaw_test_report_tree.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-recent", "main", 0, "2026-01-02T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-recent", "main", 0, "2026-01-02T10:00:05Z", 800, 0.002, true)).unwrap());
        lines.push(serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // print_tree with no run_id should pick run-recent (newest)
        let result = print_tree(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_tree_with_specific_run_id() {
        let dir = std::env::temp_dir();
        let path = dir.join("zeroclaw_test_report_tree_specific.jsonl");
        let line = serde_json::to_string(&make_start("run-specific", "main", 0, "2026-01-01T10:00:00Z")).unwrap();
        std::fs::write(&path, line + "\n").unwrap();
        let result = print_tree(&path, Some("run-specific"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn fmt_duration_formats_ms_and_seconds() {
        assert_eq!(fmt_duration(500), "500ms");
        assert_eq!(fmt_duration(1000), "1.00s");
        assert_eq!(fmt_duration(2500), "2.50s");
    }
}
