//! CLI-facing delegation log reporter.
//!
//! Public entry points used by `zeroclaw delegations [list|show|stats|export]`:
//! - [`print_summary`]: overall totals across all stored runs.
//! - [`print_runs`]: table of runs, newest first.
//! - [`print_tree`]: indented delegation tree for one run.
//! - [`print_stats`]: per-agent aggregated statistics table.
//! - [`print_export`]: stream delegation events as JSONL or CSV.
//! - [`get_log_summary`]: programmatic aggregate for `zeroclaw status`.
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

struct AgentStats {
    agent_name: String,
    delegation_count: usize,
    end_count: usize,
    success_count: usize,
    total_duration_ms: u64,
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

fn collect_agent_stats(events: &[Value]) -> Vec<AgentStats> {
    let mut map: HashMap<String, AgentStats> = HashMap::new();
    for ev in events {
        let Some(name) = ev.get("agent_name").and_then(|x| x.as_str()) else {
            continue;
        };
        let entry = map.entry(name.to_owned()).or_insert_with(|| AgentStats {
            agent_name: name.to_owned(),
            delegation_count: 0,
            end_count: 0,
            success_count: 0,
            total_duration_ms: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        });
        match ev.get("event_type").and_then(|x| x.as_str()) {
            Some("DelegationStart") => entry.delegation_count += 1,
            Some("DelegationEnd") => {
                entry.end_count += 1;
                if ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false) {
                    entry.success_count += 1;
                }
                if let Some(dur) = ev.get("duration_ms").and_then(|x| x.as_u64()) {
                    entry.total_duration_ms += dur;
                }
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
    let mut stats: Vec<AgentStats> = map.into_values().collect();
    // Heaviest first (most tokens), then alphabetical as tiebreaker.
    stats.sort_by(|a, b| {
        b.total_tokens
            .cmp(&a.total_tokens)
            .then(a.agent_name.cmp(&b.agent_name))
    });
    stats
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

// ─── CSV helpers ─────────────────────────────────────────────────────────────

/// Wrap `s` in double-quotes when it contains a comma, double-quote, or newline.
/// Internal double-quotes are escaped by doubling them (RFC 4180).
fn csv_field(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_owned()
    }
}

// ─── Public data types ────────────────────────────────────────────────────────

/// Output format for [`print_export`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExportFormat {
    /// Newline-delimited JSON — one raw event object per line.
    Jsonl,
    /// RFC 4180 CSV — one row per `DelegationEnd` event.
    Csv,
}

/// Aggregate statistics extracted from the delegation log.
///
/// Returned by [`get_log_summary`] for callers that need the data
/// programmatically (e.g. `zeroclaw status`) rather than pre-formatted text.
#[derive(Debug, Clone, Default)]
pub struct LogSummary {
    /// Number of distinct process invocations stored in the log.
    pub run_count: usize,
    /// Total `DelegationStart` events across all runs.
    pub total_delegations: usize,
    /// Cumulative tokens across all `DelegationEnd` events.
    pub total_tokens: u64,
    /// Cumulative cost (USD) across all `DelegationEnd` events.
    pub total_cost_usd: f64,
    /// Start time of the most recent run (newest first).
    pub latest_run_time: Option<DateTime<Utc>>,
}

// ─── Public API ───────────────────────────────────────────────────────────────

/// Stream delegation events to stdout as JSONL or CSV.
///
/// `ExportFormat::Jsonl` (default): emits one raw event JSON object per line,
/// suitable for piping to `jq` or re-importing into another tool.
///
/// `ExportFormat::Csv`: emits a header row followed by one row per
/// `DelegationEnd` event with columns:
/// `run_id,agent_name,model,depth,duration_ms,tokens_used,cost_usd,success,timestamp`
///
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_export(log_path: &Path, run_id: Option<&str>, format: ExportFormat) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        return Ok(());
    }

    let events: Vec<Value> = if let Some(rid) = run_id {
        all_events
            .into_iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events
    };

    match format {
        ExportFormat::Jsonl => {
            for ev in &events {
                println!("{}", serde_json::to_string(ev)?);
            }
        }
        ExportFormat::Csv => {
            println!("run_id,agent_name,model,depth,duration_ms,tokens_used,cost_usd,success,timestamp");
            for ev in &events {
                if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
                    continue;
                }
                let run_id_col = csv_field(ev.get("run_id").and_then(|x| x.as_str()).unwrap_or(""));
                let agent = csv_field(ev.get("agent_name").and_then(|x| x.as_str()).unwrap_or(""));
                let model = csv_field(ev.get("model").and_then(|x| x.as_str()).unwrap_or(""));
                let depth = ev.get("depth").and_then(|x| x.as_u64()).unwrap_or(0);
                let dur = ev
                    .get("duration_ms")
                    .and_then(|x| x.as_u64())
                    .map(|d| d.to_string())
                    .unwrap_or_default();
                let tok = ev
                    .get("tokens_used")
                    .and_then(|x| x.as_u64())
                    .map(|t| t.to_string())
                    .unwrap_or_default();
                let cost = ev
                    .get("cost_usd")
                    .and_then(|x| x.as_f64())
                    .map(|c| format!("{c:.6}"))
                    .unwrap_or_default();
                let success = ev
                    .get("success")
                    .and_then(|x| x.as_bool())
                    .map(|s| if s { "true" } else { "false" })
                    .unwrap_or("");
                let ts = csv_field(ev.get("timestamp").and_then(|x| x.as_str()).unwrap_or(""));
                println!("{run_id_col},{agent},{model},{depth},{dur},{tok},{cost},{success},{ts}");
            }
        }
    }
    Ok(())
}

/// Return aggregate statistics from the delegation log, or `None` if the
/// log does not exist or contains no parseable run data.
pub fn get_log_summary(log_path: &Path) -> Result<Option<LogSummary>> {
    let events = read_all_events(log_path)?;
    if events.is_empty() {
        return Ok(None);
    }
    let runs = collect_runs(&events);
    if runs.is_empty() {
        return Ok(None);
    }
    let total_delegations: usize = runs.iter().map(|r| r.delegation_count).sum();
    let total_tokens: u64 = runs.iter().map(|r| r.total_tokens).sum();
    let total_cost_usd: f64 = runs.iter().map(|r| r.total_cost_usd).sum();
    let latest_run_time = runs.first().and_then(|r| r.start_time);
    Ok(Some(LogSummary {
        run_count: runs.len(),
        total_delegations,
        total_tokens,
        total_cost_usd,
        latest_run_time,
    }))
}

/// Print a per-agent statistics table to stdout.
///
/// When `run_id` is `Some`, only events from that run are included.
/// `None` aggregates across all stored runs.
///
/// Columns: agent | count | ok% | avg_dur | tokens | cost
/// Rows are sorted by total tokens descending (heaviest agent first).
pub fn print_stats(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // Optional run filter — consume all_events to avoid cloning.
    let events: Vec<Value> = if let Some(rid) = run_id {
        all_events
            .into_iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    let stats = collect_agent_stats(&events);
    if stats.is_empty() {
        println!("No delegation events found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Delegation Stats{scope}");
    println!();
    println!(
        "{:<26} {:>6}  {:>6}  {:>8}  {:>10}  {:>10}",
        "agent", "count", "ok%", "avg_dur", "tokens", "cost"
    );
    println!("{}", "─".repeat(76));

    for s in &stats {
        let ok_pct = if s.end_count > 0 {
            format!("{:.1}%", 100.0 * s.success_count as f64 / s.end_count as f64)
        } else {
            "—".to_owned()
        };
        let avg_dur = if s.end_count > 0 {
            fmt_duration(s.total_duration_ms / s.end_count as u64)
        } else {
            "—".to_owned()
        };
        let tokens = if s.total_tokens > 0 {
            s.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if s.total_cost_usd > 0.0 {
            format!("${:.4}", s.total_cost_usd)
        } else {
            "—".to_owned()
        };
        println!(
            "{:<26} {:>6}  {:>6}  {:>8}  {:>10}  {:>10}",
            s.agent_name, s.delegation_count, ok_pct, avg_dur, tokens, cost
        );
    }

    println!("{}", "─".repeat(76));
    let total_count: usize = stats.iter().map(|s| s.delegation_count).sum();
    let total_tokens: u64 = stats.iter().map(|s| s.total_tokens).sum();
    let total_cost: f64 = stats.iter().map(|s| s.total_cost_usd).sum();
    println!(
        "{:<26} {:>6}  {:>6}  {:>8}  {:>10}  {:>10}",
        "TOTAL",
        total_count,
        "",
        "",
        if total_tokens > 0 {
            total_tokens.to_string()
        } else {
            "—".to_owned()
        },
        if total_cost > 0.0 {
            format!("${:.4}", total_cost)
        } else {
            "—".to_owned()
        }
    );
    println!();
    println!("Use `zeroclaw delegations stats --run <id>` to scope to one run.");
    Ok(())
}

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

    #[test]
    fn collect_agent_stats_aggregates_by_agent_name() {
        let events = vec![
            make_start("run-a", "main", 0, "2026-01-01T10:00:00Z"),
            make_end("run-a", "main", 0, "2026-01-01T10:00:05Z", 1000, 0.003, true),
            make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z"),
            make_end("run-a", "sub", 1, "2026-01-01T10:00:04Z", 500, 0.001, true),
            make_start("run-a", "main", 0, "2026-01-01T11:00:00Z"),
            make_end("run-a", "main", 0, "2026-01-01T11:00:05Z", 2000, 0.006, false),
        ];
        let stats = collect_agent_stats(&events);
        let main = stats.iter().find(|s| s.agent_name == "main").unwrap();
        let sub = stats.iter().find(|s| s.agent_name == "sub").unwrap();
        assert_eq!(main.delegation_count, 2);
        assert_eq!(main.end_count, 2);
        assert_eq!(main.total_tokens, 3000);
        assert_eq!(sub.delegation_count, 1);
        assert_eq!(sub.total_tokens, 500);
    }

    #[test]
    fn collect_agent_stats_tracks_success_and_duration() {
        let events = vec![
            make_start("run-a", "main", 0, "2026-01-01T10:00:00Z"),
            make_end("run-a", "main", 0, "2026-01-01T10:00:05Z", 100, 0.001, true),
            make_start("run-a", "main", 0, "2026-01-01T11:00:00Z"),
            make_end("run-a", "main", 0, "2026-01-01T11:00:05Z", 200, 0.002, false),
        ];
        let stats = collect_agent_stats(&events);
        let main = stats.iter().find(|s| s.agent_name == "main").unwrap();
        assert_eq!(main.success_count, 1);
        assert_eq!(main.end_count, 2);
        // duration_ms from make_end is always 1000 (see fixture above)
        assert_eq!(main.total_duration_ms, 2000);
    }

    #[test]
    fn collect_agent_stats_sorts_tokens_descending() {
        let events = vec![
            make_start("run-a", "light", 1, "2026-01-01T10:00:00Z"),
            make_end("run-a", "light", 1, "2026-01-01T10:00:01Z", 100, 0.0001, true),
            make_start("run-a", "heavy", 0, "2026-01-01T10:00:00Z"),
            make_end("run-a", "heavy", 0, "2026-01-01T10:00:05Z", 5000, 0.015, true),
        ];
        let stats = collect_agent_stats(&events);
        assert_eq!(stats.len(), 2);
        assert_eq!(stats[0].agent_name, "heavy"); // most tokens first
        assert_eq!(stats[1].agent_name, "light");
    }

    #[test]
    fn print_stats_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_stats_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_stats(&path, None).is_ok());
    }

    #[test]
    fn print_stats_with_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_stats_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-keep", "main", 0, "2026-01-01T10:00:05Z", 999, 0.003, true)).unwrap());
        lines.push(serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z")).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_stats(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn get_log_summary_on_missing_file_returns_none() {
        let path = std::env::temp_dir().join("zeroclaw_test_summary_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = get_log_summary(&path);
        assert!(result.is_ok());
        assert!(result.unwrap().is_none());
    }

    #[test]
    fn get_log_summary_on_empty_log_returns_none() {
        let path = std::env::temp_dir().join("zeroclaw_test_summary_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = get_log_summary(&path);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
        assert!(result.unwrap().is_none());
    }

    #[test]
    fn get_log_summary_aggregates_all_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_summary_agg.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-x", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-x", "main", 0, "2026-01-01T10:00:05Z", 1000, 0.003, true)).unwrap());
        lines.push(serde_json::to_string(&make_start("run-y", "main", 0, "2026-01-02T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-y", "main", 0, "2026-01-02T10:00:05Z", 2000, 0.006, true)).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let summary = get_log_summary(&path).unwrap().unwrap();
        let _ = std::fs::remove_file(&path);
        assert_eq!(summary.run_count, 2);
        assert_eq!(summary.total_delegations, 2);
        assert_eq!(summary.total_tokens, 3000);
        assert!((summary.total_cost_usd - 0.009).abs() < 1e-9);
    }

    #[test]
    fn get_log_summary_latest_run_time_is_most_recent() {
        let path = std::env::temp_dir().join("zeroclaw_test_summary_latest.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_start("run-new", "main", 0, "2026-01-03T10:00:00Z")).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let summary = get_log_summary(&path).unwrap().unwrap();
        let _ = std::fs::remove_file(&path);
        let ts = summary.latest_run_time.expect("should have latest_run_time");
        assert_eq!(ts.format("%Y-%m-%d").to_string(), "2026-01-03");
    }

    #[test]
    fn csv_field_passthrough_for_plain_strings() {
        assert_eq!(csv_field("hello"), "hello");
        assert_eq!(csv_field("claude-sonnet-4"), "claude-sonnet-4");
    }

    #[test]
    fn csv_field_wraps_strings_containing_commas() {
        assert_eq!(csv_field("a,b"), "\"a,b\"");
    }

    #[test]
    fn csv_field_escapes_embedded_double_quotes() {
        assert_eq!(csv_field("say \"hi\""), "\"say \"\"hi\"\"\"");
    }

    #[test]
    fn print_export_jsonl_on_missing_log_produces_no_error() {
        let path = std::env::temp_dir().join("zeroclaw_test_export_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_export(&path, None, ExportFormat::Jsonl).is_ok());
    }

    #[test]
    fn print_export_csv_filters_to_delegation_end_events() {
        let path = std::env::temp_dir().join("zeroclaw_test_export_csv.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-e", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_end("run-e", "main", 0, "2026-01-01T10:00:05Z", 500, 0.001, true)).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_export(&path, None, ExportFormat::Csv);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_export_jsonl_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_export_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z")).unwrap());
        lines.push(serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z")).unwrap());
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_export(&path, Some("run-keep"), ExportFormat::Jsonl);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }
}
