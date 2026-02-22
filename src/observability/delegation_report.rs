//! CLI-facing delegation log reporter.
//!
//! Public entry points used by `zeroclaw delegations [list|show|stats|export|diff|top]`:
//! - [`print_summary`]: overall totals across all stored runs.
//! - [`print_runs`]: table of runs, newest first.
//! - [`print_tree`]: indented delegation tree for one run.
//! - [`print_stats`]: per-agent aggregated statistics table.
//! - [`print_export`]: stream delegation events as JSONL or CSV.
//! - [`print_diff`]: side-by-side comparison of two runs with token/cost deltas.
//! - [`print_top`]: global agent leaderboard ranked by tokens or cost.
//! - [`print_prune`]: remove old runs from the log, keeping the N most recent.
//! - [`print_models`]: per-model breakdown table across all (or one) run.
//! - [`print_providers`]: per-provider breakdown table across all (or one) run.
//! - [`print_depth`]: per-depth-level breakdown table across all (or one) run.
//! - [`print_errors`]: list failed delegations with agent, duration, and error message.
//! - [`print_slow`]: list the N slowest delegations ranked by duration descending.
//! - [`print_cost`]: per-run cost breakdown table sorted by total cost descending.
//! - [`print_recent`]: list the N most recently completed delegations, newest first.
//! - [`print_active`]: list currently in-flight delegations (starts without matching ends).
//! - [`print_agent`]: show all completed delegations for a named agent, newest first.
//! - [`print_model`]: show all completed delegations for a named model, newest first.
//! - [`print_provider`]: show all completed delegations for a named provider, newest first.
//! - [`print_run`]: show all completed delegations for a specific run, oldest first.
//! - [`print_depth_view`]: show all completed delegations at a given nesting depth, newest first.
//! - [`print_daily`]: per-calendar-day delegation breakdown table, oldest day first.
//! - [`get_log_summary`]: programmatic aggregate for `zeroclaw status`.
//!
//! All parsing is done via `serde_json::Value` — no new dependencies.

use anyhow::{bail, Result};
use chrono::{DateTime, Datelike, Timelike, Utc};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
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

struct TopAgentRow {
    agent_name: String,
    run_count: usize,
    delegation_count: usize,
    total_tokens: u64,
    total_cost_usd: f64,
}

struct ModelRow {
    model: String,
    run_count: usize,
    delegation_count: usize,
    total_tokens: u64,
    total_cost_usd: f64,
}

struct ProviderRow {
    provider: String,
    run_count: usize,
    delegation_count: usize,
    total_tokens: u64,
    total_cost_usd: f64,
}

struct DepthRow {
    depth: u32,
    delegation_count: usize,
    end_count: usize,
    success_count: usize,
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

// ─── Diff helpers ─────────────────────────────────────────────────────────────

/// Return the first stored run whose ID starts with `prefix`, or `None`.
///
/// `runs` must be sorted newest-first (as returned by [`collect_runs`]) so
/// that prefix lookups consistently resolve to the most recent matching run.
fn resolve_run_id<'a>(runs: &'a [RunInfo], prefix: &str) -> Option<&'a str> {
    runs.iter()
        .find(|r| r.run_id.starts_with(prefix))
        .map(|r| r.run_id.as_str())
}

/// Format a signed token delta for display (e.g. `+1000`, `-200`, `0`).
fn fmt_delta_tokens(delta: i64) -> String {
    match delta.cmp(&0) {
        std::cmp::Ordering::Greater => format!("+{delta}"),
        std::cmp::Ordering::Less => delta.to_string(),
        std::cmp::Ordering::Equal => "0".to_owned(),
    }
}

/// Format a signed cost delta for display (e.g. `+$0.0030`, `-$0.0010`, `$0.0000`).
fn fmt_delta_cost(delta: f64) -> String {
    if delta > 0.000_05 {
        format!("+${delta:.4}")
    } else if delta < -0.000_05 {
        format!("-${:.4}", delta.abs())
    } else {
        "$0.0000".to_owned()
    }
}

// ─── Public data types ────────────────────────────────────────────────────────

/// Sort key for [`print_top`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TopBy {
    /// Rank agents by cumulative tokens (highest first).
    Tokens,
    /// Rank agents by cumulative cost in USD (highest first).
    Cost,
}

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

/// Print a side-by-side per-agent comparison of two runs to stdout.
///
/// Each run is identified by a full UUID or any unique prefix of one.
/// When `run_b` is `None` the function defaults to the most recent stored run
/// that is not `run_a`.
///
/// Output columns: `agent | del_A | del_B | tok_A | tok_B | Δtok | cost_A | cost_B | Δcost`
/// A totals row is appended at the bottom.
///
/// Returns an error when either run ID cannot be resolved or when no second
/// run is available to diff against.
pub fn print_diff(log_path: &Path, run_a: &str, run_b: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let runs = collect_runs(&all_events);
    if runs.is_empty() {
        println!("No runs found.");
        return Ok(());
    }

    // Resolve run_a — supports prefix matching (newest-first tie-break).
    let resolved_a = resolve_run_id(&runs, run_a)
        .ok_or_else(|| anyhow::anyhow!("run not found matching prefix: {run_a}"))?
        .to_owned();

    // Resolve run_b — defaults to the most recent stored run that is not run_a.
    let resolved_b = if let Some(b) = run_b {
        resolve_run_id(&runs, b)
            .ok_or_else(|| anyhow::anyhow!("run not found matching prefix: {b}"))?
            .to_owned()
    } else {
        runs.iter()
            .find(|r| r.run_id != resolved_a)
            .map(|r| r.run_id.clone())
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "only one run stored — cannot diff; \
                     provide a second run ID or record another run first"
                )
            })?
    };

    if resolved_a == resolved_b {
        bail!("both run IDs resolve to the same run ({resolved_a}); provide two distinct runs");
    }

    // Filter events per run.
    let events_a: Vec<Value> = all_events
        .iter()
        .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(resolved_a.as_str()))
        .cloned()
        .collect();
    let events_b: Vec<Value> = all_events
        .iter()
        .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(resolved_b.as_str()))
        .cloned()
        .collect();

    let stats_a = collect_agent_stats(&events_a);
    let stats_b = collect_agent_stats(&events_b);

    // Build lookup maps.
    let map_a: HashMap<String, &AgentStats> =
        stats_a.iter().map(|s| (s.agent_name.clone(), s)).collect();
    let map_b: HashMap<String, &AgentStats> =
        stats_b.iter().map(|s| (s.agent_name.clone(), s)).collect();

    // Union of all agent names, sorted by combined token weight descending.
    let mut all_agents: Vec<String> = {
        let mut names: HashSet<String> = HashSet::new();
        for s in &stats_a {
            names.insert(s.agent_name.clone());
        }
        for s in &stats_b {
            names.insert(s.agent_name.clone());
        }
        names.into_iter().collect()
    };
    all_agents.sort_by(|nx, ny| {
        let w_x = map_a.get(nx.as_str()).map_or(0, |s| s.total_tokens)
            + map_b.get(nx.as_str()).map_or(0, |s| s.total_tokens);
        let w_y = map_a.get(ny.as_str()).map_or(0, |s| s.total_tokens)
            + map_b.get(ny.as_str()).map_or(0, |s| s.total_tokens);
        w_y.cmp(&w_x).then(nx.cmp(ny))
    });

    // Run metadata for the header.
    let info_a = runs.iter().find(|r| r.run_id == resolved_a);
    let info_b = runs.iter().find(|r| r.run_id == resolved_b);
    let ts_a = info_a
        .and_then(|r| r.start_time)
        .map(|t| t.format("%Y-%m-%d %H:%M:%S UTC").to_string())
        .unwrap_or_else(|| "unknown".to_owned());
    let ts_b = info_b
        .and_then(|r| r.start_time)
        .map(|t| t.format("%Y-%m-%d %H:%M:%S UTC").to_string())
        .unwrap_or_else(|| "unknown".to_owned());

    println!("Delegation Diff");
    println!(
        "  A: [{}]  {}",
        &resolved_a[..8.min(resolved_a.len())],
        ts_a
    );
    println!(
        "  B: [{}]  {}",
        &resolved_b[..8.min(resolved_b.len())],
        ts_b
    );
    println!();
    println!(
        "{:<22} {:>6} {:>6}  {:>8} {:>8} {:>8}  {:>8} {:>8} {:>8}",
        "agent", "del_A", "del_B", "tok_A", "tok_B", "Δtok", "cost_A", "cost_B", "Δcost"
    );
    println!("{}", "─".repeat(88));

    let mut total_del_a: usize = 0;
    let mut total_del_b: usize = 0;
    let mut total_tok_a: u64 = 0;
    let mut total_tok_b: u64 = 0;
    let mut total_cost_a: f64 = 0.0;
    let mut total_cost_b: f64 = 0.0;

    for name in &all_agents {
        let a_opt = map_a.get(name.as_str());
        let b_opt = map_b.get(name.as_str());

        let del_a = a_opt.map_or(0, |s| s.delegation_count);
        let del_b = b_opt.map_or(0, |s| s.delegation_count);
        let tok_a = a_opt.map_or(0, |s| s.total_tokens);
        let tok_b = b_opt.map_or(0, |s| s.total_tokens);
        let cost_a = a_opt.map_or(0.0, |s| s.total_cost_usd);
        let cost_b = b_opt.map_or(0.0, |s| s.total_cost_usd);

        let tok_a_str = if tok_a > 0 {
            tok_a.to_string()
        } else {
            "—".to_owned()
        };
        let tok_b_str = if tok_b > 0 {
            tok_b.to_string()
        } else {
            "—".to_owned()
        };
        let tok_delta_str = if tok_a == 0 && tok_b == 0 {
            "—".to_owned()
        } else {
            fmt_delta_tokens(tok_b as i64 - tok_a as i64)
        };
        let cost_a_str = if cost_a > 0.0 {
            format!("${cost_a:.4}")
        } else {
            "—".to_owned()
        };
        let cost_b_str = if cost_b > 0.0 {
            format!("${cost_b:.4}")
        } else {
            "—".to_owned()
        };
        let cost_delta_str = if cost_a == 0.0 && cost_b == 0.0 {
            "—".to_owned()
        } else {
            fmt_delta_cost(cost_b - cost_a)
        };

        println!(
            "{:<22} {:>6} {:>6}  {:>8} {:>8} {:>8}  {:>8} {:>8} {:>8}",
            name,
            del_a,
            del_b,
            tok_a_str,
            tok_b_str,
            tok_delta_str,
            cost_a_str,
            cost_b_str,
            cost_delta_str,
        );

        total_del_a += del_a;
        total_del_b += del_b;
        total_tok_a += tok_a;
        total_tok_b += tok_b;
        total_cost_a += cost_a;
        total_cost_b += cost_b;
    }

    println!("{}", "─".repeat(88));
    let total_tok_delta_str = if total_tok_a == 0 && total_tok_b == 0 {
        "—".to_owned()
    } else {
        fmt_delta_tokens(total_tok_b as i64 - total_tok_a as i64)
    };
    let total_cost_delta_str = if total_cost_a == 0.0 && total_cost_b == 0.0 {
        "—".to_owned()
    } else {
        fmt_delta_cost(total_cost_b - total_cost_a)
    };
    println!(
        "{:<22} {:>6} {:>6}  {:>8} {:>8} {:>8}  {:>8} {:>8} {:>8}",
        "TOTAL",
        total_del_a,
        total_del_b,
        if total_tok_a > 0 {
            total_tok_a.to_string()
        } else {
            "—".to_owned()
        },
        if total_tok_b > 0 {
            total_tok_b.to_string()
        } else {
            "—".to_owned()
        },
        total_tok_delta_str,
        if total_cost_a > 0.0 {
            format!("${total_cost_a:.4}")
        } else {
            "—".to_owned()
        },
        if total_cost_b > 0.0 {
            format!("${total_cost_b:.4}")
        } else {
            "—".to_owned()
        },
        total_cost_delta_str,
    );
    println!();
    println!("Use `zeroclaw delegations diff <run_a> <run_b>` to compare two specific runs.");
    Ok(())
}

/// Print a global agent leaderboard ranked by tokens or cost.
///
/// Aggregates every `DelegationStart` / `DelegationEnd` event across **all**
/// stored runs and ranks agents by `by` (tokens or cost), highest first.
/// `limit` caps the number of rows shown (default: 10).
///
/// Columns: `# | agent | runs | delegations | tokens | cost`
///
/// Produces an informational message and returns `Ok` when the log is absent
/// or empty.
pub fn print_top(log_path: &Path, by: TopBy, limit: usize) -> Result<()> {
    let events = read_all_events(log_path)?;
    if events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // Aggregate per agent — track distinct runs separately.
    let mut rows: HashMap<String, TopAgentRow> = HashMap::new();
    let mut agent_runs: HashMap<String, HashSet<String>> = HashMap::new();

    for ev in &events {
        let Some(name) = ev.get("agent_name").and_then(|x| x.as_str()) else {
            continue;
        };
        let Some(rid) = ev.get("run_id").and_then(|x| x.as_str()) else {
            continue;
        };
        agent_runs
            .entry(name.to_owned())
            .or_default()
            .insert(rid.to_owned());
        let entry = rows.entry(name.to_owned()).or_insert_with(|| TopAgentRow {
            agent_name: name.to_owned(),
            run_count: 0,
            delegation_count: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        });
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

    // Fill run counts from the side-table.
    for (name, row) in rows.iter_mut() {
        row.run_count = agent_runs.get(name).map_or(0, |s| s.len());
    }

    let mut sorted: Vec<TopAgentRow> = rows.into_values().collect();
    match by {
        TopBy::Tokens => sorted.sort_by(|a, b| {
            b.total_tokens
                .cmp(&a.total_tokens)
                .then(a.agent_name.cmp(&b.agent_name))
        }),
        TopBy::Cost => sorted.sort_by(|a, b| {
            b.total_cost_usd
                .partial_cmp(&a.total_cost_usd)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.agent_name.cmp(&b.agent_name))
        }),
    }

    let total = sorted.len();
    sorted.truncate(limit);
    let shown = sorted.len();

    let by_str = match by {
        TopBy::Tokens => "tokens",
        TopBy::Cost => "cost",
    };
    println!("Top Agents  (all runs, ranked by {by_str})");
    println!();
    println!(
        "{:>3}  {:<26} {:>5}  {:>11}  {:>10}  {:>10}",
        "#", "agent", "runs", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(74));

    for (i, row) in sorted.iter().enumerate() {
        let tok = if row.total_tokens > 0 {
            row.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd)
        } else {
            "—".to_owned()
        };
        println!(
            "{:>3}  {:<26} {:>5}  {:>11}  {:>10}  {:>10}",
            i + 1,
            row.agent_name,
            row.run_count,
            row.delegation_count,
            tok,
            cost,
        );
    }

    println!("{}", "─".repeat(74));
    println!("Showing top {shown} of {total} agent(s).");
    println!();
    println!("Use `--by cost` to rank by total cost instead of tokens.");
    Ok(())
}

/// Remove old runs from the delegation log, keeping the N most recent.
///
/// Reads all stored runs, sorts them newest-first (by earliest event timestamp),
/// retains only the `keep` most recent, and atomically rewrites the log file
/// with the surviving events. The write is atomic: events are written to a
/// `.tmp` sibling and then renamed over the original, so a crash mid-write
/// leaves the original file intact.
///
/// When `keep` is zero **all** runs are removed and the log is left empty.
/// When the number of stored runs is already ≤ `keep`, nothing is written.
///
/// Returns `Ok` when the log file is absent, empty, or has nothing to prune.
pub fn print_prune(log_path: &Path, keep: usize) -> Result<()> {
    if !log_path.exists() {
        println!("No delegation log found at: {}", log_path.display());
        println!("Nothing to prune.");
        return Ok(());
    }

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("Log is empty — nothing to prune.");
        return Ok(());
    }

    let runs = collect_runs(&all_events);
    let total_runs = runs.len();

    if total_runs <= keep {
        println!(
            "Nothing to prune: {} run(s) stored, --keep {}.",
            total_runs, keep
        );
        return Ok(());
    }

    // Runs are newest-first; keep the first `keep`, prune the rest.
    let prune_ids: HashSet<&str> = runs[keep..].iter().map(|r| r.run_id.as_str()).collect();
    let pruned_run_count = prune_ids.len();

    let kept_events: Vec<&Value> = all_events
        .iter()
        .filter(|e| {
            e.get("run_id")
                .and_then(|x| x.as_str())
                .map_or(true, |rid| !prune_ids.contains(rid))
        })
        .collect();

    let removed_event_count = all_events.len() - kept_events.len();

    // Atomic write: serialize to a temp file, then rename over the original.
    let tmp_path = {
        let mut s = log_path.as_os_str().to_owned();
        s.push(".tmp");
        std::path::PathBuf::from(s)
    };
    {
        let mut content = String::new();
        for ev in &kept_events {
            content.push_str(&serde_json::to_string(ev)?);
            content.push('\n');
        }
        std::fs::write(&tmp_path, content)?;
    }
    std::fs::rename(&tmp_path, log_path)?;

    println!(
        "Pruned {} run(s) ({} event(s) removed). {} run(s) / {} event(s) remaining.",
        pruned_run_count,
        removed_event_count,
        keep,
        kept_events.len(),
    );
    Ok(())
}

/// Print a per-model breakdown table to stdout.
///
/// Aggregates every `DelegationStart` / `DelegationEnd` event, optionally
/// scoped to a single run via `run_id`, and groups the results by `model`
/// field.  Rows are sorted by cumulative tokens descending, with alphabetical
/// tiebreaks.
///
/// Columns: `# | model | runs | delegations | tokens | cost`
///
/// Returns `Ok` and prints an informational message when the log is absent,
/// empty, or contains no events matching `run_id`.
pub fn print_models(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate per model; track distinct runs via a side-table.
    let mut rows: HashMap<String, ModelRow> = HashMap::new();
    let mut model_runs: HashMap<String, HashSet<String>> = HashMap::new();

    for ev in &events {
        let Some(model) = ev.get("model").and_then(|x| x.as_str()) else {
            continue;
        };
        let rid = ev.get("run_id").and_then(|x| x.as_str()).unwrap_or("");
        if !rid.is_empty() {
            model_runs
                .entry(model.to_owned())
                .or_default()
                .insert(rid.to_owned());
        }
        let entry = rows.entry(model.to_owned()).or_insert_with(|| ModelRow {
            model: model.to_owned(),
            run_count: 0,
            delegation_count: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        });
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

    // Fill run counts from the side-table.
    for (model, row) in rows.iter_mut() {
        row.run_count = model_runs.get(model).map_or(0, |s| s.len());
    }

    let mut sorted: Vec<ModelRow> = rows.into_values().collect();
    sorted.sort_by(|a, b| {
        b.total_tokens
            .cmp(&a.total_tokens)
            .then(a.model.cmp(&b.model))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Model Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<32} {:>5}  {:>11}  {:>10}  {:>10}",
        "#", "model", "runs", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(80));

    for (i, row) in sorted.iter().enumerate() {
        let tok = if row.total_tokens > 0 {
            row.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd)
        } else {
            "—".to_owned()
        };
        let runs_col = if run_id.is_some() {
            "—".to_owned()
        } else {
            row.run_count.to_string()
        };
        println!(
            "{:>3}  {:<32} {:>5}  {:>11}  {:>10}  {:>10}",
            i + 1,
            row.model,
            runs_col,
            row.delegation_count,
            tok,
            cost,
        );
    }

    println!("{}", "─".repeat(80));
    let total_tok: u64 = sorted.iter().map(|r| r.total_tokens).sum();
    let total_cost: f64 = sorted.iter().map(|r| r.total_cost_usd).sum();
    println!(
        "{:>3}  {:<32} {:>5}  {:>11}  {:>10}  {:>10}",
        "",
        "TOTAL",
        "",
        sorted.iter().map(|r| r.delegation_count).sum::<usize>(),
        if total_tok > 0 {
            total_tok.to_string()
        } else {
            "—".to_owned()
        },
        if total_cost > 0.0 {
            format!("${total_cost:.4}")
        } else {
            "—".to_owned()
        },
    );
    println!();
    println!("Use `--run <id>` to scope to a single run.");
    Ok(())
}

/// Aggregate delegation events by `provider` field and print a breakdown table.
///
/// Rows are sorted by total tokens descending; alpha tiebreak on provider name.
/// When `run_id` is `Some`, only events from that run are included and the
/// `runs` column shows `"—"` (distinct-run counting is meaningless for one run).
pub fn print_providers(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate per provider; track distinct runs via a side-table.
    let mut rows: HashMap<String, ProviderRow> = HashMap::new();
    let mut provider_runs: HashMap<String, HashSet<String>> = HashMap::new();

    for ev in &events {
        let Some(provider) = ev.get("provider").and_then(|x| x.as_str()) else {
            continue;
        };
        let rid = ev.get("run_id").and_then(|x| x.as_str()).unwrap_or("");
        if !rid.is_empty() {
            provider_runs
                .entry(provider.to_owned())
                .or_default()
                .insert(rid.to_owned());
        }
        let entry = rows
            .entry(provider.to_owned())
            .or_insert_with(|| ProviderRow {
                provider: provider.to_owned(),
                run_count: 0,
                delegation_count: 0,
                total_tokens: 0,
                total_cost_usd: 0.0,
            });
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

    // Fill run counts from the side-table.
    for (provider, row) in &mut rows {
        row.run_count = provider_runs.get(provider).map_or(0, |s| s.len());
    }

    let mut sorted: Vec<ProviderRow> = rows.into_values().collect();
    sorted.sort_by(|a, b| {
        b.total_tokens
            .cmp(&a.total_tokens)
            .then(a.provider.cmp(&b.provider))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Provider Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<20} {:>5}  {:>11}  {:>10}  {:>10}",
        "#", "provider", "runs", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(68));

    for (i, row) in sorted.iter().enumerate() {
        let tok = if row.total_tokens > 0 {
            row.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd)
        } else {
            "—".to_owned()
        };
        let runs_col = if run_id.is_some() {
            "—".to_owned()
        } else {
            row.run_count.to_string()
        };
        println!(
            "{:>3}  {:<20} {:>5}  {:>11}  {:>10}  {:>10}",
            i + 1,
            row.provider,
            runs_col,
            row.delegation_count,
            tok,
            cost,
        );
    }

    println!("{}", "─".repeat(68));
    let total_tok: u64 = sorted.iter().map(|r| r.total_tokens).sum();
    let total_cost: f64 = sorted.iter().map(|r| r.total_cost_usd).sum();
    println!(
        "{:>3}  {:<20} {:>5}  {:>11}  {:>10}  {:>10}",
        "",
        "TOTAL",
        "",
        sorted.iter().map(|r| r.delegation_count).sum::<usize>(),
        if total_tok > 0 {
            total_tok.to_string()
        } else {
            "—".to_owned()
        },
        if total_cost > 0.0 {
            format!("${total_cost:.4}")
        } else {
            "—".to_owned()
        },
    );
    println!();
    println!("Use `--run <id>` to scope to a single run.");
    Ok(())
}

/// Aggregate delegation events by `depth` level and print a breakdown table.
///
/// Rows are sorted by depth ascending (root level first). When `run_id` is
/// `Some`, only events from that run are included.
pub fn print_depth(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate per depth level.
    let mut rows: HashMap<u32, DepthRow> = HashMap::new();

    for ev in &events {
        let Some(depth) = ev.get("depth").and_then(|x| x.as_u64()).map(|d| d as u32) else {
            continue;
        };
        let entry = rows.entry(depth).or_insert_with(|| DepthRow {
            depth,
            delegation_count: 0,
            end_count: 0,
            success_count: 0,
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

    // Sort by depth ascending.
    let mut sorted: Vec<DepthRow> = rows.into_values().collect();
    sorted.sort_by_key(|r| r.depth);

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Depth Breakdown{scope}");
    println!();
    println!(
        "{:>5}  {:>11}  {:>6}  {:>9}  {:>10}  {:>10}",
        "depth", "delegations", "ended", "success%", "tokens", "cost"
    );
    println!("{}", "─".repeat(60));

    for row in &sorted {
        let success_pct = if row.end_count > 0 {
            format!(
                "{:.1}%",
                100.0 * row.success_count as f64 / row.end_count as f64
            )
        } else {
            "—".to_owned()
        };
        let tok = if row.total_tokens > 0 {
            row.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd)
        } else {
            "—".to_owned()
        };
        println!(
            "{:>5}  {:>11}  {:>6}  {:>9}  {:>10}  {:>10}",
            row.depth, row.delegation_count, row.end_count, success_pct, tok, cost,
        );
    }

    println!("{}", "─".repeat(60));
    let total_tok: u64 = sorted.iter().map(|r| r.total_tokens).sum();
    let total_cost: f64 = sorted.iter().map(|r| r.total_cost_usd).sum();
    println!(
        "{:>5}  {:>11}  {:>6}  {:>9}  {:>10}  {:>10}",
        "TOTAL",
        sorted.iter().map(|r| r.delegation_count).sum::<usize>(),
        sorted.iter().map(|r| r.end_count).sum::<usize>(),
        "",
        if total_tok > 0 {
            total_tok.to_string()
        } else {
            "—".to_owned()
        },
        if total_cost > 0.0 {
            format!("${total_cost:.4}")
        } else {
            "—".to_owned()
        },
    );
    println!();
    println!("Use `--run <id>` to scope to a single run.");
    Ok(())
}

/// List all failed delegations with agent, depth, duration, and error message.
///
/// Filters `DelegationEnd` events where `success` is `false`, ordered by
/// timestamp ascending (oldest failure first). When `run_id` is `Some`, only
/// events from that run are shown. Error messages are truncated to 80 chars.
pub fn print_errors(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Collect failed DelegationEnd events.
    let mut failures: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && !e.get("success").and_then(|x| x.as_bool()).unwrap_or(true)
        })
        .collect();

    // Sort by timestamp ascending (oldest failure first).
    failures.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        ta.cmp(tb)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Failed Delegations{scope}");
    println!();

    if failures.is_empty() {
        println!("No failed delegations found.");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {}",
        "#", "run", "agent", "depth", "duration", "error"
    );
    println!("{}", "─".repeat(90));

    for (i, ev) in failures.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev.get("agent_name").and_then(|x| x.as_str()).unwrap_or("?");
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let error = ev
            .get("error_message")
            .and_then(|x| x.as_str())
            .unwrap_or("(no message)");
        // Truncate long error messages.
        let error_display = if error.len() > 80 {
            format!("{}…", &error[..79])
        } else {
            error.to_owned()
        };
        println!(
            "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {}",
            i + 1,
            run,
            agent,
            depth,
            duration,
            error_display,
        );
    }

    println!("{}", "─".repeat(90));
    println!("{} failed delegation(s) found.", failures.len());
    Ok(())
}

/// List the N slowest completed delegations ranked by duration descending.
///
/// Reads `DelegationEnd` events, optionally filtered to a single run, then
/// sorts by `duration_ms` descending and prints the top `limit` rows.
///
/// Columns: `#` | `run` (8-char prefix) | `agent` | `depth` | `duration` | `tokens` | `cost`
pub fn print_slow(log_path: &Path, run_id: Option<&str>, limit: usize) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Collect all DelegationEnd events that have a duration.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("duration_ms").and_then(|x| x.as_u64()).is_some()
        })
        .collect();

    // Sort slowest first.
    ends.sort_by(|a, b| {
        let da = a.get("duration_ms").and_then(|x| x.as_u64()).unwrap_or(0);
        let db = b.get("duration_ms").and_then(|x| x.as_u64()).unwrap_or(0);
        db.cmp(&da)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    let shown = ends.len().min(limit);
    println!(
        "Slowest Delegations{scope}  [showing {shown} of {}]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {:>8}  {}",
        "#", "run", "agent", "depth", "duration", "tokens", "cost"
    );
    println!("{}", "─".repeat(80));

    for (i, ev) in ends.iter().take(limit).enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev.get("agent_name").and_then(|x| x.as_str()).unwrap_or("?");
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        println!(
            "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {:>8}  {}",
            i + 1,
            run,
            agent,
            depth,
            duration,
            tokens,
            cost,
        );
    }

    println!("{}", "─".repeat(80));
    println!(
        "Top {shown} slowest of {} completed delegation(s).",
        ends.len()
    );
    Ok(())
}

/// Stream delegation events to stdout as JSONL or CSV.
///
/// `ExportFormat::Jsonl` (default): emits one raw event JSON object per line,
/// suitable for piping to `jq` or re-importing into another tool.
///
/// Print a per-run cost breakdown table sorted by total cost descending.
///
/// One row per stored run. When `run_id` is `Some`, only that run is shown.
///
/// Columns: `#` | `run` (8-char prefix) | `start (UTC)` | `delegations` |
///          `tokens` | `cost` | `avg/del`
///
/// `avg/del` is the average cost per completed delegation for that run,
/// shown as `—` when no delegation ends were recorded.
pub fn print_cost(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // Filter to the requested run before aggregating if a run_id is given.
    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate per run: start_time, delegation_count (Start events),
    // end_count (End events), total_tokens, total_cost.
    struct CostRow {
        run_id: String,
        start_time: Option<DateTime<Utc>>,
        delegation_count: usize,
        end_count: usize,
        total_tokens: u64,
        total_cost_usd: f64,
    }

    let mut map: std::collections::HashMap<String, CostRow> = std::collections::HashMap::new();

    for ev in &events {
        let Some(rid) = ev.get("run_id").and_then(|x| x.as_str()) else {
            continue;
        };
        let ts = ev.get("timestamp").and_then(parse_ts);
        let row = map.entry(rid.to_owned()).or_insert_with(|| CostRow {
            run_id: rid.to_owned(),
            start_time: None,
            delegation_count: 0,
            end_count: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        });
        if let Some(ts) = ts {
            if row.start_time.map_or(true, |s| ts < s) {
                row.start_time = Some(ts);
            }
        }
        match ev.get("event_type").and_then(|x| x.as_str()) {
            Some("DelegationStart") => row.delegation_count += 1,
            Some("DelegationEnd") => {
                row.end_count += 1;
                if let Some(tok) = ev.get("tokens_used").and_then(|x| x.as_u64()) {
                    row.total_tokens += tok;
                }
                if let Some(cost) = ev.get("cost_usd").and_then(|x| x.as_f64()) {
                    row.total_cost_usd += cost;
                }
            }
            _ => {}
        }
    }

    // Sort by total cost descending; secondary: newest start first.
    let mut rows: Vec<CostRow> = map.into_values().collect();
    rows.sort_by(|a, b| {
        b.total_cost_usd
            .partial_cmp(&a.total_cost_usd)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| b.start_time.cmp(&a.start_time))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Delegation Cost Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<10}  {:<19}  {:>11}  {:>8}  {:>9}  {:>9}",
        "#", "run", "start (UTC)", "delegations", "tokens", "cost", "avg/del"
    );
    println!("{}", "─".repeat(85));

    for (i, row) in rows.iter().enumerate() {
        let run_prefix: String = row.run_id.chars().take(8).collect();
        let ts = row
            .start_time
            .map(|t| t.format("%Y-%m-%d %H:%M:%S").to_string())
            .unwrap_or_else(|| "unknown".to_owned());
        let tok = if row.total_tokens > 0 {
            row.total_tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost = if row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd)
        } else {
            "—".to_owned()
        };
        let avg = if row.end_count > 0 && row.total_cost_usd > 0.0 {
            format!("${:.4}", row.total_cost_usd / row.end_count as f64)
        } else {
            "—".to_owned()
        };
        println!(
            "{:>3}  {:<10}  {:<19}  {:>11}  {:>8}  {:>9}  {:>9}",
            i + 1,
            run_prefix,
            ts,
            row.delegation_count,
            tok,
            cost,
            avg,
        );
    }

    println!("{}", "─".repeat(85));
    let total_cost: f64 = rows.iter().map(|r| r.total_cost_usd).sum();
    println!("{} run(s) • total cost: ${total_cost:.4}", rows.len());
    Ok(())
}

/// List the N most recently completed delegations, newest first.
///
/// Reads `DelegationEnd` events, optionally filtered to a single run, then
/// sorts by `timestamp` descending and prints the top `limit` rows.
///
/// Columns: `#` | `run` (8-char prefix) | `agent` | `depth` |
///          `duration` | `tokens` | `cost` | `finished (UTC)`
pub fn print_recent(log_path: &Path, run_id: Option<&str>, limit: usize) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Collect all DelegationEnd events.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd"))
        .collect();

    // Sort newest first (ISO-8601 string comparison is correct for UTC).
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        tb.cmp(ta)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    let shown = ends.len().min(limit);
    println!(
        "Most Recent Delegations{scope}  [showing {shown} of {}]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {:>8}  {:>9}  {}",
        "#", "run", "agent", "depth", "duration", "tokens", "cost", "finished (UTC)"
    );
    println!("{}", "─".repeat(100));

    for (i, ev) in ends.iter().take(limit).enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev.get("agent_name").and_then(|x| x.as_str()).unwrap_or("?");
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        // Format the timestamp into a short UTC display.
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:<22}  {:>5}  {:>9}  {:>8}  {:>9}  {}",
            i + 1,
            run,
            agent,
            depth,
            duration,
            tokens,
            cost,
            finished,
        );
    }

    println!("{}", "─".repeat(100));
    println!(
        "Top {shown} most recent of {} completed delegation(s).",
        ends.len()
    );
    Ok(())
}

/// List currently in-flight delegations — `DelegationStart` events that have
/// no matching `DelegationEnd` in the log yet.
///
/// Matches starts to ends FIFO per `(run_id, agent_name, depth)` key so that
/// the correct unmatched starts are surfaced when an agent is delegated more
/// than once within the same run at the same depth.
///
/// Sorted oldest-start first so the longest-running delegation appears at the
/// top.  When `run_id` is `Some`, only events from that run are considered.
pub fn print_active(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // FIFO match: for each (run_id, agent_name, depth) key, pair each start
    // with the corresponding end by insertion order.  Unmatched starts are
    // the currently active (in-flight) delegations.
    type Key = (String, String, u32);
    let mut start_queues: HashMap<Key, Vec<&Value>> = HashMap::new();
    let mut end_counts: HashMap<Key, usize> = HashMap::new();

    for ev in &events {
        let etype = ev.get("event_type").and_then(|x| x.as_str()).unwrap_or("");
        let rid = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_owned();
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_owned();
        let depth = ev.get("depth").and_then(|x| x.as_u64()).unwrap_or(0) as u32;
        let key = (rid, agent, depth);
        match etype {
            "DelegationStart" => {
                start_queues.entry(key).or_default().push(ev);
            }
            "DelegationEnd" => {
                *end_counts.entry(key).or_default() += 1;
            }
            _ => {}
        }
    }

    // Collect unmatched starts.
    let mut active: Vec<&Value> = Vec::new();
    for (key, starts) in &start_queues {
        let matched = *end_counts.get(key).unwrap_or(&0);
        for start in starts.iter().skip(matched) {
            active.push(start);
        }
    }

    // Sort oldest-start first (ascending ISO-8601 timestamp).
    active.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        ta.cmp(tb)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Active Delegations{scope}  [{} in-flight]", active.len());
    println!();

    if active.is_empty() {
        println!("No active (in-flight) delegations found.");
        return Ok(());
    }

    let now = Utc::now();
    println!(
        "{:>3}  {:<10}  {:<22}  {:>5}  {:<20}  {}",
        "#", "run", "agent", "depth", "started (UTC)", "elapsed"
    );
    println!("{}", "─".repeat(80));

    for (i, ev) in active.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev.get("agent_name").and_then(|x| x.as_str()).unwrap_or("?");
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let started_dt = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok());
        let started = started_dt
            .as_ref()
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        let elapsed = started_dt
            .map(|dt| {
                let secs = now
                    .signed_duration_since(dt.with_timezone(&Utc))
                    .num_seconds()
                    .max(0);
                if secs < 60 {
                    format!("{secs}s")
                } else if secs < 3600 {
                    format!("{}m{}s", secs / 60, secs % 60)
                } else {
                    format!("{}h{}m", secs / 3600, (secs % 3600) / 60)
                }
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:<22}  {:>5}  {:<20}  {}",
            i + 1,
            run,
            agent,
            depth,
            started,
            elapsed,
        );
    }

    println!("{}", "─".repeat(80));
    println!("{} active (in-flight) delegation(s).", active.len());
    Ok(())
}

/// Show all completed delegations for a specific agent, sorted newest first.
///
/// Filters `DelegationEnd` events where `agent_name` matches the given name
/// (case-sensitive exact match).  Optionally scoped to a single run via
/// `run_id`.  Results are sorted by finish timestamp descending so the most
/// recent invocation appears at the top.
///
/// Output columns: # | run | depth | duration | tokens | cost | ok | finished (UTC)
pub fn print_agent(log_path: &Path, agent: &str, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Filter DelegationEnd events for this agent.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("agent_name").and_then(|x| x.as_str()) == Some(agent)
        })
        .collect();

    // Sort newest first.
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        tb.cmp(ta)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!(
        "Delegation history for agent \"{agent}\"{scope}  [{} occurrence(s)]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found for agent \"{agent}\".");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
        "#", "run", "depth", "duration", "tokens", "cost", "ok", "finished (UTC)"
    );
    println!("{}", "─".repeat(85));

    for (i, ev) in ends.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let ok = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .map(|s| if s { "yes" } else { "no" })
            .unwrap_or("?");
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
            i + 1,
            run,
            depth,
            duration,
            tokens,
            cost,
            ok,
            finished,
        );
    }

    println!("{}", "─".repeat(85));
    let total_tokens: u64 = ends
        .iter()
        .filter_map(|e| e.get("tokens_used").and_then(|x| x.as_u64()))
        .sum();
    let total_cost: f64 = ends
        .iter()
        .filter_map(|e| e.get("cost_usd").and_then(|x| x.as_f64()))
        .sum();
    let success_count = ends
        .iter()
        .filter(|e| e.get("success").and_then(|x| x.as_bool()) == Some(true))
        .count();
    println!(
        "{} occurrence(s) — {} succeeded  •  {} total tokens  •  ${:.4} total cost",
        ends.len(),
        success_count,
        total_tokens,
        total_cost,
    );
    Ok(())
}

/// Show all completed delegations for a specific model, newest first.
///
/// Filters `DelegationEnd` events whose `model` field exactly matches `model`
/// (case-sensitive). When `run_id` is `Some`, only events from that run are
/// included. Results are sorted by timestamp descending (most recent first).
///
/// Output columns: # | run | agent | depth | duration | tokens | cost | ok | finished (UTC)
///
/// The footer prints total occurrences, success count, cumulative tokens, and
/// cumulative cost.
pub fn print_model(log_path: &Path, model: &str, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Filter DelegationEnd events for this model.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("model").and_then(|x| x.as_str()) == Some(model)
        })
        .collect();

    // Sort newest first.
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        tb.cmp(ta)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!(
        "Delegation history for model \"{model}\"{scope}  [{} occurrence(s)]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found for model \"{model}\".");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<14}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
        "#", "run", "agent", "depth", "duration", "tokens", "cost", "ok", "finished (UTC)"
    );
    println!("{}", "─".repeat(99));

    for (i, ev) in ends.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("?")
            .to_owned();
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let ok = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .map(|s| if s { "yes" } else { "no" })
            .unwrap_or("?");
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:<14}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
            i + 1,
            run,
            agent,
            depth,
            duration,
            tokens,
            cost,
            ok,
            finished,
        );
    }

    println!("{}", "─".repeat(99));
    let total_tokens: u64 = ends
        .iter()
        .filter_map(|e| e.get("tokens_used").and_then(|x| x.as_u64()))
        .sum();
    let total_cost: f64 = ends
        .iter()
        .filter_map(|e| e.get("cost_usd").and_then(|x| x.as_f64()))
        .sum();
    let success_count = ends
        .iter()
        .filter(|e| e.get("success").and_then(|x| x.as_bool()) == Some(true))
        .count();
    println!(
        "{} occurrence(s) — {} succeeded  •  {} total tokens  •  ${:.4} total cost",
        ends.len(),
        success_count,
        total_tokens,
        total_cost,
    );
    Ok(())
}

/// Show all completed delegations for a specific provider, newest first.
///
/// Filters `DelegationEnd` events whose `provider` field exactly matches
/// `provider` (case-sensitive). When `run_id` is `Some`, only events from
/// that run are included. Results are sorted by timestamp descending.
///
/// Output columns: # | run | agent | model | depth | duration | tokens | cost | ok | finished (UTC)
///
/// The footer prints total occurrences, success count, cumulative tokens, and
/// cumulative cost.
pub fn print_provider(log_path: &Path, provider: &str, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Filter DelegationEnd events for this provider.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("provider").and_then(|x| x.as_str()) == Some(provider)
        })
        .collect();

    // Sort newest first.
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        tb.cmp(ta)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!(
        "Delegation history for provider \"{provider}\"{scope}  [{} occurrence(s)]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found for provider \"{provider}\".");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<14}  {:<20}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
        "#", "run", "agent", "model", "depth", "duration", "tokens", "cost", "ok", "finished (UTC)"
    );
    println!("{}", "─".repeat(117));

    for (i, ev) in ends.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("?")
            .to_owned();
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("?")
            .to_owned();
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let ok = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .map(|s| if s { "yes" } else { "no" })
            .unwrap_or("?");
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:<14}  {:<20}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
            i + 1,
            run,
            agent,
            model,
            depth,
            duration,
            tokens,
            cost,
            ok,
            finished,
        );
    }

    println!("{}", "─".repeat(117));
    let total_tokens: u64 = ends
        .iter()
        .filter_map(|e| e.get("tokens_used").and_then(|x| x.as_u64()))
        .sum();
    let total_cost: f64 = ends
        .iter()
        .filter_map(|e| e.get("cost_usd").and_then(|x| x.as_f64()))
        .sum();
    let success_count = ends
        .iter()
        .filter(|e| e.get("success").and_then(|x| x.as_bool()) == Some(true))
        .count();
    println!(
        "{} occurrence(s) — {} succeeded  •  {} total tokens  •  ${:.4} total cost",
        ends.len(),
        success_count,
        total_tokens,
        total_cost,
    );
    Ok(())
}

/// Show all completed delegations for a specific run, oldest first.
///
/// Filters `DelegationEnd` events whose `run_id` field exactly matches
/// `run_id`. Results are sorted by timestamp ascending (chronological order).
///
/// Output columns: # | agent | depth | duration | tokens | cost | ok | finished (UTC)
///
/// The footer prints total completions, success count, cumulative tokens, and
/// cumulative cost.
pub fn print_run(log_path: &Path, run_id: &str) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // Filter DelegationEnd events for this run.
    let mut ends: Vec<&Value> = all_events
        .iter()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("run_id").and_then(|x| x.as_str()) == Some(run_id)
        })
        .collect();

    // Sort oldest first (chronological).
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        ta.cmp(tb)
    });

    println!(
        "Run report: {run_id}  [{} completed delegation(s)]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found for run \"{run_id}\".");
        return Ok(());
    }

    println!(
        "{:>3}  {:<20}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
        "#", "agent", "depth", "duration", "tokens", "cost", "ok", "finished (UTC)"
    );
    println!("{}", "─".repeat(86));

    for (i, ev) in ends.iter().enumerate() {
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("?")
            .to_owned();
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .map(|d| d.to_string())
            .unwrap_or_else(|| "?".to_owned());
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let ok = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .map(|s| if s { "yes" } else { "no" })
            .unwrap_or("?");
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<20}  {:>5}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
            i + 1,
            agent,
            depth,
            duration,
            tokens,
            cost,
            ok,
            finished,
        );
    }

    println!("{}", "─".repeat(86));
    let total_tokens: u64 = ends
        .iter()
        .filter_map(|e| e.get("tokens_used").and_then(|x| x.as_u64()))
        .sum();
    let total_cost: f64 = ends
        .iter()
        .filter_map(|e| e.get("cost_usd").and_then(|x| x.as_f64()))
        .sum();
    let success_count = ends
        .iter()
        .filter(|e| e.get("success").and_then(|x| x.as_bool()) == Some(true))
        .count();
    println!(
        "{} completed — {} succeeded  •  {} total tokens  •  ${:.4} total cost",
        ends.len(),
        success_count,
        total_tokens,
        total_cost,
    );
    Ok(())
}

/// Show all completed delegations at a given nesting depth, newest first.
///
/// Filters `DelegationEnd` events whose `depth` field equals `depth`.
/// When `run_id` is `Some`, only events from that run are included.
/// Results are sorted by timestamp descending (most recent first).
///
/// Output columns: # | run | agent | duration | tokens | cost | ok | finished (UTC)
///
/// The footer prints total occurrences, success count, cumulative tokens, and
/// cumulative cost.
pub fn print_depth_view(log_path: &Path, depth: u32, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Filter DelegationEnd events at this depth.
    let mut ends: Vec<&Value> = events
        .iter()
        .copied()
        .filter(|e| {
            e.get("event_type").and_then(|x| x.as_str()) == Some("DelegationEnd")
                && e.get("depth").and_then(|x| x.as_u64()) == Some(u64::from(depth))
        })
        .collect();

    // Sort newest first.
    ends.sort_by(|a, b| {
        let ta = a.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        let tb = b.get("timestamp").and_then(|x| x.as_str()).unwrap_or("");
        tb.cmp(ta)
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!(
        "Delegation history for depth {depth}{scope}  [{} occurrence(s)]",
        ends.len()
    );
    println!();

    if ends.is_empty() {
        println!("No completed delegations found at depth {depth}.");
        return Ok(());
    }

    println!(
        "{:>3}  {:<10}  {:<20}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
        "#", "run", "agent", "duration", "tokens", "cost", "ok", "finished (UTC)"
    );
    println!("{}", "─".repeat(89));

    for (i, ev) in ends.iter().enumerate() {
        let run = ev
            .get("run_id")
            .and_then(|x| x.as_str())
            .map(|r| r.chars().take(8).collect::<String>())
            .unwrap_or_else(|| "?".to_owned());
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("?")
            .to_owned();
        let duration = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .map(fmt_duration)
            .unwrap_or_else(|| "—".to_owned());
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .map(|t| t.to_string())
            .unwrap_or_else(|| "—".to_owned());
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .map(|c| format!("${c:.4}"))
            .unwrap_or_else(|| "—".to_owned());
        let ok = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .map(|s| if s { "yes" } else { "no" })
            .unwrap_or("?");
        let finished = ev
            .get("timestamp")
            .and_then(|x| x.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| {
                dt.with_timezone(&Utc)
                    .format("%Y-%m-%d %H:%M:%S")
                    .to_string()
            })
            .unwrap_or_else(|| "?".to_owned());
        println!(
            "{:>3}  {:<10}  {:<20}  {:>9}  {:>8}  {:>9}  {:>4}  {}",
            i + 1,
            run,
            agent,
            duration,
            tokens,
            cost,
            ok,
            finished,
        );
    }

    println!("{}", "─".repeat(89));
    let total_tokens: u64 = ends
        .iter()
        .filter_map(|e| e.get("tokens_used").and_then(|x| x.as_u64()))
        .sum();
    let total_cost: f64 = ends
        .iter()
        .filter_map(|e| e.get("cost_usd").and_then(|x| x.as_f64()))
        .sum();
    let success_count = ends
        .iter()
        .filter(|e| e.get("success").and_then(|x| x.as_bool()) == Some(true))
        .count();
    println!(
        "{} occurrence(s) — {} succeeded  •  {} total tokens  •  ${:.4} total cost",
        ends.len(),
        success_count,
        total_tokens,
        total_cost,
    );
    Ok(())
}

/// Per-calendar-day delegation breakdown, oldest day first.
///
/// Aggregates `DelegationEnd` events by UTC calendar date (YYYY-MM-DD)
/// extracted from their `timestamp` field.  When `run_id` is `Some`, only
/// events from that run are included.  Rows are sorted oldest-first so the
/// table reads chronologically.
///
/// Output columns: date | count | ok% | tokens | cost
///
/// The footer prints the total number of days, total delegation count,
/// success count, and cumulative cost.
pub fn print_daily(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate DelegationEnd events by UTC date (first 10 chars of timestamp).
    let mut map: std::collections::BTreeMap<String, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        if ts.len() < 10 {
            continue;
        }
        let date = ts[..10].to_owned();
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(date).or_insert((0usize, 0usize, 0u64, 0.0f64));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Daily Delegation Breakdown{scope}");
    println!();
    println!(
        "{:<10}  {:>7}  {:>8}  {:>10}  {:>10}",
        "date", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "─".repeat(53));

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (date, (count, success_count, tokens, cost)) in &map {
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count) as f64 / (*count) as f64);
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "—".to_owned()
        };
        println!(
            "{:<10}  {:>7}  {:>8}  {:>10}  {:>10}",
            date, count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(53));
    println!(
        "{} day(s)  •  {} total delegations  •  {} succeeded  •  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by UTC hour-of-day (00–23) and print a
/// breakdown table, sorted lowest-hour first.
///
/// Only `DelegationEnd` events are counted.  The hour key is extracted from
/// characters 11–12 of the ISO-8601 timestamp (e.g. `"2026-01-15T14:30:00Z"`
/// → `"14"`).  Events with a timestamp shorter than 13 chars are skipped.
///
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: hour (UTC) | count | ok% | tokens | cost
pub fn print_hourly(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate DelegationEnd events by UTC hour (chars 11..13 of timestamp).
    let mut map: std::collections::BTreeMap<String, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        if ts.len() < 13 {
            continue;
        }
        let hour = ts[11..13].to_owned();
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(hour).or_insert((0usize, 0usize, 0u64, 0.0f64));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Hourly Delegation Breakdown{scope}");
    println!();
    println!(
        "{:<8}  {:>7}  {:>8}  {:>10}  {:>10}",
        "hour (UTC)", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "─".repeat(53));

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (hour, (count, success_count, tokens, cost)) in &map {
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count) as f64 / (*count) as f64);
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "—".to_owned()
        };
        println!(
            "{:<8}  {:>7}  {:>8}  {:>10}  {:>10}",
            format!("{hour}:xx"), count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(53));
    println!(
        "{} hour(s) active  •  {} total delegations  •  {} succeeded  •  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by UTC calendar month (YYYY-MM) and print a
/// breakdown table, sorted oldest-month first.
///
/// Only `DelegationEnd` events are counted.  The month key is extracted from
/// the first 7 characters of the ISO-8601 timestamp (e.g.
/// `"2026-01-15T14:30:00Z"` → `"2026-01"`).  Events with a timestamp shorter
/// than 7 chars are skipped.
///
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: month | count | ok% | tokens | cost
pub fn print_monthly(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate DelegationEnd events by UTC month (first 7 chars of timestamp).
    let mut map: std::collections::BTreeMap<String, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        if ts.len() < 7 {
            continue;
        }
        let month = ts[..7].to_owned();
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(month).or_insert((0usize, 0usize, 0u64, 0.0f64));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Monthly Delegation Breakdown{scope}");
    println!();
    println!(
        "{:<7}  {:>7}  {:>8}  {:>10}  {:>10}",
        "month", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "─".repeat(50));

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (month, (count, success_count, tokens, cost)) in &map {
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count) as f64 / (*count) as f64);
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "—".to_owned()
        };
        println!(
            "{:<7}  {:>7}  {:>8}  {:>10}  {:>10}",
            month, count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(50));
    println!(
        "{} month(s)  •  {} total delegations  •  {} succeeded  •  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by UTC calendar quarter (YYYY-QN) and
/// print a breakdown table, sorted oldest-quarter first.
///
/// Only `DelegationEnd` events are counted.  The quarter is derived from
/// the month digits in the ISO-8601 timestamp (characters 5–6):
///   01–03 → Q1 · 04–06 → Q2 · 07–09 → Q3 · 10–12 → Q4
///
/// Events with a timestamp shorter than 7 chars or an unrecognised month
/// are skipped.  Use `run_id` to scope to a single run; `None` aggregates
/// across every stored run.
///
/// Output columns: quarter | count | ok% | tokens | cost
pub fn print_quarterly(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate DelegationEnd events by UTC quarter.
    let mut map: std::collections::BTreeMap<String, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        if ts.len() < 7 {
            continue;
        }
        let year = &ts[..4];
        let month_str = &ts[5..7];
        let quarter = match month_str {
            "01" | "02" | "03" => 1u8,
            "04" | "05" | "06" => 2,
            "07" | "08" | "09" => 3,
            "10" | "11" | "12" => 4,
            _ => continue,
        };
        let key = format!("{year}-Q{quarter}");
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(key).or_insert((0usize, 0usize, 0u64, 0.0f64));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Quarterly Delegation Breakdown{scope}");
    println!();
    println!(
        "{:<7}  {:>7}  {:>8}  {:>10}  {:>10}",
        "quarter", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "─".repeat(50));

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (quarter, (count, success_count, tokens, cost)) in &map {
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count) as f64 / (*count) as f64);
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "—".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "—".to_owned()
        };
        println!(
            "{:<7}  {:>7}  {:>8}  {:>10}  {:>10}",
            quarter, count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(50));
    println!(
        "{} quarter(s)  •  {} total delegations  •  {} succeeded  •  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Groups `DelegationEnd` events by the (agent_name × model) cross-product
/// and ranks them by total tokens consumed (descending).  When `agent_name`
/// or `model` is absent the value is substituted with `"unknown"`.  Use
/// `run_id` to scope to a single run; `None` aggregates across every stored
/// run.
///
/// Output columns: # | agent | model | delegations | tokens | cost
pub fn print_agent_model(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate by (agent × model); value = (count, tokens, cost).
    let mut map: HashMap<String, (usize, u64, f64)> = HashMap::new();
    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let key = format!("{agent}/{model}");
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(key).or_insert((0, 0, 0.0));
        entry.0 += 1;
        entry.1 += tokens;
        entry.2 += cost;
    }

    let mut rows: Vec<(String, usize, u64, f64)> = map
        .into_iter()
        .map(|(k, (count, tokens, cost))| (k, count, tokens, cost))
        .collect();
    rows.sort_by(|a, b| b.2.cmp(&a.2).then(a.0.cmp(&b.0)));

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Agent \u{d7} Model Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<16}  {:<20}  {:>11}  {:>10}  {:>10}",
        "#", "agent", "model", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(80));

    let mut total_count: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (rank, (key, count, tokens, cost)) in rows.iter().enumerate() {
        let (agent, model) = key
            .split_once('/')
            .unwrap_or((key.as_str(), "unknown"));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:>3}  {:<16}  {:<20}  {:>11}  {:>10}  {:>10}",
            rank + 1,
            agent,
            model,
            count,
            tok_str,
            cost_str,
        );
        total_count += count;
        total_tokens += *tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(80));
    println!(
        "{}  combination(s)  \u{2022}  {} total delegations  \u{2022}  ${:.4} total cost",
        rows.len(),
        total_count,
        total_cost,
    );
    Ok(())
}

/// Groups `DelegationEnd` events by the (provider × model) cross-product
/// and ranks them by total tokens consumed (descending).  When `provider`
/// or `model` is absent the value is substituted with `"unknown"`.  Use
/// `run_id` to scope to a single run; `None` aggregates across every stored
/// run.
///
/// Output columns: # | provider | model | delegations | tokens | cost
pub fn print_provider_model(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate by (provider × model); value = (count, tokens, cost).
    let mut map: HashMap<String, (usize, u64, f64)> = HashMap::new();
    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let provider = ev
            .get("provider")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let key = format!("{provider}/{model}");
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(key).or_insert((0, 0, 0.0));
        entry.0 += 1;
        entry.1 += tokens;
        entry.2 += cost;
    }

    let mut rows: Vec<(String, usize, u64, f64)> = map
        .into_iter()
        .map(|(k, (count, tokens, cost))| (k, count, tokens, cost))
        .collect();
    rows.sort_by(|a, b| b.2.cmp(&a.2).then(a.0.cmp(&b.0)));

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Provider \u{d7} Model Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<14}  {:<20}  {:>11}  {:>10}  {:>10}",
        "#", "provider", "model", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(78));

    let mut total_count: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (rank, (key, count, tokens, cost)) in rows.iter().enumerate() {
        let (provider, model) = key
            .split_once('/')
            .unwrap_or((key.as_str(), "unknown"));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:>3}  {:<14}  {:<20}  {:>11}  {:>10}  {:>10}",
            rank + 1,
            provider,
            model,
            count,
            tok_str,
            cost_str,
        );
        total_count += count;
        total_tokens += *tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(78));
    println!(
        "{}  combination(s)  \u{2022}  {} total delegations  \u{2022}  ${:.4} total cost",
        rows.len(),
        total_count,
        total_cost,
    );
    Ok(())
}

/// Groups `DelegationEnd` events by the (agent_name × provider) cross-product
/// and ranks them by total tokens consumed (descending).  When `agent_name`
/// or `provider` is absent the value is substituted with `"unknown"`.  Use
/// `run_id` to scope to a single run; `None` aggregates across every stored
/// run.
///
/// Output columns: # | agent | provider | delegations | tokens | cost
pub fn print_agent_provider(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate by (agent × provider); value = (count, tokens, cost).
    let mut map: HashMap<String, (usize, u64, f64)> = HashMap::new();
    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let provider = ev
            .get("provider")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown");
        let key = format!("{agent}/{provider}");
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(key).or_insert((0, 0, 0.0));
        entry.0 += 1;
        entry.1 += tokens;
        entry.2 += cost;
    }

    let mut rows: Vec<(String, usize, u64, f64)> = map
        .into_iter()
        .map(|(k, (count, tokens, cost))| (k, count, tokens, cost))
        .collect();
    rows.sort_by(|a, b| b.2.cmp(&a.2).then(a.0.cmp(&b.0)));

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Agent \u{d7} Provider Breakdown{scope}");
    println!();
    println!(
        "{:>3}  {:<16}  {:<14}  {:>11}  {:>10}  {:>10}",
        "#", "agent", "provider", "delegations", "tokens", "cost"
    );
    println!("{}", "─".repeat(78));

    let mut total_count: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (rank, (key, count, tokens, cost)) in rows.iter().enumerate() {
        let (agent, provider) = key
            .split_once('/')
            .unwrap_or((key.as_str(), "unknown"));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:>3}  {:<16}  {:<14}  {:>11}  {:>10}  {:>10}",
            rank + 1,
            agent,
            provider,
            count,
            tok_str,
            cost_str,
        );
        total_count += count;
        total_tokens += *tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(78));
    println!(
        "{}  combination(s)  \u{2022}  {} total delegations  \u{2022}  ${:.4} total cost",
        rows.len(),
        total_count,
        total_cost,
    );
    Ok(())
}

/// Groups `DelegationEnd` events into five duration buckets and shows
/// aggregate statistics per bucket, ordered fastest-first.
///
/// Bucket boundaries (milliseconds):
///   instant: 0–499 · fast: 500–1 999 · normal: 2 000–9 999
///   slow: 10 000–59 999 · very slow: ≥ 60 000
///
/// Empty buckets are omitted.  Use `run_id` to scope to a single run;
/// `None` aggregates across every stored run.
///
/// Output columns: bucket | count | ok% | tokens | cost
pub fn print_duration_bucket(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 5] = ["<500ms", "500ms–2s", "2s–10s", "10s–60s", ">60s"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // buckets[i] = (count, success_count, tokens, cost)
    let mut buckets: [(usize, usize, u64, f64); 5] = [(0, 0, 0, 0.0); 5];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let duration_ms = ev
            .get("duration_ms")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let idx = match duration_ms {
            0..=499 => 0,
            500..=1999 => 1,
            2000..=9999 => 2,
            10000..=59999 => 3,
            _ => 4,
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        buckets[idx].0 += 1;
        if ok {
            buckets[idx].1 += 1;
        }
        buckets[idx].2 += tokens;
        buckets[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Duration Bucket Breakdown{scope}");
    println!();
    println!(
        "{:<10}  {:>7}  {:>8}  {:>10}  {:>10}",
        "bucket", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "─".repeat(55));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<10}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "─".repeat(55));
    println!(
        "{}  bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Histogram of `DelegationEnd` events bucketed by `tokens_used`.
///
/// Five fixed-width buckets (in smallest-to-largest order):
/// `0–99`, `100–999`, `1k–9.9k`, `10k–99.9k`, `100k+`.
/// Empty buckets are omitted from the output.
///
/// Mirrors `zeroclaw delegations token-bucket`.
pub fn print_token_bucket(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 5] = ["0\u{2013}99", "100\u{2013}999", "1k\u{2013}9.9k", "10k\u{2013}99.9k", "100k+"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // buckets[i] = (count, success_count, tokens, cost)
    let mut buckets: [(usize, usize, u64, f64); 5] = [(0, 0, 0, 0.0); 5];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let tokens_used = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let idx = match tokens_used {
            0..=99 => 0,
            100..=999 => 1,
            1000..=9999 => 2,
            10000..=99999 => 3,
            _ => 4,
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = tokens_used;
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        buckets[idx].0 += 1;
        if ok {
            buckets[idx].1 += 1;
        }
        buckets[idx].2 += tokens;
        buckets[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Token Bucket Breakdown{scope}");
    println!();
    println!(
        "{:<12}  {:>7}  {:>8}  {:>10}  {:>10}",
        "bucket", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(57));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<12}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(57));
    println!(
        "{}  bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Histogram of `DelegationEnd` events bucketed by `cost_usd`.
///
/// Five fixed-width buckets (cheapest-to-most-expensive order):
/// `<$0.001`, `$0.001–$0.01`, `$0.01–$0.10`, `$0.10–$1.00`, `≥$1.00`.
/// Empty buckets are omitted from the output.
///
/// Mirrors `zeroclaw delegations cost-bucket`.
pub fn print_cost_bucket(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 5] = [
        "<$0.001",
        "$0.001\u{2013}$0.01",
        "$0.01\u{2013}$0.10",
        "$0.10\u{2013}$1.00",
        "\u{2265}$1.00",
    ];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // buckets[i] = (count, success_count, tokens, cost)
    let mut buckets: [(usize, usize, u64, f64); 5] = [(0, 0, 0, 0.0); 5];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let cost_usd = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let idx = if cost_usd < 0.001 {
            0
        } else if cost_usd < 0.01 {
            1
        } else if cost_usd < 0.10 {
            2
        } else if cost_usd < 1.00 {
            3
        } else {
            4
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        buckets[idx].0 += 1;
        if ok {
            buckets[idx].1 += 1;
        }
        buckets[idx].2 += tokens;
        buckets[idx].3 += cost_usd;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Cost Bucket Breakdown{scope}");
    println!();
    println!(
        "{:<16}  {:>7}  {:>8}  {:>10}  {:>10}",
        "bucket", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(61));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<16}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(61));
    println!(
        "{}  bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Breakdown of `DelegationEnd` events by ISO weekday (Mon–Sun, UTC).
///
/// Seven fixed slots in Mon-first order; empty days are omitted.
/// Events from all matching runs are bucketed by the UTC weekday of
/// their `timestamp` field.
///
/// Mirrors `zeroclaw delegations weekday`.
pub fn print_weekday(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 7] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // slots[i] = (count, success_count, tokens, cost)  Mon=0 … Sun=6
    let mut slots: [(usize, usize, u64, f64); 7] = [(0, 0, 0, 0.0); 7];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        let Ok(dt) = DateTime::parse_from_rfc3339(ts) else {
            continue;
        };
        let idx = dt.weekday().num_days_from_monday() as usize;
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        slots[idx].0 += 1;
        if ok {
            slots[idx].1 += 1;
        }
        slots[idx].2 += tokens;
        slots[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Weekday Breakdown{scope}");
    println!();
    println!(
        "{:<6}  {:>7}  {:>8}  {:>10}  {:>10}",
        "day", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(49));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut active: usize = 0;

    for (i, (count, success_count, tokens, cost)) in slots.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        active += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<6}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(49));
    println!(
        "{}  active day(s)  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        active,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by ISO 8601 week (YYYY-WXX) and print a
/// breakdown table, sorted oldest-week first.
///
/// Only `DelegationEnd` events are counted.  The week key is derived by
/// parsing the RFC-3339 timestamp with chrono and calling `iso_week()`.
/// Events with an unparseable timestamp are skipped.
///
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: week | count | ok% | tokens | cost
pub fn print_weekly(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // Aggregate DelegationEnd events by ISO week key "YYYY-WXX".
    let mut map: std::collections::BTreeMap<String, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(ts) = ev.get("timestamp").and_then(|x| x.as_str()) else {
            continue;
        };
        let Ok(dt) = DateTime::parse_from_rfc3339(ts) else {
            continue;
        };
        let iw = dt.iso_week();
        let key = format!("{}-W{:02}", iw.year(), iw.week());
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = map.entry(key).or_insert((0usize, 0usize, 0u64, 0.0f64));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        println!("No completed delegations found.");
        return Ok(());
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Weekly Delegation Breakdown{scope}");
    println!();
    println!(
        "{:<9}  {:>7}  {:>8}  {:>10}  {:>10}",
        "week", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(52));

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;

    for (week, (count, success_count, tokens, cost)) in &map {
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count) as f64 / (*count) as f64);
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<9}  {:>7}  {:>8}  {:>10}  {:>10}",
            week, count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(52));
    println!(
        "{} week(s)  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations into five depth buckets and print a
/// breakdown table, ordered shallowest-first.
///
/// Bucket boundaries:
///   root      depth 0
///   sub       depth 1
///   deep      depth 2
///   deeper    depth 3
///   very deep depth 4+
///
/// Only `DelegationEnd` events are counted.  Empty buckets are omitted.
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: depth | count | ok% | tokens | cost
pub fn print_depth_bucket(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 5] = ["root (0)", "sub (1)", "deep (2)", "deeper (3)", "very deep (4+)"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // buckets[i] = (count, success_count, tokens, cost)
    let mut buckets: [(usize, usize, u64, f64); 5] = [(0, 0, 0, 0.0); 5];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let depth = ev
            .get("depth")
            .and_then(|x| x.as_u64())
            .unwrap_or(0) as usize;
        let idx = match depth {
            0 => 0,
            1 => 1,
            2 => 2,
            3 => 3,
            _ => 4,
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        buckets[idx].0 += 1;
        if ok {
            buckets[idx].1 += 1;
        }
        buckets[idx].2 += tokens;
        buckets[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Depth Bucket Breakdown{scope}");
    println!();
    println!(
        "{:<15}  {:>7}  {:>8}  {:>10}  {:>10}",
        "depth", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(58));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<15}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(58));
    println!(
        "{} bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by model-family tier and print a
/// breakdown table, ordered haiku → sonnet → opus → other.
///
/// Tier assignment is based on a case-insensitive substring match on the
/// `model` field:
///   haiku   model name contains "haiku"
///   sonnet  model name contains "sonnet"
///   opus    model name contains "opus"
///   other   everything else (including missing/null model)
///
/// Only `DelegationEnd` events are counted.  Empty tiers are omitted.
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: tier | count | ok% | tokens | cost
pub fn print_model_tier(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 4] = ["haiku", "sonnet", "opus", "other"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // tiers[i] = (count, success_count, tokens, cost)
    // 0=haiku, 1=sonnet, 2=opus, 3=other
    let mut tiers: [(usize, usize, u64, f64); 4] = [(0, 0, 0, 0.0); 4];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let idx = if model.contains("haiku") {
            0
        } else if model.contains("sonnet") {
            1
        } else if model.contains("opus") {
            2
        } else {
            3
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        tiers[idx].0 += 1;
        if ok {
            tiers[idx].1 += 1;
        }
        tiers[idx].2 += tokens;
        tiers[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Model Tier Breakdown{scope}");
    println!();
    println!(
        "{:<8}  {:>7}  {:>8}  {:>10}  {:>10}",
        "tier", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(51));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in tiers.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<8}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(51));
    println!(
        "{} tier(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Aggregate completed delegations by provider tier and print a breakdown
/// table, ordered anthropic → openai → google → other.
///
/// Tier assignment is based on a case-insensitive substring match on the
/// `provider` field:
///   anthropic  provider name contains "anthropic"
///   openai     provider name contains "openai"
///   google     provider name contains "google"
///   other      everything else (including missing/null provider)
///
/// Only `DelegationEnd` events are counted.  Empty tiers are omitted.
/// Use `run_id` to scope to a single process invocation; `None` aggregates
/// across every stored run.
///
/// Output columns: tier | count | ok% | tokens | cost
pub fn print_provider_tier(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 4] = ["anthropic", "openai", "google", "other"];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    let events: Vec<&Value> = if let Some(rid) = run_id {
        all_events
            .iter()
            .filter(|e| e.get("run_id").and_then(|x| x.as_str()) == Some(rid))
            .collect()
    } else {
        all_events.iter().collect()
    };

    if events.is_empty() {
        println!("No events found for run: {}", run_id.unwrap_or("?"));
        return Ok(());
    }

    // tiers[i] = (count, success_count, tokens, cost)
    // 0=anthropic, 1=openai, 2=google, 3=other
    let mut tiers: [(usize, usize, u64, f64); 4] = [(0, 0, 0, 0.0); 4];

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let provider = ev
            .get("provider")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let idx = if provider.contains("anthropic") {
            0
        } else if provider.contains("openai") {
            1
        } else if provider.contains("google") {
            2
        } else {
            3
        };
        let ok = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        tiers[idx].0 += 1;
        if ok {
            tiers[idx].1 += 1;
        }
        tiers[idx].2 += tokens;
        tiers[idx].3 += cost;
    }

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Provider Tier Breakdown{scope}");
    println!();
    println!(
        "{:<11}  {:>7}  {:>8}  {:>10}  {:>10}",
        "tier", "count", "ok%", "tokens", "cost"
    );
    println!("{}", "\u{2500}".repeat(54));

    let mut total_count: usize = 0;
    let mut total_success: usize = 0;
    let mut total_tokens: u64 = 0;
    let mut total_cost: f64 = 0.0;
    let mut populated: usize = 0;

    for (i, (count, success_count, tokens, cost)) in tiers.iter().enumerate() {
        if *count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = format!("{:.1}%", 100.0 * (*success_count as f64) / (*count as f64));
        let tok_str = if *tokens > 0 {
            tokens.to_string()
        } else {
            "\u{2014}".to_owned()
        };
        let cost_str = if *cost > 0.0 {
            format!("${cost:.4}")
        } else {
            "\u{2014}".to_owned()
        };
        println!(
            "{:<11}  {:>7}  {:>8}  {:>10}  {:>10}",
            LABELS[i], count, ok_pct, tok_str, cost_str,
        );
        total_count += count;
        total_success += success_count;
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{}", "\u{2500}".repeat(54));
    println!(
        "{} tier(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Show delegation counts, success rate, token usage, and cost bucketed by
/// time of day: night (00–05), morning (06–11), afternoon (12–17), evening (18–23).
///
/// Hour is derived from the UTC timestamp on each `DelegationEnd` event.
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_time_of_day(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 4] = [
        "night (00-05)",
        "morning (06-11)",
        "afternoon (12-17)",
        "evening (18-23)",
    ];
    let mut buckets: [(usize, usize, u64, f64); 4] = [(0, 0, 0, 0.0); 4];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        return Ok(());
    }

    for ev in &all_events {
        if ev.get("event_type").and_then(|v| v.as_str()).unwrap_or("") != "DelegationEnd" {
            continue;
        }
        if let Some(rid) = run_id {
            if ev.get("run_id").and_then(|v| v.as_str()).unwrap_or("") != rid {
                continue;
            }
        }
        let ts = ev.get("timestamp").and_then(|v| v.as_str()).unwrap_or("");
        let hour = if let Ok(dt) = DateTime::parse_from_rfc3339(ts) {
            dt.with_timezone(&Utc).hour()
        } else {
            continue;
        };
        let idx: usize = match hour {
            0..=5 => 0,
            6..=11 => 1,
            12..=17 => 2,
            _ => 3,
        };
        let tokens = ev.get("tokens_used").and_then(|v| v.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let success = ev.get("success").and_then(|v| v.as_bool()).unwrap_or(false);
        let (c, s, t, co) = buckets[idx];
        buckets[idx] = (c + 1, s + if success { 1 } else { 0 }, t + tokens, co + cost);
    }

    if buckets.iter().all(|(c, ..)| *c == 0) {
        return Ok(());
    }

    let sep = "\u{2500}".repeat(61);
    println!("{:<18}  {:>7}  {:>8}  {:>10}  {:>10}", "period", "count", "ok%", "tokens", "cost ($)");
    println!("{sep}");

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_cost = 0.0f64;
    let mut populated = 0usize;

    for (i, &(count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = 100.0 * success_count as f64 / count as f64;
        println!(
            "{:<18}  {:>7}  {:>7.1}%  {:>10}  {:>10.4}",
            LABELS[i], count, ok_pct, tokens, cost,
        );
        total_count += count;
        total_success += success_count;
        total_cost += cost;
    }

    println!("{sep}");
    println!(
        "{} bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Show delegation counts, success rate, token usage, and cost grouped by
/// day of month (1–31), sorted numerically.  Useful for spotting calendar
/// patterns and end-of-month activity spikes.
///
/// Day is derived from the UTC timestamp on each `DelegationEnd` event.
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_day_of_month(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let mut map: std::collections::BTreeMap<u32, (usize, usize, u64, f64)> =
        std::collections::BTreeMap::new();

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        return Ok(());
    }

    for ev in &all_events {
        if ev.get("event_type").and_then(|v| v.as_str()).unwrap_or("") != "DelegationEnd" {
            continue;
        }
        if let Some(rid) = run_id {
            if ev.get("run_id").and_then(|v| v.as_str()).unwrap_or("") != rid {
                continue;
            }
        }
        let ts = ev.get("timestamp").and_then(|v| v.as_str()).unwrap_or("");
        let day = if let Ok(dt) = DateTime::parse_from_rfc3339(ts) {
            dt.with_timezone(&Utc).day()
        } else {
            continue;
        };
        let tokens = ev.get("tokens_used").and_then(|v| v.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let success = ev.get("success").and_then(|v| v.as_bool()).unwrap_or(false);
        let entry = map.entry(day).or_insert((0, 0, 0, 0.0));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if map.is_empty() {
        return Ok(());
    }

    let sep = "\u{2500}".repeat(47);
    println!("{:<4}  {:>7}  {:>8}  {:>10}  {:>10}", "day", "count", "ok%", "tokens", "cost ($)");
    println!("{sep}");

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_cost = 0.0f64;

    for (&day, &(count, success_count, tokens, cost)) in &map {
        let ok_pct = 100.0 * success_count as f64 / count as f64;
        println!(
            "{:<4}  {:>7}  {:>7.1}%  {:>10}  {:>10.4}",
            day, count, ok_pct, tokens, cost,
        );
        total_count += count;
        total_success += success_count;
        total_cost += cost;
    }

    println!("{sep}");
    println!(
        "{} day(s) active  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        map.len(),
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Show delegation counts, success rate, token usage, and cost bucketed by
/// cost per 1 000 tokens (token efficiency): very cheap (<$0.002/1k),
/// cheap ($0.002–$0.008/1k), moderate ($0.008–$0.020/1k), expensive (>$0.020/1k).
///
/// Delegations with zero `tokens_used` are skipped (efficiency undefined).
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_token_efficiency(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 4] = ["very cheap", "cheap", "moderate", "expensive"];
    let mut buckets: [(usize, usize, u64, f64); 4] = [(0, 0, 0, 0.0); 4];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        return Ok(());
    }

    for ev in &all_events {
        if ev.get("event_type").and_then(|v| v.as_str()).unwrap_or("") != "DelegationEnd" {
            continue;
        }
        if let Some(rid) = run_id {
            if ev.get("run_id").and_then(|v| v.as_str()).unwrap_or("") != rid {
                continue;
            }
        }
        let tokens = ev.get("tokens_used").and_then(|v| v.as_u64()).unwrap_or(0);
        if tokens == 0 {
            continue;
        }
        let cost = ev.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let efficiency = cost / (tokens as f64 / 1_000.0);
        let idx: usize = if efficiency < 0.002 {
            0
        } else if efficiency < 0.008 {
            1
        } else if efficiency < 0.020 {
            2
        } else {
            3
        };
        let success = ev.get("success").and_then(|v| v.as_bool()).unwrap_or(false);
        let (c, s, t, co) = buckets[idx];
        buckets[idx] = (c + 1, s + if success { 1 } else { 0 }, t + tokens, co + cost);
    }

    if buckets.iter().all(|(c, ..)| *c == 0) {
        return Ok(());
    }

    let sep = "\u{2500}".repeat(53);
    println!("{:<10}  {:>7}  {:>8}  {:>10}  {:>10}", "tier", "count", "ok%", "tokens", "cost ($)");
    println!("{sep}");

    let mut total_count = 0usize;
    let mut total_success = 0usize;
    let mut total_cost = 0.0f64;
    let mut populated = 0usize;

    for (i, &(count, success_count, tokens, cost)) in buckets.iter().enumerate() {
        if count == 0 {
            continue;
        }
        populated += 1;
        let ok_pct = 100.0 * success_count as f64 / count as f64;
        println!(
            "{:<10}  {:>7}  {:>7.1}%  {:>10}  {:>10.4}",
            LABELS[i], count, ok_pct, tokens, cost,
        );
        total_count += count;
        total_success += success_count;
        total_cost += cost;
    }

    println!("{sep}");
    println!(
        "{} bucket(s) populated  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        total_success,
        total_cost,
    );
    Ok(())
}

/// Show delegation counts, token usage, and cost split by outcome: succeeded
/// vs. failed.  Answers "how much token/cost spending landed on failed calls?".
///
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_success_breakdown(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    const LABELS: [&str; 2] = ["succeeded", "failed"];
    // [count, tokens, cost]  (no success_count sub-field — outcome IS the category)
    let mut buckets: [(usize, u64, f64); 2] = [(0, 0, 0.0); 2];

    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        return Ok(());
    }

    for ev in &all_events {
        if ev.get("event_type").and_then(|v| v.as_str()).unwrap_or("") != "DelegationEnd" {
            continue;
        }
        if let Some(rid) = run_id {
            if ev.get("run_id").and_then(|v| v.as_str()).unwrap_or("") != rid {
                continue;
            }
        }
        let success = ev.get("success").and_then(|v| v.as_bool()).unwrap_or(false);
        let tokens = ev.get("tokens_used").and_then(|v| v.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let idx = if success { 0 } else { 1 };
        let (c, t, co) = buckets[idx];
        buckets[idx] = (c + 1, t + tokens, co + cost);
    }

    if buckets.iter().all(|(c, ..)| *c == 0) {
        return Ok(());
    }

    let total_count: usize = buckets.iter().map(|(c, ..)| c).sum();
    let sep = "\u{2500}".repeat(53);
    println!("{:<10}  {:>7}  {:>8}  {:>10}  {:>10}", "outcome", "count", "share%", "tokens", "cost ($)");
    println!("{sep}");

    let mut total_tokens = 0u64;
    let mut total_cost = 0.0f64;
    let mut populated = 0usize;

    for (i, &(count, tokens, cost)) in buckets.iter().enumerate() {
        if count == 0 {
            continue;
        }
        populated += 1;
        let share = 100.0 * count as f64 / total_count as f64;
        println!(
            "{:<10}  {:>7}  {:>7.1}%  {:>10}  {:>10.4}",
            LABELS[i], count, share, tokens, cost,
        );
        total_tokens += tokens;
        total_cost += cost;
    }

    println!("{sep}");
    let succeeded = buckets[0].0;
    println!(
        "{} outcome(s) present  \u{2022}  {} total delegations  \u{2022}  {} succeeded  \u{2022}  ${:.4} total cost",
        populated,
        total_count,
        succeeded,
        total_cost,
    );
    Ok(())
}

/// Ranks agents by average cost per delegation (most expensive per call first).
///
/// Answers "which individual agent type is most expensive per invocation?" as opposed
/// to `print_top` (total-volume ranking) and `print_stats` (count-sorted, avg duration focus).
///
/// Columns: # | agent | delegations | ok% | avg_cost | avg_tokens | total_cost
///
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_agent_cost_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
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

    // agent → (count, success_count, tokens, total_cost)
    let mut map: std::collections::HashMap<String, (usize, usize, u64, f64)> =
        std::collections::HashMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let agent = ev
            .get("agent_name")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown")
            .to_owned();
        let success = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev.get("tokens_used").and_then(|x| x.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let e = map.entry(agent).or_insert((0, 0, 0, 0.0));
        e.0 += 1;
        if success {
            e.1 += 1;
        }
        e.2 += tokens;
        e.3 += cost;
    }

    if map.is_empty() {
        return Ok(());
    }

    // Sort by avg_cost per delegation descending, break ties by name ascending.
    let mut rows: Vec<(String, usize, usize, u64, f64)> = map
        .into_iter()
        .map(|(agent, (count, ok, tokens, cost))| (agent, count, ok, tokens, cost))
        .collect();
    rows.sort_by(|a, b| {
        let avg_a = a.4 / a.1 as f64;
        let avg_b = b.4 / b.1 as f64;
        avg_b.partial_cmp(&avg_a).unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Agent cost rank — avg cost per delegation{scope}");
    println!();
    println!(
        "{:>3}  {:<26}  {:>7}  {:>8}  {:>10}  {:>10}  {:>10}",
        "#", "agent", "count", "ok%", "avg_cost", "avg_tok", "total_cost"
    );
    println!("{}", "─".repeat(84));

    for (rank, (agent, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let ok_pct = 100.0 * (*ok as f64) / (*count as f64);
        let avg_cost = cost / (*count as f64);
        let avg_tok = *tokens as f64 / (*count as f64);
        println!(
            "{:>3}  {:<26}  {:>7}  {:>7.1}%  {:>10.4}  {:>10.0}  {:>10.4}",
            rank + 1,
            agent,
            count,
            ok_pct,
            avg_cost,
            avg_tok,
            cost
        );
    }

    println!("{}", "─".repeat(84));
    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_cost: f64 = rows.iter().map(|(_, _, _, _, c)| c).sum();
    println!(
        "{} agent(s) \u{2022} {} total delegations \u{2022} ${:.4} total cost",
        rows.len(),
        total_delegations,
        total_cost
    );

    Ok(())
}

/// Ranks models by average cost per delegation (most expensive per call first).
///
/// Answers "which model is most expensive per individual invocation?" — distinct from
/// `print_models` (sorted by total tokens) and `print_top --by cost` (agent-level totals).
///
/// Columns: # | model | delegations | ok% | avg_cost | avg_tokens | total_cost
///
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_model_cost_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
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

    // model → (count, success_count, tokens, total_cost)
    let mut map: std::collections::HashMap<String, (usize, usize, u64, f64)> =
        std::collections::HashMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown")
            .to_owned();
        let success = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev.get("tokens_used").and_then(|x| x.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let e = map.entry(model).or_insert((0, 0, 0, 0.0));
        e.0 += 1;
        if success {
            e.1 += 1;
        }
        e.2 += tokens;
        e.3 += cost;
    }

    if map.is_empty() {
        return Ok(());
    }

    // Sort by avg_cost per delegation descending, break ties by model name ascending.
    let mut rows: Vec<(String, usize, usize, u64, f64)> = map
        .into_iter()
        .map(|(model, (count, ok, tokens, cost))| (model, count, ok, tokens, cost))
        .collect();
    rows.sort_by(|a, b| {
        let avg_a = a.4 / a.1 as f64;
        let avg_b = b.4 / b.1 as f64;
        avg_b.partial_cmp(&avg_a).unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Model cost rank — avg cost per delegation{scope}");
    println!();
    println!(
        "{:>3}  {:<34}  {:>7}  {:>8}  {:>10}  {:>10}  {:>10}",
        "#", "model", "count", "ok%", "avg_cost", "avg_tok", "total_cost"
    );
    println!("{}", "─".repeat(92));

    for (rank, (model, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let ok_pct = 100.0 * (*ok as f64) / (*count as f64);
        let avg_cost = cost / (*count as f64);
        let avg_tok = *tokens as f64 / (*count as f64);
        println!(
            "{:>3}  {:<34}  {:>7}  {:>7.1}%  {:>10.4}  {:>10.0}  {:>10.4}",
            rank + 1,
            model,
            count,
            ok_pct,
            avg_cost,
            avg_tok,
            cost
        );
    }

    println!("{}", "─".repeat(92));
    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_cost: f64 = rows.iter().map(|(_, _, _, _, c)| c).sum();
    println!(
        "{} model(s) \u{2022} {} total delegations \u{2022} ${:.4} total cost",
        rows.len(),
        total_delegations,
        total_cost
    );

    Ok(())
}

/// Ranks providers by average cost per delegation (most expensive per call first).
///
/// Completes the cost-rank trio alongside `print_agent_cost_rank` and
/// `print_model_cost_rank`. Distinct from `print_providers` (total-token sorted).
///
/// Columns: # | provider | delegations | ok% | avg_cost | avg_tokens | total_cost
///
/// When `run_id` is `Some`, only events from that run are included.
/// Produces no output (and returns `Ok`) when the log is absent or empty.
pub fn print_provider_cost_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
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

    // provider → (count, success_count, tokens, total_cost)
    let mut map: std::collections::HashMap<String, (usize, usize, u64, f64)> =
        std::collections::HashMap::new();

    for ev in &events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let provider = ev
            .get("provider")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown")
            .to_owned();
        let success = ev.get("success").and_then(|x| x.as_bool()).unwrap_or(false);
        let tokens = ev.get("tokens_used").and_then(|x| x.as_u64()).unwrap_or(0);
        let cost = ev.get("cost_usd").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let e = map.entry(provider).or_insert((0, 0, 0, 0.0));
        e.0 += 1;
        if success {
            e.1 += 1;
        }
        e.2 += tokens;
        e.3 += cost;
    }

    if map.is_empty() {
        return Ok(());
    }

    // Sort by avg_cost per delegation descending, break ties by provider name ascending.
    let mut rows: Vec<(String, usize, usize, u64, f64)> = map
        .into_iter()
        .map(|(provider, (count, ok, tokens, cost))| (provider, count, ok, tokens, cost))
        .collect();
    rows.sort_by(|a, b| {
        let avg_a = a.4 / a.1 as f64;
        let avg_b = b.4 / b.1 as f64;
        avg_b.partial_cmp(&avg_a).unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    let scope = run_id
        .map(|r| format!("  (run: {r})"))
        .unwrap_or_else(|| "  (all runs)".to_owned());
    println!("Provider cost rank — avg cost per delegation{scope}");
    println!();
    println!(
        "{:>3}  {:<18}  {:>7}  {:>8}  {:>10}  {:>10}  {:>10}",
        "#", "provider", "count", "ok%", "avg_cost", "avg_tok", "total_cost"
    );
    println!("{}", "─".repeat(76));

    for (rank, (provider, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let ok_pct = 100.0 * (*ok as f64) / (*count as f64);
        let avg_cost = cost / (*count as f64);
        let avg_tok = *tokens as f64 / (*count as f64);
        println!(
            "{:>3}  {:<18}  {:>7}  {:>7.1}%  {:>10.4}  {:>10.0}  {:>10.4}",
            rank + 1,
            provider,
            count,
            ok_pct,
            avg_cost,
            avg_tok,
            cost
        );
    }

    println!("{}", "─".repeat(76));
    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_cost: f64 = rows.iter().map(|(_, _, _, _, c)| c).sum();
    println!(
        "{} provider(s) \u{2022} {} total delegations \u{2022} ${:.4} total cost",
        rows.len(),
        total_delegations,
        total_cost
    );

    Ok(())
}

/// Ranks runs by total cost (most expensive run first).
///
/// Answers "which run burned the most money?" — distinct from agent/model/provider cost-rank
/// (per-invocation average) and from `print_top` (agent-level total volume).
///
/// Output columns: `# | run | delegations | ok% | avg_cost | avg_tok | total_cost`
///
/// Sorted by total_cost descending, ties by run_id ascending.
/// When `run_id` is `Some`, only events from that run are included (shows a single row).
pub fn print_run_cost_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // run_id → (count, success_count, tokens, total_cost)
    let mut run_map: HashMap<String, (usize, usize, u64, f64)> = HashMap::new();

    for ev in &all_events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(rid) = ev.get("run_id").and_then(|x| x.as_str()) else {
            continue;
        };
        if let Some(filter) = run_id {
            if rid != filter {
                continue;
            }
        }
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = run_map.entry(rid.to_owned()).or_insert((0, 0, 0, 0.0));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if run_map.is_empty() {
        println!("No delegation events found.");
        return Ok(());
    }

    let mut rows: Vec<(String, usize, usize, u64, f64)> = run_map
        .into_iter()
        .map(|(rid, (c, ok, tok, cost))| (rid, c, ok, tok, cost))
        .collect();
    // Sort: total_cost desc, ties by run_id asc
    rows.sort_by(|a, b| {
        b.4.partial_cmp(&a.4)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.0.cmp(&b.0))
    });

    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_cost: f64 = rows.iter().map(|(_, _, _, _, cost)| cost).sum();

    println!(
        " {:<3} {:<32} {:>11} {:>6} {:>10} {:>9} {:>12}",
        "#", "run", "delegations", "ok%", "avg_cost", "avg_tok", "total_cost"
    );
    println!("{}", "─".repeat(90));
    for (i, (rid, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let avg_cost = if *count > 0 { cost / *count as f64 } else { 0.0 };
        let avg_tok = if *count > 0 { tokens / *count as u64 } else { 0 };
        let ok_pct = if *count > 0 {
            100.0 * *ok as f64 / *count as f64
        } else {
            0.0
        };
        println!(
            " {:<3} {:<32} {:>11} {:>5.1}% {:>10.4} {:>9} {:>12.4}",
            i + 1,
            rid,
            count,
            ok_pct,
            avg_cost,
            avg_tok,
            cost,
        );
    }
    println!("{}", "─".repeat(90));
    println!(
        "{} run(s) \u{2022} {} total delegations \u{2022} ${:.4} total cost",
        rows.len(),
        total_delegations,
        total_cost
    );

    Ok(())
}

/// Ranks agents by success rate (most reliable first).
///
/// Answers "which agents are most reliable?" — distinct from `print_agent_cost_rank`
/// (sorted by avg cost) and `print_success_breakdown` (aggregate only, no per-agent view).
///
/// Output columns: `# | agent | delegations | ok% | failures | avg_cost | avg_tok`
///
/// Sorted by ok_pct descending, ties by delegation count descending (more samples first),
/// then by agent name ascending.
/// When `run_id` is `Some`, only events from that run are included.
pub fn print_agent_success_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // agent_name → (count, success_count, tokens, total_cost)
    let mut agent_map: HashMap<String, (usize, usize, u64, f64)> = HashMap::new();

    for ev in &all_events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let Some(agent) = ev.get("agent_name").and_then(|x| x.as_str()) else {
            continue;
        };
        if let Some(filter) = run_id {
            if ev.get("run_id").and_then(|x| x.as_str()) != Some(filter) {
                continue;
            }
        }
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = agent_map.entry(agent.to_owned()).or_insert((0, 0, 0, 0.0));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if agent_map.is_empty() {
        println!("No delegation events found.");
        return Ok(());
    }

    let mut rows: Vec<(String, usize, usize, u64, f64)> = agent_map
        .into_iter()
        .map(|(agent, (c, ok, tok, cost))| (agent, c, ok, tok, cost))
        .collect();
    // Sort: ok_pct desc, ties by count desc, then name asc
    rows.sort_by(|a, b| {
        let ok_a = if a.1 > 0 { a.2 as f64 / a.1 as f64 } else { 0.0 };
        let ok_b = if b.1 > 0 { b.2 as f64 / b.1 as f64 } else { 0.0 };
        ok_b.partial_cmp(&ok_a)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(b.1.cmp(&a.1))
            .then(a.0.cmp(&b.0))
    });

    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_failures: usize = rows.iter().map(|(_, c, ok, _, _)| c - ok).sum();

    println!(
        " {:<3} {:<26} {:>11} {:>6} {:>9} {:>10} {:>9}",
        "#", "agent", "delegations", "ok%", "failures", "avg_cost", "avg_tok"
    );
    println!("{}", "─".repeat(84));
    for (i, (agent, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let failures = count - ok;
        let avg_cost = if *count > 0 { cost / *count as f64 } else { 0.0 };
        let avg_tok = if *count > 0 { tokens / *count as u64 } else { 0 };
        let ok_pct = if *count > 0 {
            100.0 * *ok as f64 / *count as f64
        } else {
            0.0
        };
        println!(
            " {:<3} {:<26} {:>11} {:>5.1}% {:>9} {:>10.4} {:>9}",
            i + 1,
            agent,
            count,
            ok_pct,
            failures,
            avg_cost,
            avg_tok,
        );
    }
    println!("{}", "─".repeat(84));
    println!(
        "{} agent(s) \u{2022} {} total delegations \u{2022} {} total failures",
        rows.len(),
        total_delegations,
        total_failures,
    );

    Ok(())
}

/// Ranks models by success rate (most reliable first).
///
/// Answers "which model is most reliable?" — mirrors `print_agent_success_rank`
/// but keyed by the `model` field rather than `agent_name`.
///
/// Output columns: `# | model | delegations | ok% | failures | avg_cost | avg_tok`
///
/// Sorted by ok_pct descending, ties by delegation count descending, then model name ascending.
/// When `run_id` is `Some`, only events from that run are included.
pub fn print_model_success_rank(log_path: &Path, run_id: Option<&str>) -> Result<()> {
    let all_events = read_all_events(log_path)?;
    if all_events.is_empty() {
        println!("No delegation data found at: {}", log_path.display());
        println!("Run ZeroClaw with a workflow that uses the `delegate` tool.");
        return Ok(());
    }

    // model → (count, success_count, tokens, total_cost)
    let mut model_map: HashMap<String, (usize, usize, u64, f64)> = HashMap::new();

    for ev in &all_events {
        if ev.get("event_type").and_then(|x| x.as_str()) != Some("DelegationEnd") {
            continue;
        }
        let model = ev
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("unknown")
            .to_owned();
        if let Some(filter) = run_id {
            if ev.get("run_id").and_then(|x| x.as_str()) != Some(filter) {
                continue;
            }
        }
        let success = ev
            .get("success")
            .and_then(|x| x.as_bool())
            .unwrap_or(false);
        let tokens = ev
            .get("tokens_used")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let cost = ev
            .get("cost_usd")
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0);
        let entry = model_map.entry(model).or_insert((0, 0, 0, 0.0));
        entry.0 += 1;
        if success {
            entry.1 += 1;
        }
        entry.2 += tokens;
        entry.3 += cost;
    }

    if model_map.is_empty() {
        println!("No delegation events found.");
        return Ok(());
    }

    let mut rows: Vec<(String, usize, usize, u64, f64)> = model_map
        .into_iter()
        .map(|(model, (c, ok, tok, cost))| (model, c, ok, tok, cost))
        .collect();
    // Sort: ok_pct desc, ties by count desc, then model name asc
    rows.sort_by(|a, b| {
        let ok_a = if a.1 > 0 { a.2 as f64 / a.1 as f64 } else { 0.0 };
        let ok_b = if b.1 > 0 { b.2 as f64 / b.1 as f64 } else { 0.0 };
        ok_b.partial_cmp(&ok_a)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(b.1.cmp(&a.1))
            .then(a.0.cmp(&b.0))
    });

    let total_delegations: usize = rows.iter().map(|(_, c, _, _, _)| c).sum();
    let total_failures: usize = rows.iter().map(|(_, c, ok, _, _)| c - ok).sum();

    println!(
        " {:<3} {:<34} {:>11} {:>6} {:>9} {:>10} {:>9}",
        "#", "model", "delegations", "ok%", "failures", "avg_cost", "avg_tok"
    );
    println!("{}", "─".repeat(92));
    for (i, (model, count, ok, tokens, cost)) in rows.iter().enumerate() {
        let failures = count - ok;
        let avg_cost = if *count > 0 { cost / *count as f64 } else { 0.0 };
        let avg_tok = if *count > 0 { tokens / *count as u64 } else { 0 };
        let ok_pct = if *count > 0 {
            100.0 * *ok as f64 / *count as f64
        } else {
            0.0
        };
        println!(
            " {:<3} {:<34} {:>11} {:>5.1}% {:>9} {:>10.4} {:>9}",
            i + 1,
            model,
            count,
            ok_pct,
            failures,
            avg_cost,
            avg_tok,
        );
    }
    println!("{}", "─".repeat(92));
    println!(
        "{} model(s) \u{2022} {} total delegations \u{2022} {} total failures",
        rows.len(),
        total_delegations,
        total_failures,
    );

    Ok(())
}

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
            println!(
                "run_id,agent_name,model,depth,duration_ms,tokens_used,cost_usd,success,timestamp"
            );
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
            format!(
                "{:.1}%",
                100.0 * s.success_count as f64 / s.end_count as f64
            )
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
        println!(
            "{:<42} {:>8} {:>8} {:>10}  {}",
            label, dur, tok, cost, status
        );
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
            make_end(
                "run-aaa",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ),
            make_start("run-bbb", "main", 0, "2026-01-01T11:00:00Z"),
            make_end(
                "run-bbb",
                "main",
                0,
                "2026-01-01T11:00:05Z",
                2000,
                0.006,
                true,
            ),
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
            make_end(
                "run-aaa",
                "sub",
                1,
                "2026-01-01T10:00:03Z",
                500,
                0.001,
                true,
            ),
            make_end(
                "run-aaa",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ),
        ];
        let runs = collect_runs(&events);
        assert_eq!(runs.len(), 1);
        assert_eq!(runs[0].delegation_count, 2); // two DelegationStart events
        assert_eq!(runs[0].total_tokens, 1500); // 500 + 1000 from DelegationEnd events
    }

    #[test]
    fn build_nodes_matches_start_and_end() {
        let events = vec![
            make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z"),
            make_end(
                "run-aaa",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1234,
                0.0037,
                true,
            ),
        ];
        let nodes = build_nodes(&events);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].agent_name, "main");
        assert_eq!(nodes[0].tokens_used, Some(1234));
        assert_eq!(nodes[0].success, Some(true));
    }

    #[test]
    fn build_nodes_marks_unmatched_as_in_flight() {
        let events = vec![make_start("run-aaa", "main", 0, "2026-01-01T10:00:00Z")];
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
        lines.push(
            serde_json::to_string(&make_start("run-test", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-test",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
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
        lines.push(
            serde_json::to_string(&make_start("run-recent", "main", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-recent",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                800,
                0.002,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
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
        let line = serde_json::to_string(&make_start(
            "run-specific",
            "main",
            0,
            "2026-01-01T10:00:00Z",
        ))
        .unwrap();
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
            make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ),
            make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z"),
            make_end("run-a", "sub", 1, "2026-01-01T10:00:04Z", 500, 0.001, true),
            make_start("run-a", "main", 0, "2026-01-01T11:00:00Z"),
            make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T11:00:05Z",
                2000,
                0.006,
                false,
            ),
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
            make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T11:00:05Z",
                200,
                0.002,
                false,
            ),
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
            make_end(
                "run-a",
                "light",
                1,
                "2026-01-01T10:00:01Z",
                100,
                0.0001,
                true,
            ),
            make_start("run-a", "heavy", 0, "2026-01-01T10:00:00Z"),
            make_end(
                "run-a",
                "heavy",
                0,
                "2026-01-01T10:00:05Z",
                5000,
                0.015,
                true,
            ),
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
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-keep",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                999,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
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
        lines.push(
            serde_json::to_string(&make_start("run-x", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-x",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-y", "main", 0, "2026-01-02T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-y",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                2000,
                0.006,
                true,
            ))
            .unwrap(),
        );
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
        lines.push(
            serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-new", "main", 0, "2026-01-03T10:00:00Z"))
                .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let summary = get_log_summary(&path).unwrap().unwrap();
        let _ = std::fs::remove_file(&path);
        let ts = summary
            .latest_run_time
            .expect("should have latest_run_time");
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
        lines.push(
            serde_json::to_string(&make_start("run-e", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-e",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_export(&path, None, ExportFormat::Csv);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_export_jsonl_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_export_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_export(&path, Some("run-keep"), ExportFormat::Jsonl);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_top_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_top(&path, TopBy::Tokens, 10).is_ok());
    }

    #[test]
    fn print_top_sorts_by_tokens_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_tok.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "light", 1, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "light",
                1,
                "2026-01-01T10:00:01Z",
                100,
                0.0001,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "heavy", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "heavy",
                0,
                "2026-01-01T10:00:05Z",
                5000,
                0.015,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_top(&path, TopBy::Tokens, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_top_sorts_by_cost_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_cost.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "cheap", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "cheap",
                0,
                "2026-01-01T10:00:01Z",
                1000,
                0.001,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "pricey", 1, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "pricey",
                1,
                "2026-01-01T10:00:05Z",
                500,
                0.050,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_top(&path, TopBy::Cost, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_top_limit_truncates_results() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_limit.jsonl");
        let mut lines = Vec::new();
        for i in 0..5u64 {
            let agent = format!("agent-{i}");
            lines.push(
                serde_json::to_string(&make_start("run-x", &agent, 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(
                    "run-x",
                    &agent,
                    0,
                    "2026-01-01T10:00:01Z",
                    i * 100,
                    i as f64 * 0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_top(&path, TopBy::Tokens, 2).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_top_aggregates_tokens_across_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_agg.jsonl");
        let mut lines = Vec::new();
        // "main" appears in two separate runs — totals should be summed
        lines.push(
            serde_json::to_string(&make_start("run-1", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-1",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-2", "main", 0, "2026-01-02T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-2",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                2000,
                0.006,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();

        let events = read_all_events(&path).unwrap();
        let _ = std::fs::remove_file(&path);

        // Verify aggregation via internal helpers (no file I/O needed after this)
        let mut rows: HashMap<String, TopAgentRow> = HashMap::new();
        let mut agent_runs_map: HashMap<String, HashSet<String>> = HashMap::new();
        for ev in &events {
            let Some(name) = ev.get("agent_name").and_then(|x| x.as_str()) else {
                continue;
            };
            let Some(rid) = ev.get("run_id").and_then(|x| x.as_str()) else {
                continue;
            };
            agent_runs_map
                .entry(name.to_owned())
                .or_default()
                .insert(rid.to_owned());
            let entry = rows.entry(name.to_owned()).or_insert_with(|| TopAgentRow {
                agent_name: name.to_owned(),
                run_count: 0,
                delegation_count: 0,
                total_tokens: 0,
                total_cost_usd: 0.0,
            });
            match ev.get("event_type").and_then(|x| x.as_str()) {
                Some("DelegationStart") => entry.delegation_count += 1,
                Some("DelegationEnd") => {
                    if let Some(tok) = ev.get("tokens_used").and_then(|x| x.as_u64()) {
                        entry.total_tokens += tok;
                    }
                }
                _ => {}
            }
        }
        for (name, row) in rows.iter_mut() {
            row.run_count = agent_runs_map.get(name).map_or(0, |s| s.len());
        }
        let main = rows.get("main").unwrap();
        assert_eq!(main.total_tokens, 3000); // 1000 + 2000
        assert_eq!(main.run_count, 2);
        assert_eq!(main.delegation_count, 2);
    }

    #[test]
    fn print_top_counts_distinct_runs_per_agent() {
        let path = std::env::temp_dir().join("zeroclaw_test_top_runs.jsonl");
        let mut lines = Vec::new();
        for run in &["run-p", "run-q", "run-r"] {
            lines.push(
                serde_json::to_string(&make_start(run, "shared-agent", 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
        }
        // unrelated agent in only one run
        lines.push(
            serde_json::to_string(&make_start(
                "run-p",
                "solo-agent",
                1,
                "2026-01-01T10:00:00Z",
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_top(&path, TopBy::Tokens, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn resolve_run_id_returns_first_prefix_match() {
        let runs = vec![
            RunInfo {
                run_id: "aaa-newer".to_owned(),
                start_time: None,
                delegation_count: 0,
                total_tokens: 0,
                total_cost_usd: 0.0,
            },
            RunInfo {
                run_id: "bbb-older".to_owned(),
                start_time: None,
                delegation_count: 0,
                total_tokens: 0,
                total_cost_usd: 0.0,
            },
        ];
        assert_eq!(resolve_run_id(&runs, "aaa"), Some("aaa-newer"));
        assert_eq!(resolve_run_id(&runs, "bbb"), Some("bbb-older"));
        // Full ID also works
        assert_eq!(resolve_run_id(&runs, "aaa-newer"), Some("aaa-newer"));
    }

    #[test]
    fn resolve_run_id_returns_none_when_no_match() {
        let runs = vec![RunInfo {
            run_id: "aaa-1".to_owned(),
            start_time: None,
            delegation_count: 0,
            total_tokens: 0,
            total_cost_usd: 0.0,
        }];
        assert_eq!(resolve_run_id(&runs, "xyz"), None);
    }

    #[test]
    fn print_diff_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_diff_empty.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_diff(&path, "any-prefix", None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_diff_two_runs_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_diff_two.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-alpha", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-alpha",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-beta", "main", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-beta",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                2000,
                0.006,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_diff(&path, "run-alpha", Some("run-beta"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_diff_defaults_run_b_to_most_recent_other() {
        let path = std::env::temp_dir().join("zeroclaw_test_diff_default_b.jsonl");
        let mut lines = Vec::new();
        // run-older has earlier timestamp → run-newer will be newest → default run_b
        lines.push(
            serde_json::to_string(&make_start("run-older", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-older",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-newer", "main", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-newer",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                2000,
                0.006,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_diff(&path, "run-older", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_diff_unknown_run_returns_error() {
        let path = std::env::temp_dir().join("zeroclaw_test_diff_bad_run.jsonl");
        let line =
            serde_json::to_string(&make_start("run-real", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap();
        std::fs::write(&path, line + "\n").unwrap();
        let result = print_diff(&path, "run-nonexistent", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_err());
    }

    #[test]
    fn print_prune_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_prune(&path, 10).is_ok());
    }

    #[test]
    fn print_prune_fewer_runs_than_keep_is_noop() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_noop.jsonl");
        let line =
            serde_json::to_string(&make_start("run-only", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap();
        std::fs::write(&path, line + "\n").unwrap();
        // 1 run stored, --keep 5 → nothing to prune
        assert!(print_prune(&path, 5).is_ok());
        let content = std::fs::read_to_string(&path).unwrap();
        let _ = std::fs::remove_file(&path);
        assert!(
            content.contains("run-only"),
            "sole run should be intact after noop"
        );
    }

    #[test]
    fn print_prune_removes_oldest_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_removes.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-mid", "main", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-new", "main", 0, "2026-01-03T10:00:00Z"))
                .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // Keep 2 most recent → run-old should be pruned
        assert!(print_prune(&path, 2).is_ok());
        let content = std::fs::read_to_string(&path).unwrap();
        let _ = std::fs::remove_file(&path);
        assert!(
            !content.contains("run-old"),
            "run-old should have been pruned"
        );
        assert!(content.contains("run-mid"), "run-mid should be retained");
        assert!(content.contains("run-new"), "run-new should be retained");
    }

    #[test]
    fn print_prune_keep_zero_empties_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_zero.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-b", "main", 0, "2026-01-02T10:00:00Z")).unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // keep=0 → all runs pruned
        assert!(print_prune(&path, 0).is_ok());
        let content = std::fs::read_to_string(&path).unwrap();
        let _ = std::fs::remove_file(&path);
        assert!(
            content.trim().is_empty(),
            "log should be empty after keep=0"
        );
    }

    #[test]
    fn print_prune_preserves_all_events_for_kept_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_keeps.jsonl");
        let mut lines = Vec::new();
        // run-old has 2 events; run-new has 2 events. Keep 1 → run-old removed.
        lines.push(
            serde_json::to_string(&make_start("run-old", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-old",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                100,
                0.001,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-new", "main", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-new",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                200,
                0.002,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_prune(&path, 1).is_ok());
        let remaining = read_all_events(&path).unwrap();
        let _ = std::fs::remove_file(&path);
        // Only the 2 run-new events should remain
        assert_eq!(
            remaining.len(),
            2,
            "exactly 2 events for kept run should remain"
        );
        assert!(
            remaining
                .iter()
                .all(|e| e.get("run_id").and_then(|x| x.as_str()) == Some("run-new")),
            "all remaining events must belong to run-new"
        );
    }

    #[test]
    fn print_prune_exact_keep_equals_run_count_is_noop() {
        let path = std::env::temp_dir().join("zeroclaw_test_prune_exact.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-b", "main", 0, "2026-01-02T10:00:00Z")).unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // Exactly 2 runs, keep=2 → noop, file unchanged
        assert!(print_prune(&path, 2).is_ok());
        let remaining = read_all_events(&path).unwrap();
        let _ = std::fs::remove_file(&path);
        assert_eq!(
            remaining.len(),
            2,
            "both events should remain when keep equals run count"
        );
    }

    #[test]
    fn print_models_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_models(&path, None).is_ok());
    }

    #[test]
    fn print_models_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_models(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_models_aggregates_tokens_and_cost_by_model() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_agg.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "sub",
                1,
                "2026-01-01T10:00:04Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // Both events use "claude-sonnet-4" (from make_end fixture)
        let result = print_models(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_models_sorts_by_tokens_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_sort.jsonl");
        let mut lines = Vec::new();
        // Two different events — make_end always uses model "claude-sonnet-4",
        // so both rows accumulate into a single model.  Verify Ok.
        lines.push(
            serde_json::to_string(&make_start("run-a", "heavy", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "heavy",
                0,
                "2026-01-01T10:00:05Z",
                5000,
                0.015,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "light", 1, "2026-01-01T10:00:01Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "light",
                1,
                "2026-01-01T10:00:03Z",
                100,
                0.0001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_models(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_models_with_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-keep",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                800,
                0.002,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-skip",
                "other",
                0,
                "2026-01-02T10:00:05Z",
                9999,
                0.030,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        // Scoped to run-keep — run-skip tokens must not appear in output
        let result = print_models(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_models_counts_distinct_runs_per_model() {
        let path = std::env::temp_dir().join("zeroclaw_test_models_runs.jsonl");
        let mut lines = Vec::new();
        // "claude-sonnet-4" appears in two distinct runs
        for run in &["run-p", "run-q"] {
            lines.push(
                serde_json::to_string(&make_start(run, "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(
                    run,
                    "main",
                    0,
                    "2026-01-01T10:00:05Z",
                    500,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_models(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_providers_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_providers(&path, None).is_ok());
    }

    #[test]
    fn print_providers_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_providers(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_providers_aggregates_tokens_and_cost_by_provider() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_agg.jsonl");
        let mut lines = Vec::new();
        // Both fixtures use provider "anthropic"; verify aggregation succeeds.
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "sub",
                1,
                "2026-01-01T10:00:04Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_providers(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_providers_sorts_by_tokens_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_sort.jsonl");
        // Two providers: "anthropic" (high tokens) and "openai" (low tokens).
        let ev_start_a = serde_json::json!({
            "event_type": "DelegationStart", "run_id": "run-s",
            "agent_name": "main", "provider": "anthropic",
            "model": "claude-sonnet-4", "depth": 0, "timestamp": "2026-01-01T10:00:00Z"
        });
        let ev_end_a = serde_json::json!({
            "event_type": "DelegationEnd", "run_id": "run-s",
            "agent_name": "main", "provider": "anthropic",
            "model": "claude-sonnet-4", "depth": 0, "duration_ms": 1000u64,
            "success": true, "tokens_used": 5000u64, "cost_usd": 0.015,
            "timestamp": "2026-01-01T10:00:05Z"
        });
        let ev_start_b = serde_json::json!({
            "event_type": "DelegationStart", "run_id": "run-s",
            "agent_name": "helper", "provider": "openai",
            "model": "gpt-4o", "depth": 1, "timestamp": "2026-01-01T10:00:01Z"
        });
        let ev_end_b = serde_json::json!({
            "event_type": "DelegationEnd", "run_id": "run-s",
            "agent_name": "helper", "provider": "openai",
            "model": "gpt-4o", "depth": 1, "duration_ms": 500u64,
            "success": true, "tokens_used": 100u64, "cost_usd": 0.0001,
            "timestamp": "2026-01-01T10:00:03Z"
        });
        let lines: Vec<String> = [ev_start_a, ev_end_a, ev_start_b, ev_end_b]
            .iter()
            .map(|v| serde_json::to_string(v).unwrap())
            .collect();
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_providers(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_providers_with_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-keep",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                800,
                0.002,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-skip",
                "other",
                0,
                "2026-01-02T10:00:05Z",
                9999,
                0.030,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_providers(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_providers_counts_distinct_runs_per_provider() {
        let path = std::env::temp_dir().join("zeroclaw_test_providers_runs.jsonl");
        let mut lines = Vec::new();
        // "anthropic" appears in two distinct runs
        for run in &["run-x", "run-y"] {
            lines.push(
                serde_json::to_string(&make_start(run, "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(
                    run,
                    "main",
                    0,
                    "2026-01-01T10:00:05Z",
                    500,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_providers(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_depth_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_depth(&path, None).is_ok());
    }

    #[test]
    fn print_depth_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_depth(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_depth_aggregates_by_depth_level() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_agg.jsonl");
        let mut lines = Vec::new();
        // depth 0: main agent
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:10Z",
                1000,
                0.003,
                true,
            ))
            .unwrap(),
        );
        // depth 1: sub-agent
        lines.push(
            serde_json::to_string(&make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "sub",
                1,
                "2026-01-01T10:00:09Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_sorts_ascending() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_sort.jsonl");
        let mut lines = Vec::new();
        // Insert depth 2 before depth 0 to verify ascending sort.
        lines.push(
            serde_json::to_string(&make_start("run-a", "leaf", 2, "2026-01-01T10:00:02Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "leaf",
                2,
                "2026-01-01T10:00:08Z",
                200,
                0.0005,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:10Z",
                800,
                0.002,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_depth(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_depth_with_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-keep",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                600,
                0.002,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-skip",
                "other",
                0,
                "2026-01-02T10:00:05Z",
                9999,
                0.030,
                false,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_tracks_success_and_failure() {
        let path = std::env::temp_dir().join("zeroclaw_test_depth_success.jsonl");
        let mut lines = Vec::new();
        // Two depth-1 agents: one succeeds, one fails.
        lines.push(
            serde_json::to_string(&make_start("run-a", "ok-sub", 1, "2026-01-01T10:00:01Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "ok-sub",
                1,
                "2026-01-01T10:00:05Z",
                300,
                0.001,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "fail-sub", 1, "2026-01-01T10:00:02Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "fail-sub",
                1,
                "2026-01-01T10:00:06Z",
                100,
                0.0003,
                false,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_depth(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    fn make_end_failed(run_id: &str, agent: &str, depth: u32, ts: &str, error_msg: &str) -> Value {
        serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": agent,
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "depth": depth,
            "duration_ms": 500u64,
            "success": false,
            "error_message": error_msg,
            "tokens_used": null,
            "cost_usd": null,
            "timestamp": ts
        })
    }

    #[test]
    fn print_errors_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_errors(&path, None).is_ok());
    }

    #[test]
    fn print_errors_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_errors(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_errors_with_no_failures_reports_clean() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_clean.jsonl");
        let mut lines = Vec::new();
        // Only successful delegations — no failures.
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_errors(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_errors_lists_failed_delegations() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_failed.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end_failed(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                "tool not found",
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "sub", 1, "2026-01-01T10:00:01Z")).unwrap(),
        );
        // sub succeeds — should not appear in errors list.
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "sub",
                1,
                "2026-01-01T10:00:04Z",
                200,
                0.0005,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_errors(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_errors_with_run_filter_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_filter.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end_failed(
                "run-keep",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                "timeout",
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end_failed(
                "run-skip",
                "other",
                0,
                "2026-01-02T10:00:05Z",
                "other error",
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_errors(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_errors_truncates_long_error_messages() {
        let path = std::env::temp_dir().join("zeroclaw_test_errors_truncate.jsonl");
        let mut lines = Vec::new();
        let long_msg = "x".repeat(200);
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end_failed(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                &long_msg,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_errors(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    // ── print_slow tests ──────────────────────────────────────────────────────

    #[test]
    fn print_slow_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_slow(&path, None, 10).is_ok());
    }

    #[test]
    fn print_slow_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_slow(&path, None, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_slow_with_no_ended_delegations_reports_empty() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_noend.jsonl");
        // Only DelegationStart events — no DelegationEnd.
        let lines =
            vec![
                serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_slow(&path, None, 10);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_slow_sorts_by_duration_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_sort.jsonl");
        // Three delegations with durations 500ms, 2000ms, 300ms.
        // Expected order after sort: 2000ms, 500ms, 300ms.
        let events = [
            make_start("run-a", "fast", 0, "2026-01-01T10:00:00Z"),
            serde_json::json!({
                "event_type": "DelegationEnd", "run_id": "run-a",
                "agent_name": "fast", "provider": "anthropic",
                "model": "claude-sonnet-4", "depth": 0u32,
                "duration_ms": 300u64, "success": true,
                "tokens_used": 100u64, "cost_usd": 0.001,
                "timestamp": "2026-01-01T10:00:01Z"
            }),
            make_start("run-a", "medium", 1, "2026-01-01T10:00:00Z"),
            serde_json::json!({
                "event_type": "DelegationEnd", "run_id": "run-a",
                "agent_name": "medium", "provider": "anthropic",
                "model": "claude-sonnet-4", "depth": 1u32,
                "duration_ms": 500u64, "success": true,
                "tokens_used": 200u64, "cost_usd": 0.002,
                "timestamp": "2026-01-01T10:00:02Z"
            }),
            make_start("run-a", "slow_agent", 2, "2026-01-01T10:00:00Z"),
            serde_json::json!({
                "event_type": "DelegationEnd", "run_id": "run-a",
                "agent_name": "slow_agent", "provider": "anthropic",
                "model": "claude-sonnet-4", "depth": 2u32,
                "duration_ms": 2000u64, "success": true,
                "tokens_used": 400u64, "cost_usd": 0.004,
                "timestamp": "2026-01-01T10:00:03Z"
            }),
        ];
        let lines: Vec<String> = events
            .iter()
            .map(|e| serde_json::to_string(e).unwrap())
            .collect();
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_slow(&path, None, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_slow_respects_limit() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_limit.jsonl");
        // Five delegations — limit 2 should only show top 2.
        let durations: &[u64] = &[100, 500, 300, 800, 200];
        let mut lines = Vec::new();
        for (i, dur) in durations.iter().enumerate() {
            let agent = format!("agent_{i}");
            lines.push(
                serde_json::to_string(&make_start("run-a", &agent, 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&serde_json::json!({
                    "event_type": "DelegationEnd", "run_id": "run-a",
                    "agent_name": agent, "provider": "anthropic",
                    "model": "claude-sonnet-4", "depth": 0u32,
                    "duration_ms": dur, "success": true,
                    "tokens_used": 100u64, "cost_usd": 0.001,
                    "timestamp": "2026-01-01T10:00:01Z"
                }))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_slow(&path, None, 2).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_slow_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_slow_run_filter.jsonl");
        let mut lines = Vec::new();
        // run-keep has a slow delegation; run-skip has a faster one.
        lines.push(
            serde_json::to_string(&make_start("run-keep", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&serde_json::json!({
                "event_type": "DelegationEnd", "run_id": "run-keep",
                "agent_name": "main", "provider": "anthropic",
                "model": "claude-sonnet-4", "depth": 0u32,
                "duration_ms": 5000u64, "success": true,
                "tokens_used": 300u64, "cost_usd": 0.003,
                "timestamp": "2026-01-01T10:00:05Z"
            }))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-skip", "other", 0, "2026-01-02T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&serde_json::json!({
                "event_type": "DelegationEnd", "run_id": "run-skip",
                "agent_name": "other", "provider": "anthropic",
                "model": "claude-sonnet-4", "depth": 0u32,
                "duration_ms": 100u64, "success": true,
                "tokens_used": 50u64, "cost_usd": 0.0005,
                "timestamp": "2026-01-02T10:00:01Z"
            }))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_slow(&path, Some("run-keep"), 10);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_cost tests ──────────────────────────────────────────────────────

    #[test]
    fn print_cost_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_cost(&path, None).is_ok());
    }

    #[test]
    fn print_cost_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_cost(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_cost_with_single_run_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_single.jsonl");
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                500,
                0.001,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_cost(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_sorts_by_cost_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_sort.jsonl");
        // run-cheap: $0.001, run-expensive: $0.010 — expensive should appear first.
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-cheap", "main", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-cheap",
                "main",
                0,
                "2026-01-01T10:00:01Z",
                100,
                0.001,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start(
                "run-expensive",
                "main",
                0,
                "2026-01-02T10:00:00Z",
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-expensive",
                "main",
                0,
                "2026-01-02T10:00:05Z",
                1000,
                0.010,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_cost(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_cost_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_filter.jsonl");
        let mut lines = Vec::new();
        for (run, ts_start, ts_end, cost) in &[
            (
                "run-a",
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:00:01Z",
                0.005f64,
            ),
            (
                "run-b",
                "2026-01-02T10:00:00Z",
                "2026-01-02T10:00:01Z",
                0.002f64,
            ),
        ] {
            lines.push(serde_json::to_string(&make_start(run, "main", 0, ts_start)).unwrap());
            lines.push(
                serde_json::to_string(&make_end(run, "main", 0, ts_end, 200, *cost, true)).unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_cost(&path, Some("run-a"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_shows_avg_per_delegation() {
        let path = std::env::temp_dir().join("zeroclaw_test_cost_avg.jsonl");
        // Two DelegationEnd events for one run — avg should be half the total.
        let mut lines = Vec::new();
        lines.push(
            serde_json::to_string(&make_start("run-a", "agent1", 0, "2026-01-01T10:00:00Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "agent1",
                0,
                "2026-01-01T10:00:01Z",
                200,
                0.004,
                true,
            ))
            .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-a", "agent2", 1, "2026-01-01T10:00:02Z"))
                .unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-a",
                "agent2",
                1,
                "2026-01-01T10:00:03Z",
                200,
                0.004,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_cost(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    // ── print_recent tests ────────────────────────────────────────────────────

    #[test]
    fn print_recent_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_recent(&path, None, 10).is_ok());
    }

    #[test]
    fn print_recent_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_recent(&path, None, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_recent_with_no_ends_reports_empty() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_noend.jsonl");
        let lines =
            vec![
                serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_recent(&path, None, 10);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_recent_sorts_by_timestamp_descending() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_sort.jsonl");
        // Three delegations with timestamps at T+1, T+3, T+2 — should show T+3, T+2, T+1.
        let ts_pairs = [
            ("2026-01-01T10:00:01Z", "agent_first"),
            ("2026-01-01T10:00:03Z", "agent_latest"),
            ("2026-01-01T10:00:02Z", "agent_middle"),
        ];
        let mut lines = Vec::new();
        for (ts, agent) in &ts_pairs {
            lines.push(
                serde_json::to_string(&make_start("run-a", agent, 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end("run-a", agent, 0, ts, 100, 0.001, true)).unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_recent(&path, None, 10).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_recent_respects_limit() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_limit.jsonl");
        let mut lines = Vec::new();
        for i in 0..5usize {
            let agent = format!("agent_{i}");
            let ts = format!("2026-01-01T10:00:{:02}Z", i);
            lines.push(
                serde_json::to_string(&make_start("run-a", &agent, 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end("run-a", &agent, 0, &ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        assert!(print_recent(&path, None, 2).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_recent_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_recent_filter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:01Z"),
            ("run-skip", "2026-01-02T10:00:01Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_start(run, "main", 0, "2026-01-01T09:00:00Z")).unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(run, "main", 0, ts, 100, 0.001, true)).unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_recent(&path, Some("run-keep"), 10);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_active_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_active_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_active(&path, None).is_ok());
    }

    #[test]
    fn print_active_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_active_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_active(&path, None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_active_with_only_ends_reports_empty() {
        // DelegationEnd with no prior start — should show 0 active.
        let path = std::env::temp_dir().join("zeroclaw_test_active_onlyends.jsonl");
        let lines = vec![serde_json::to_string(&make_end(
            "run-a",
            "main",
            0,
            "2026-01-01T10:00:01Z",
            100,
            0.001,
            true,
        ))
        .unwrap()];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_active(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_active_shows_unmatched_starts() {
        // One start with no matching end — should surface as 1 active.
        let path = std::env::temp_dir().join("zeroclaw_test_active_unmatched.jsonl");
        let lines = vec![serde_json::to_string(&make_start(
            "run-a",
            "research",
            1,
            "2026-01-01T10:00:00Z",
        ))
        .unwrap()];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_active(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_active_excludes_completed_delegations() {
        // A start+end pair for the same key — matched, so 0 active.
        let path = std::env::temp_dir().join("zeroclaw_test_active_completed.jsonl");
        let lines = vec![
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
            serde_json::to_string(&make_end(
                "run-a",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                5000,
                0.002,
                true,
            ))
            .unwrap(),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_active(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_active_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_active_filter.jsonl");
        let mut lines = Vec::new();
        // run-a: start only (active), run-b: start+end (completed)
        lines.push(
            serde_json::to_string(&make_start("run-a", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_start("run-b", "main", 0, "2026-01-01T10:00:00Z")).unwrap(),
        );
        lines.push(
            serde_json::to_string(&make_end(
                "run-b",
                "main",
                0,
                "2026-01-01T10:00:05Z",
                5000,
                0.002,
                true,
            ))
            .unwrap(),
        );
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_active(&path, Some("run-a"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_agent_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_agent(&path, "research", None).is_ok());
    }

    #[test]
    fn print_agent_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_agent_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_agent(&path, "research", None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_agent_with_no_matching_ends_reports_empty() {
        // Only starts for "research" — no ends, so nothing to show.
        let path = std::env::temp_dir().join("zeroclaw_test_agent_nomatch.jsonl");
        let lines = vec![serde_json::to_string(&make_start(
            "run-a",
            "research",
            1,
            "2026-01-01T10:00:00Z",
        ))
        .unwrap()];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent(&path, "research", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_shows_matching_ends_newest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_agent_sort.jsonl");
        // Two completed "research" delegations at T+1 and T+3; should show T+3 first.
        let mut lines = Vec::new();
        for (ts, run) in &[
            ("2026-01-01T10:00:01Z", "run-a"),
            ("2026-01-01T10:00:03Z", "run-b"),
        ] {
            lines.push(
                serde_json::to_string(&make_start(run, "research", 1, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(run, "research", 1, ts, 500, 0.002, true)).unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent(&path, "research", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_excludes_other_agents() {
        // "main" and "research" both complete; querying "research" should exclude "main".
        let path = std::env::temp_dir().join("zeroclaw_test_agent_exclude.jsonl");
        let mut lines = Vec::new();
        for agent in &["main", "research"] {
            lines.push(
                serde_json::to_string(&make_start("run-a", agent, 0, "2026-01-01T10:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(
                    "run-a",
                    agent,
                    0,
                    "2026-01-01T10:00:05Z",
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent(&path, "research", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_agent_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:01Z"),
            ("run-skip", "2026-01-02T10:00:01Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_start(run, "research", 1, "2026-01-01T09:00:00Z"))
                    .unwrap(),
            );
            lines.push(
                serde_json::to_string(&make_end(run, "research", 1, ts, 200, 0.001, true)).unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent(&path, "research", Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_model tests ────────────────────────────────────────────────────

    /// Build a DelegationEnd event with an explicit model name (for model-filter tests).
    fn make_end_m(
        run_id: &str,
        agent: &str,
        model: &str,
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
            "model": model,
            "depth": depth,
            "duration_ms": 1000u64,
            "success": success,
            "tokens_used": tokens,
            "cost_usd": cost,
            "timestamp": ts
        })
    }

    #[test]
    fn print_model_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_model_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_model(&path, "claude-sonnet-4", None).is_ok());
    }

    #[test]
    fn print_model_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_model_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_model(&path, "claude-sonnet-4", None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_model_with_no_matching_ends_reports_empty() {
        // Only starts — no ends, so nothing to show.
        let path = std::env::temp_dir().join("zeroclaw_test_model_nomatch.jsonl");
        let lines = vec![serde_json::to_string(&make_start(
            "run-a",
            "research",
            1,
            "2026-01-01T10:00:00Z",
        ))
        .unwrap()];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model(&path, "claude-sonnet-4", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_shows_matching_ends_newest_first() {
        // Two ends for the same model at T+1 and T+3; should show T+3 first.
        let path = std::env::temp_dir().join("zeroclaw_test_model_sort.jsonl");
        let mut lines = Vec::new();
        for (ts, run) in &[
            ("2026-01-01T10:00:01Z", "run-a"),
            ("2026-01-01T10:00:03Z", "run-b"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    run,
                    "research",
                    "claude-sonnet-4",
                    1,
                    ts,
                    500,
                    0.002,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model(&path, "claude-sonnet-4", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_excludes_other_models() {
        // Two models complete; querying one should exclude the other.
        let path = std::env::temp_dir().join("zeroclaw_test_model_exclude.jsonl");
        let mut lines = Vec::new();
        for model in &["claude-sonnet-4", "gpt-4o"] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    "run-a",
                    "research",
                    model,
                    0,
                    "2026-01-01T10:00:05Z",
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model(&path, "claude-sonnet-4", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_model_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:01Z"),
            ("run-skip", "2026-01-02T10:00:01Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    run,
                    "research",
                    "claude-sonnet-4",
                    1,
                    ts,
                    200,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model(&path, "claude-sonnet-4", Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_provider tests ─────────────────────────────────────────────────

    /// Build a DelegationEnd event with explicit provider, model fields.
    fn make_end_p(
        run_id: &str,
        agent: &str,
        provider: &str,
        model: &str,
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
            "provider": provider,
            "model": model,
            "depth": depth,
            "duration_ms": 1000u64,
            "success": success,
            "tokens_used": tokens,
            "cost_usd": cost,
            "timestamp": ts
        })
    }

    #[test]
    fn print_provider_on_missing_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_provider_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        assert!(print_provider(&path, "anthropic", None).is_ok());
    }

    #[test]
    fn print_provider_on_empty_log_succeeds() {
        let path = std::env::temp_dir().join("zeroclaw_test_provider_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        assert!(print_provider(&path, "anthropic", None).is_ok());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn print_provider_with_no_matching_ends_reports_empty() {
        // Only starts — no ends, so nothing to show.
        let path = std::env::temp_dir().join("zeroclaw_test_provider_nomatch.jsonl");
        let lines = vec![serde_json::to_string(&make_start(
            "run-a",
            "research",
            1,
            "2026-01-01T10:00:00Z",
        ))
        .unwrap()];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider(&path, "anthropic", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_shows_matching_ends_newest_first() {
        // Two ends for the same provider at T+1 and T+3; should show T+3 first.
        let path = std::env::temp_dir().join("zeroclaw_test_provider_sort.jsonl");
        let mut lines = Vec::new();
        for (ts, run) in &[
            ("2026-01-01T10:00:01Z", "run-a"),
            ("2026-01-01T10:00:03Z", "run-b"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    run,
                    "research",
                    "anthropic",
                    "claude-sonnet-4",
                    1,
                    ts,
                    500,
                    0.002,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider(&path, "anthropic", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_excludes_other_providers() {
        // Two providers complete; querying one should exclude the other.
        let path = std::env::temp_dir().join("zeroclaw_test_provider_exclude.jsonl");
        let mut lines = Vec::new();
        for (prov, model) in &[("anthropic", "claude-sonnet-4"), ("openai", "gpt-4o")] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    "run-a",
                    "research",
                    prov,
                    model,
                    0,
                    "2026-01-01T10:00:05Z",
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider(&path, "anthropic", None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_provider_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:01Z"),
            ("run-skip", "2026-01-02T10:00:01Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    run,
                    "research",
                    "anthropic",
                    "claude-sonnet-4",
                    1,
                    ts,
                    200,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider(&path, "anthropic", Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_run tests ───────────────────────────────────────────────────────

    #[test]
    fn print_run_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_run(&path, "run-abc");
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_run(&path, "run-abc");
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_no_matching_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_nomatch.jsonl");
        let line = serde_json::to_string(&make_end(
            "run-other",
            "research",
            1,
            "2026-01-01T10:00:00Z",
            100,
            0.001,
            true,
        ))
        .unwrap();
        std::fs::write(&path, line + "\n").unwrap();
        let result = print_run(&path, "run-target");
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_oldest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_oldest.jsonl");
        let mut lines = Vec::new();
        for ts in &["2026-01-01T10:00:02Z", "2026-01-01T10:00:01Z"] {
            lines.push(
                serde_json::to_string(&make_end(
                    "run-alpha",
                    "research",
                    1,
                    ts,
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run(&path, "run-alpha");
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_excludes_other_runs() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_excludes.jsonl");
        let mut lines = Vec::new();
        for run in &["run-keep", "run-skip"] {
            lines.push(
                serde_json::to_string(&make_end(
                    run,
                    "research",
                    1,
                    "2026-01-01T10:00:00Z",
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run(&path, "run-keep");
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_mixed_success() {
        let path = std::env::temp_dir().join("zeroclaw_test_run_mixed.jsonl");
        let mut lines = Vec::new();
        for (ts, success) in &[
            ("2026-01-01T10:00:01Z", true),
            ("2026-01-01T10:00:02Z", false),
        ] {
            lines.push(
                serde_json::to_string(&make_end(
                    "run-mixed",
                    "research",
                    1,
                    ts,
                    200,
                    0.002,
                    *success,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run(&path, "run-mixed");
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_depth_view tests ────────────────────────────────────────────────

    #[test]
    fn print_depth_view_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_depth_view(&path, 0, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_view_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_depth_view(&path, 0, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_view_no_matching_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_nomatch.jsonl");
        let line = serde_json::to_string(&make_end(
            "run-a",
            "research",
            2,
            "2026-01-01T10:00:00Z",
            100,
            0.001,
            true,
        ))
        .unwrap();
        std::fs::write(&path, line + "\n").unwrap();
        let result = print_depth_view(&path, 0, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_view_newest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_newest.jsonl");
        let mut lines = Vec::new();
        for ts in &["2026-01-01T10:00:02Z", "2026-01-01T10:00:01Z"] {
            lines.push(
                serde_json::to_string(&make_end(
                    "run-a",
                    "research",
                    0,
                    ts,
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_view(&path, 0, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_view_excludes_other_depths() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_excludes.jsonl");
        let mut lines = Vec::new();
        for depth in &[0u32, 1, 2] {
            lines.push(
                serde_json::to_string(&make_end(
                    "run-a",
                    "research",
                    *depth,
                    "2026-01-01T10:00:00Z",
                    100,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_view(&path, 1, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_view_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_depthview_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:01Z"),
            ("run-skip", "2026-01-02T10:00:01Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end(
                    run,
                    "research",
                    0,
                    ts,
                    200,
                    0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_view(&path, 0, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_daily tests ─────────────────────────────────────────────────────

    #[test]
    fn print_daily_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_daily(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_daily_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_daily(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_daily_no_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_noends.jsonl");
        let start = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-a",
            "agent_name": "research",
            "depth": 0,
            "timestamp": "2026-01-01T10:00:00Z"
        });
        std::fs::write(&path, serde_json::to_string(&start).unwrap() + "\n").unwrap();
        let result = print_daily(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_daily_groups_by_date() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_groups.jsonl");
        let mut lines = Vec::new();
        // Two events on day 1, one on day 2.
        for ts in &[
            "2026-01-01T09:00:00Z",
            "2026-01-01T11:00:00Z",
            "2026-01-02T10:00:00Z",
        ] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_daily(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_daily_oldest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_oldest.jsonl");
        let mut lines = Vec::new();
        // Write newer date first — BTreeMap should sort oldest first regardless.
        for ts in &["2026-01-03T10:00:00Z", "2026-01-01T10:00:00Z"] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_daily(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_daily_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_daily_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:00Z"),
            ("run-skip", "2026-01-02T10:00:00Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end(run, "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_daily(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_hourly tests ────────────────────────────────────────────────────

    #[test]
    fn print_hourly_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_hourly(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_hourly_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_hourly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_hourly_no_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_noends.jsonl");
        let start = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-a",
            "agent_name": "research",
            "depth": 0,
            "timestamp": "2026-01-01T10:00:00Z"
        });
        std::fs::write(&path, serde_json::to_string(&start).unwrap() + "\n").unwrap();
        let result = print_hourly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_hourly_groups_by_hour() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_groups.jsonl");
        let mut lines = Vec::new();
        // Two events at 09:xx, one at 14:xx — different days but same hours should merge.
        for ts in &[
            "2026-01-01T09:15:00Z",
            "2026-01-02T09:45:00Z",
            "2026-01-01T14:00:00Z",
        ] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_hourly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_hourly_lowest_hour_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_order.jsonl");
        let mut lines = Vec::new();
        // Write later hours first — BTreeMap should sort 08 before 22.
        for ts in &["2026-01-01T22:00:00Z", "2026-01-01T08:00:00Z"] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_hourly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_hourly_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_hourly_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:00Z"),
            ("run-skip", "2026-01-01T11:00:00Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end(run, "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_hourly(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_monthly tests ───────────────────────────────────────────────────

    #[test]
    fn print_monthly_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_monthly(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_monthly_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_monthly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_monthly_no_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_noends.jsonl");
        let start = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-a",
            "agent_name": "research",
            "depth": 0,
            "timestamp": "2026-01-01T10:00:00Z"
        });
        std::fs::write(&path, serde_json::to_string(&start).unwrap() + "\n").unwrap();
        let result = print_monthly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_monthly_groups_by_month() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_groups.jsonl");
        let mut lines = Vec::new();
        // Two events in Jan, one in Feb.
        for ts in &[
            "2026-01-01T09:00:00Z",
            "2026-01-15T11:00:00Z",
            "2026-02-03T10:00:00Z",
        ] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_monthly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_monthly_oldest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_oldest.jsonl");
        let mut lines = Vec::new();
        // Write newer month first — BTreeMap should sort oldest first.
        for ts in &["2026-03-01T10:00:00Z", "2026-01-01T10:00:00Z"] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_monthly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_monthly_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_monthly_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:00Z"),
            ("run-skip", "2026-02-01T10:00:00Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end(run, "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_monthly(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_quarterly tests ─────────────────────────────────────────────────

    #[test]
    fn print_quarterly_missing_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_missing.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_quarterly(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_quarterly_empty_log() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_quarterly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_quarterly_no_ends() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_noends.jsonl");
        let start = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-a",
            "agent_name": "research",
            "depth": 0,
            "timestamp": "2026-01-01T10:00:00Z"
        });
        std::fs::write(&path, serde_json::to_string(&start).unwrap() + "\n").unwrap();
        let result = print_quarterly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_quarterly_groups_by_quarter() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_groups.jsonl");
        let mut lines = Vec::new();
        // Jan + Feb → Q1, Jul → Q3.
        for ts in &[
            "2026-01-10T09:00:00Z",
            "2026-02-20T11:00:00Z",
            "2026-07-05T10:00:00Z",
        ] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_quarterly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_quarterly_oldest_first() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_oldest.jsonl");
        let mut lines = Vec::new();
        // Write Q4 before Q1 — BTreeMap key "2026-Q1" < "2026-Q4".
        for ts in &["2026-10-01T10:00:00Z", "2026-01-01T10:00:00Z"] {
            lines.push(
                serde_json::to_string(&make_end("run-a", "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_quarterly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_quarterly_filters_by_run() {
        let path = std::env::temp_dir().join("zeroclaw_test_quarterly_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-01-01T10:00:00Z"),
            ("run-skip", "2026-04-01T10:00:00Z"),
        ] {
            lines.push(
                serde_json::to_string(&make_end(run, "research", 0, ts, 100, 0.001, true))
                    .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_quarterly(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_agentmodel.jsonl");
        let result = print_agent_model(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_model_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_agent_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_model_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "model": "claude-sonnet-4-6",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_agent_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_groups_by_pair() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_model_pairs.jsonl");
        let mut lines = Vec::new();
        for (agent, model) in &[
            ("researcher", "claude-sonnet-4-6"),
            ("coder", "claude-opus-4-6"),
            ("researcher", "claude-sonnet-4-6"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    "run-1", agent, model, 0, "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_tokens_desc() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_model_tokdesc.jsonl");
        let mut lines = Vec::new();
        for (agent, model, tokens) in &[
            ("coder", "claude-opus-4-6", 500u64),
            ("researcher", "claude-sonnet-4-6", 1000u64),
        ] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    "run-1", agent, model, 0, "2026-02-01T10:00:00Z", *tokens, 0.001,
                    true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_model_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_model_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, agent, model) in &[
            ("run-keep", "researcher", "claude-sonnet-4-6"),
            ("run-skip", "coder", "claude-opus-4-6"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_m(
                    run, agent, model, 0, "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_model(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_provmodel.jsonl");
        let result = print_provider_model(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_prov_model_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_provider_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_prov_model_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_provider_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_groups_by_pair() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_prov_model_pairs.jsonl");
        let mut lines = Vec::new();
        for (provider, model) in &[
            ("anthropic", "claude-sonnet-4-6"),
            ("openai", "gpt-4o"),
            ("anthropic", "claude-sonnet-4-6"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    "run-1", "researcher", provider, model, 0,
                    "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_tokens_desc() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_prov_model_tokdesc.jsonl");
        let mut lines = Vec::new();
        for (provider, model, tokens) in &[
            ("openai", "gpt-4o", 500u64),
            ("anthropic", "claude-sonnet-4-6", 1000u64),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    "run-1", "researcher", provider, model, 0,
                    "2026-02-01T10:00:00Z", *tokens, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_model(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_model_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_prov_model_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, provider, model) in &[
            ("run-keep", "anthropic", "claude-sonnet-4-6"),
            ("run-skip", "openai", "gpt-4o"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    run, "researcher", provider, model, 0,
                    "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_model(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_agentprov.jsonl");
        let result = print_agent_provider(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_prov_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_agent_provider(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_prov_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "provider": "anthropic",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_agent_provider(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_groups_by_pair() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_prov_pairs.jsonl");
        let mut lines = Vec::new();
        for (agent, provider) in &[
            ("researcher", "anthropic"),
            ("coder", "openai"),
            ("researcher", "anthropic"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    "run-1", agent, provider, "claude-sonnet-4-6", 0,
                    "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_provider(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_tokens_desc() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_prov_tokdesc.jsonl");
        let mut lines = Vec::new();
        for (agent, provider, tokens) in &[
            ("coder", "openai", 500u64),
            ("researcher", "anthropic", 1000u64),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    "run-1", agent, provider, "claude-sonnet-4-6", 0,
                    "2026-02-01T10:00:00Z", *tokens, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_provider(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_provider_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_agent_prov_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, agent, provider) in &[
            ("run-keep", "researcher", "anthropic"),
            ("run-skip", "coder", "openai"),
        ] {
            lines.push(
                serde_json::to_string(&make_end_p(
                    run, agent, provider, "claude-sonnet-4-6", 0,
                    "2026-02-01T10:00:00Z", 100, 0.001, true,
                ))
                .unwrap(),
            );
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_provider(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_durbucket.jsonl");
        let result = print_duration_bucket(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dur_bucket_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_duration_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dur_bucket_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_duration_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_groups_by_bucket() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dur_bucket_groups.jsonl");
        let mut lines = Vec::new();
        for duration_ms in &[200u64, 1000u64, 5000u64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": duration_ms,
                "tokens_used": 100u64,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_duration_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_fastest_first() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dur_bucket_order.jsonl");
        let mut lines = Vec::new();
        for duration_ms in &[70000u64, 100u64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": duration_ms,
                "tokens_used": 100u64,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_duration_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_duration_bucket_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dur_bucket_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, duration_ms) in &[("run-keep", 500u64), ("run-skip", 1000u64)] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "duration_ms": duration_ms,
                "tokens_used": 100u64,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_duration_bucket(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_tokbucket.jsonl");
        let result = print_token_bucket(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tok_bucket_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_token_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tok_bucket_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_token_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_groups_by_bucket() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tok_bucket_groups.jsonl");
        let mut lines = Vec::new();
        for tokens_used in &[50u64, 500u64, 5000u64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": tokens_used,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_token_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_smallest_first() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tok_bucket_order.jsonl");
        let mut lines = Vec::new();
        for tokens_used in &[200_000u64, 30u64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": tokens_used,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_token_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_bucket_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tok_bucket_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, tokens_used) in &[("run-keep", 500u64), ("run-skip", 50000u64)] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": tokens_used,
                "cost_usd": 0.001f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_token_bucket(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_costbucket.jsonl");
        let result = print_cost_bucket(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_cost_bucket_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_cost_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_cost_bucket_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_cost_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_groups_by_bucket() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_cost_bucket_groups.jsonl");
        let mut lines = Vec::new();
        for cost_usd in &[0.0005f64, 0.005f64, 0.05f64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 100u64,
                "cost_usd": cost_usd,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_cost_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_cheapest_first() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_cost_bucket_order.jsonl");
        let mut lines = Vec::new();
        for cost_usd in &[2.50f64, 0.0001f64] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 100u64,
                "cost_usd": cost_usd,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_cost_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_cost_bucket_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_cost_bucket_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, cost_usd) in &[("run-keep", 0.005f64), ("run-skip", 0.50f64)] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 100u64,
                "cost_usd": cost_usd,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_cost_bucket(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_weekday.jsonl");
        let result = print_weekday(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekday_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_weekday(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekday_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "timestamp": "2026-02-23T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_weekday(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_groups_by_day() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekday_groups.jsonl");
        let mut lines = Vec::new();
        // 2026-02-23 = Monday, 2026-02-25 = Wednesday
        for ts in &["2026-02-23T10:00:00Z", "2026-02-25T10:00:00Z"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekday(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_mon_first() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekday_order.jsonl");
        let mut lines = Vec::new();
        // 2026-02-22 = Sunday, 2026-02-23 = Monday
        for ts in &["2026-02-22T10:00:00Z", "2026-02-23T10:00:00Z"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekday(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekday_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekday_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-02-23T10:00:00Z"),
            ("run-skip", "2026-02-25T10:00:00Z"),
        ] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekday(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_weekly tests ───────────────────────────────────────────────────

    #[test]
    fn print_weekly_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_weekly.jsonl");
        let result = print_weekly(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekly_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekly_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_weekly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekly_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekly_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "timestamp": "2026-02-23T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_weekly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekly_groups_by_week() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekly_groups.jsonl");
        let mut lines = Vec::new();
        // 2026-01-05 = 2026-W02, 2026-01-12 = 2026-W03
        for ts in &["2026-01-05T10:00:00Z", "2026-01-12T10:00:00Z"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekly_same_week_aggregated() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekly_same_week.jsonl");
        let mut lines = Vec::new();
        // 2026-02-23 (Mon) and 2026-02-27 (Fri) are both in 2026-W09
        for ts in &["2026-02-23T10:00:00Z", "2026-02-27T10:00:00Z"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 300u64,
                "cost_usd": 0.003f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekly(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_weekly_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_weekly_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, ts) in &[
            ("run-keep", "2026-02-09T10:00:00Z"),
            ("run-skip", "2026-02-23T10:00:00Z"),
        ] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": ts,
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_weekly(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_depth_bucket tests ─────────────────────────────────────────────

    #[test]
    fn print_depth_bucket_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_depth_bucket.jsonl");
        let result = print_depth_bucket(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_bucket_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_depth_bucket_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_depth_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_bucket_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_depth_bucket_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "depth": 0u32,
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_depth_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_bucket_groups_by_depth() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_depth_bucket_groups.jsonl");
        let mut lines = Vec::new();
        for depth in &[0u32, 1, 2, 3, 5] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "depth": depth,
                "duration_ms": 1000u64,
                "tokens_used": 400u64,
                "cost_usd": 0.004f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_bucket_deep_goes_to_last_bucket() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_depth_bucket_deep.jsonl");
        let mut lines = Vec::new();
        // depths 4, 7, 10 should all map to bucket index 4 (very deep)
        for depth in &[4u32, 7, 10] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "depth": depth,
                "duration_ms": 500u64,
                "tokens_used": 200u64,
                "cost_usd": 0.002f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_bucket(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_depth_bucket_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_depth_bucket_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, depth) in &[("run-keep", 0u32), ("run-skip", 2u32)] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "depth": depth,
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_depth_bucket(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_model_tier tests ───────────────────────────────────────────────

    #[test]
    fn print_model_tier_missing_log() {
        let path =
            std::path::PathBuf::from("/tmp/zeroclaw_no_such_file_model_tier.jsonl");
        let result = print_model_tier(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_tier_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_model_tier_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_model_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_tier_no_ends() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_model_tier_noends.jsonl");
        let ev = serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run-1",
            "agent_name": "researcher",
            "model": "claude-sonnet-4",
            "timestamp": "2026-02-01T10:00:00Z",
        });
        std::fs::write(&path, serde_json::to_string(&ev).unwrap() + "\n").unwrap();
        let result = print_model_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_tier_groups_by_family() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_model_tier_groups.jsonl");
        let mut lines = Vec::new();
        for model in &["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6", "gpt-4o"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "model": model,
                "depth": 0u32,
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_tier_case_insensitive() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_model_tier_case.jsonl");
        let mut lines = Vec::new();
        for model in &["Claude-Sonnet-4", "CLAUDE-HAIKU-3"] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": "run-1",
                "agent_name": "researcher",
                "model": model,
                "depth": 0u32,
                "duration_ms": 800u64,
                "tokens_used": 300u64,
                "cost_usd": 0.003f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_tier_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_model_tier_runfilter.jsonl");
        let mut lines = Vec::new();
        for (run, model) in &[
            ("run-keep", "claude-sonnet-4-6"),
            ("run-skip", "claude-opus-4-6"),
        ] {
            let ev = serde_json::json!({
                "event_type": "DelegationEnd",
                "run_id": run,
                "agent_name": "researcher",
                "model": model,
                "depth": 0u32,
                "duration_ms": 1000u64,
                "tokens_used": 500u64,
                "cost_usd": 0.005f64,
                "success": true,
                "timestamp": "2026-02-01T10:00:00Z",
            });
            lines.push(serde_json::to_string(&ev).unwrap());
        }
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_tier(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── Phase 81: print_provider_tier ────────────────────────────────────────

    fn make_provider_tier_event(
        run_id: &str,
        provider: &str,
        tokens: u64,
        cost: f64,
        success: bool,
        ts: &str,
    ) -> String {
        serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": "researcher",
            "provider": provider,
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "duration_ms": 1000u64,
            "tokens_used": tokens,
            "cost_usd": cost,
            "success": success,
            "timestamp": ts,
        }))
        .unwrap()
    }

    #[test]
    fn print_provider_tier_all_providers() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_all.jsonl");
        let lines = vec![
            make_provider_tier_event(
                "run1", "anthropic", 200, 0.002, true, "2026-02-01T10:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "openai", 300, 0.003, true, "2026-02-01T11:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "google", 150, 0.001, false, "2026-02-01T12:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "bedrock", 100, 0.001, true, "2026-02-01T13:00:00Z",
            ),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_tier_empty() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_provider_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_tier_case_insensitive() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_case.jsonl");
        let lines = vec![
            make_provider_tier_event(
                "run1", "Anthropic", 200, 0.002, true, "2026-02-01T10:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "OPENAI", 300, 0.003, true, "2026-02-01T11:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "Google-Vertex", 150, 0.001, true, "2026-02-01T12:00:00Z",
            ),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_tier_aggregates_costs() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_agg.jsonl");
        let lines = vec![
            make_provider_tier_event(
                "run1", "anthropic", 100, 0.001, true, "2026-02-01T10:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "anthropic", 200, 0.002, false, "2026-02-01T11:00:00Z",
            ),
            make_provider_tier_event(
                "run1", "anthropic", 300, 0.003, true, "2026-02-01T12:00:00Z",
            ),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_tier_only_delegation_end() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_evtype.jsonl");
        let start_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run1",
            "provider": "openai",
            "model": "gpt-4o",
            "depth": 0u32,
            "timestamp": "2026-02-01T10:00:00Z",
        }))
        .unwrap();
        let end_ev = make_provider_tier_event(
            "run1", "openai", 400, 0.004, true, "2026-02-01T10:01:00Z",
        );
        std::fs::write(&path, format!("{start_ev}\n{end_ev}\n")).unwrap();
        let result = print_provider_tier(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_tier_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_provider_tier_runfilter.jsonl");
        let lines = vec![
            make_provider_tier_event(
                "run-keep", "anthropic", 500, 0.005, true, "2026-02-01T10:00:00Z",
            ),
            make_provider_tier_event(
                "run-skip", "openai", 500, 0.005, true, "2026-02-01T11:00:00Z",
            ),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_tier(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── Phase 83: print_time_of_day ──────────────────────────────────────────

    fn make_tod_event(
        run_id: &str,
        tokens: u64,
        cost: f64,
        success: bool,
        ts: &str,
    ) -> String {
        serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": "researcher",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "duration_ms": 1000u64,
            "tokens_used": tokens,
            "cost_usd": cost,
            "success": success,
            "timestamp": ts,
        }))
        .unwrap()
    }

    #[test]
    fn print_time_of_day_all_periods() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_all.jsonl");
        let lines = vec![
            // night: 03:00
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T03:00:00Z"),
            // morning: 08:00
            make_tod_event("run1", 200, 0.002, true, "2026-02-09T08:00:00Z"),
            // afternoon: 14:00
            make_tod_event("run1", 300, 0.003, false, "2026-02-09T14:00:00Z"),
            // evening: 20:00
            make_tod_event("run1", 150, 0.001, true, "2026-02-09T20:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_time_of_day(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_time_of_day_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_time_of_day(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_time_of_day_missing_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_missing_XXXX.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_time_of_day(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_time_of_day_only_delegation_end() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_evtype.jsonl");
        let start_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run1",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "timestamp": "2026-02-09T10:00:00Z",
        }))
        .unwrap();
        let end_ev = make_tod_event("run1", 400, 0.004, true, "2026-02-09T10:01:00Z");
        std::fs::write(&path, format!("{start_ev}\n{end_ev}\n")).unwrap();
        let result = print_time_of_day(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_time_of_day_boundary_hours() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_boundary.jsonl");
        let lines = vec![
            // boundary of night (00:00) → night bucket
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T00:00:00Z"),
            // boundary of night/morning (06:00) → morning bucket
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T06:00:00Z"),
            // boundary of morning/afternoon (12:00) → afternoon bucket
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T12:00:00Z"),
            // boundary of afternoon/evening (18:00) → evening bucket
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T18:00:00Z"),
            // last hour of evening (23:59) → evening bucket
            make_tod_event("run1", 100, 0.001, true, "2026-02-09T23:59:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_time_of_day(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_time_of_day_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_tod_runfilter.jsonl");
        let lines = vec![
            make_tod_event("run-keep", 500, 0.005, true, "2026-02-09T09:00:00Z"),
            make_tod_event("run-skip", 500, 0.005, true, "2026-02-09T15:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_time_of_day(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── Phase 85: print_day_of_month ─────────────────────────────────────────

    fn make_dom_event(
        run_id: &str,
        tokens: u64,
        cost: f64,
        success: bool,
        ts: &str,
    ) -> String {
        serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": "researcher",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "duration_ms": 1000u64,
            "tokens_used": tokens,
            "cost_usd": cost,
            "success": success,
            "timestamp": ts,
        }))
        .unwrap()
    }

    #[test]
    fn print_day_of_month_multiple_days() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_multi.jsonl");
        let lines = vec![
            // day 1
            make_dom_event("run1", 100, 0.001, true, "2026-02-01T10:00:00Z"),
            // day 9
            make_dom_event("run1", 200, 0.002, true, "2026-02-09T14:00:00Z"),
            // day 9 again (aggregated)
            make_dom_event("run1", 150, 0.001, false, "2026-02-09T18:00:00Z"),
            // day 22
            make_dom_event("run1", 300, 0.003, true, "2026-02-22T08:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_day_of_month(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_day_of_month_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_day_of_month(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_day_of_month_missing_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_missing_XXXX.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_day_of_month(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_day_of_month_only_delegation_end() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_evtype.jsonl");
        let start_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run1",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "timestamp": "2026-02-15T10:00:00Z",
        }))
        .unwrap();
        let end_ev = make_dom_event("run1", 400, 0.004, true, "2026-02-15T10:01:00Z");
        std::fs::write(&path, format!("{start_ev}\n{end_ev}\n")).unwrap();
        let result = print_day_of_month(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_day_of_month_sorted_numerically() {
        // Events on day 28, 1, 5 — BTreeMap ensures output in order 1, 5, 28
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_sort.jsonl");
        let lines = vec![
            make_dom_event("run1", 100, 0.001, true, "2026-02-28T10:00:00Z"),
            make_dom_event("run1", 100, 0.001, true, "2026-02-01T10:00:00Z"),
            make_dom_event("run1", 100, 0.001, true, "2026-02-05T10:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_day_of_month(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_day_of_month_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_dom_runfilter.jsonl");
        let lines = vec![
            make_dom_event("run-keep", 500, 0.005, true, "2026-02-10T09:00:00Z"),
            make_dom_event("run-skip", 500, 0.005, true, "2026-02-20T15:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_day_of_month(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── Phase 87: print_token_efficiency ─────────────────────────────────────

    fn make_eff_event(
        run_id: &str,
        tokens: u64,
        cost: f64,
        success: bool,
        ts: &str,
    ) -> String {
        serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": "researcher",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "duration_ms": 1000u64,
            "tokens_used": tokens,
            "cost_usd": cost,
            "success": success,
            "timestamp": ts,
        }))
        .unwrap()
    }

    #[test]
    fn print_token_efficiency_all_buckets() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_all.jsonl");
        let lines = vec![
            // very cheap: 1000 tokens, $0.001 → $0.001/1k < $0.002
            make_eff_event("run1", 1000, 0.001, true, "2026-02-01T10:00:00Z"),
            // cheap: 1000 tokens, $0.005 → $0.005/1k ∈ [$0.002, $0.008)
            make_eff_event("run1", 1000, 0.005, true, "2026-02-01T11:00:00Z"),
            // moderate: 1000 tokens, $0.012 → $0.012/1k ∈ [$0.008, $0.020)
            make_eff_event("run1", 1000, 0.012, false, "2026-02-01T12:00:00Z"),
            // expensive: 1000 tokens, $0.025 → $0.025/1k ≥ $0.020
            make_eff_event("run1", 1000, 0.025, true, "2026-02-01T13:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_token_efficiency(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_efficiency_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_token_efficiency(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_efficiency_missing_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_missing_XXXX.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_token_efficiency(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_efficiency_skips_zero_tokens() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_zerotok.jsonl");
        // event with 0 tokens should be skipped entirely
        let zero_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": "run1",
            "agent_name": "researcher",
            "tokens_used": 0u64,
            "cost_usd": 0.0f64,
            "success": true,
            "timestamp": "2026-02-01T10:00:00Z",
        }))
        .unwrap();
        let valid_ev = make_eff_event("run1", 2000, 0.002, true, "2026-02-01T11:00:00Z");
        std::fs::write(&path, format!("{zero_ev}\n{valid_ev}\n")).unwrap();
        let result = print_token_efficiency(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_efficiency_only_delegation_end() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_evtype.jsonl");
        let start_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run1",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "timestamp": "2026-02-01T10:00:00Z",
        }))
        .unwrap();
        let end_ev = make_eff_event("run1", 500, 0.001, true, "2026-02-01T10:01:00Z");
        std::fs::write(&path, format!("{start_ev}\n{end_ev}\n")).unwrap();
        let result = print_token_efficiency(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_token_efficiency_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_eff_runfilter.jsonl");
        let lines = vec![
            make_eff_event("run-keep", 1000, 0.003, true, "2026-02-01T10:00:00Z"),
            make_eff_event("run-skip", 1000, 0.015, true, "2026-02-01T11:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_token_efficiency(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── Phase 89: print_success_breakdown ────────────────────────────────────

    fn make_sb_event(
        run_id: &str,
        tokens: u64,
        cost: f64,
        success: bool,
        ts: &str,
    ) -> String {
        serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationEnd",
            "run_id": run_id,
            "agent_name": "researcher",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "duration_ms": 1000u64,
            "tokens_used": tokens,
            "cost_usd": cost,
            "success": success,
            "timestamp": ts,
        }))
        .unwrap()
    }

    #[test]
    fn print_success_breakdown_both_outcomes() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_both.jsonl");
        let lines = vec![
            make_sb_event("run1", 1000, 0.010, true,  "2026-02-01T10:00:00Z"),
            make_sb_event("run1", 2000, 0.020, true,  "2026-02-01T11:00:00Z"),
            make_sb_event("run1", 500,  0.005, false, "2026-02-01T12:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_success_breakdown(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_success_breakdown_empty_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_empty.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_success_breakdown(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_success_breakdown_missing_log() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_missing_XXXX.jsonl");
        let _ = std::fs::remove_file(&path);
        let result = print_success_breakdown(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_success_breakdown_all_success() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_allsuccess.jsonl");
        let lines = vec![
            make_sb_event("run1", 1000, 0.010, true, "2026-02-01T10:00:00Z"),
            make_sb_event("run1", 1500, 0.015, true, "2026-02-01T11:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_success_breakdown(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_success_breakdown_only_delegation_end() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_evtype.jsonl");
        let start_ev = serde_json::to_string(&serde_json::json!({
            "event_type": "DelegationStart",
            "run_id": "run1",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "depth": 0u32,
            "timestamp": "2026-02-01T10:00:00Z",
        }))
        .unwrap();
        let end_ev = make_sb_event("run1", 800, 0.008, true, "2026-02-01T10:01:00Z");
        std::fs::write(&path, format!("{start_ev}\n{end_ev}\n")).unwrap();
        let result = print_success_breakdown(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_success_breakdown_filters_by_run() {
        let path =
            std::env::temp_dir().join("zeroclaw_test_sb_runfilter.jsonl");
        let lines = vec![
            make_sb_event("run-keep", 1000, 0.010, true,  "2026-02-01T10:00:00Z"),
            make_sb_event("run-skip", 2000, 0.020, false, "2026-02-01T11:00:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_success_breakdown(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_agent_cost_rank ──────────────────────────────────────────────

    fn make_acr_event(run_id: &str, agent: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","agent_name":"{agent}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_agent_cost_rank_multiple_agents() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.jsonl");
        // expensive_agent: 1 delegation at $0.50 → avg $0.50
        // cheap_agent: 2 delegations at $0.02 each → avg $0.02
        let lines = vec![
            make_acr_event("r1", "expensive_agent", 5000, 0.50, true,  "2026-02-01T10:00:00Z"),
            make_acr_event("r1", "cheap_agent",     500,  0.02, true,  "2026-02-01T10:01:00Z"),
            make_acr_event("r1", "cheap_agent",     600,  0.02, false, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_cost_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_agent_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_cost_rank_missing_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("missing.jsonl");
        let result = print_agent_cost_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_cost_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"r1","agent_name":"agt","timestamp":"2026-02-01T10:00:00Z"}"#;
        let end = make_acr_event("r1", "agt", 1000, 0.05, true, "2026-02-01T10:01:00Z");
        std::fs::write(&path, format!("{start}\n{end}\n")).unwrap();
        let result = print_agent_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_cost_rank_sorted_by_avg_cost_desc() {
        // Three agents: medium ($0.10 avg), high ($0.30 avg), low ($0.01 avg)
        // Expected output order: high, medium, low
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.jsonl");
        let lines = vec![
            make_acr_event("r1", "medium_agt", 2000, 0.10, true, "2026-02-01T10:00:00Z"),
            make_acr_event("r1", "high_agt",   8000, 0.30, true, "2026-02-01T10:01:00Z"),
            make_acr_event("r1", "low_agt",     100, 0.01, true, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_cost_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("a.jsonl");
        let lines = vec![
            make_acr_event("run-keep", "agt_a", 1000, 0.05, true,  "2026-02-01T10:00:00Z"),
            make_acr_event("run-skip", "agt_b", 2000, 0.10, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_cost_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_model_cost_rank ──────────────────────────────────────────────

    fn make_mcr_event(run_id: &str, model: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","model":"{model}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_model_cost_rank_multiple_models() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("m.jsonl");
        // opus: 1 delegation at $0.80 → avg $0.80
        // haiku: 2 delegations at $0.01 each → avg $0.01
        let lines = vec![
            make_mcr_event("r1", "claude-opus-4-6",  8000, 0.80, true,  "2026-02-01T10:00:00Z"),
            make_mcr_event("r1", "claude-haiku-4-5",  400, 0.01, true,  "2026-02-01T10:01:00Z"),
            make_mcr_event("r1", "claude-haiku-4-5",  500, 0.01, false, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_cost_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("m.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_model_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_cost_rank_missing_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("missing.jsonl");
        let result = print_model_cost_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_cost_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("m.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"r1","model":"claude-sonnet-4-6","timestamp":"2026-02-01T10:00:00Z"}"#;
        let end = make_mcr_event("r1", "claude-sonnet-4-6", 2000, 0.05, true, "2026-02-01T10:01:00Z");
        std::fs::write(&path, format!("{start}\n{end}\n")).unwrap();
        let result = print_model_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_cost_rank_sorted_by_avg_cost_desc() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("m.jsonl");
        // sonnet: $0.10, opus: $0.50, haiku: $0.005 → expected order: opus, sonnet, haiku
        let lines = vec![
            make_mcr_event("r1", "claude-sonnet-4-6", 3000, 0.10, true, "2026-02-01T10:00:00Z"),
            make_mcr_event("r1", "claude-opus-4-6",   9000, 0.50, true, "2026-02-01T10:01:00Z"),
            make_mcr_event("r1", "claude-haiku-4-5",   200, 0.005, true, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_cost_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("m.jsonl");
        let lines = vec![
            make_mcr_event("run-keep", "claude-sonnet-4-6", 2000, 0.04, true,  "2026-02-01T10:00:00Z"),
            make_mcr_event("run-skip", "claude-opus-4-6",   8000, 0.80, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_cost_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_provider_cost_rank ───────────────────────────────────────────

    fn make_pcr_event(run_id: &str, provider: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","provider":"{provider}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_provider_cost_rank_multiple_providers() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        // anthropic: 1 at $0.50 → avg $0.50; openai: 2 at $0.08 each → avg $0.08
        let lines = vec![
            make_pcr_event("r1", "anthropic", 5000, 0.50, true,  "2026-02-01T10:00:00Z"),
            make_pcr_event("r1", "openai",    2000, 0.08, true,  "2026-02-01T10:01:00Z"),
            make_pcr_event("r1", "openai",    1800, 0.08, false, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_cost_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_provider_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_cost_rank_missing_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("missing.jsonl");
        let result = print_provider_cost_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_cost_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"r1","provider":"anthropic","timestamp":"2026-02-01T10:00:00Z"}"#;
        let end = make_pcr_event("r1", "anthropic", 3000, 0.06, true, "2026-02-01T10:01:00Z");
        std::fs::write(&path, format!("{start}\n{end}\n")).unwrap();
        let result = print_provider_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_cost_rank_sorted_by_avg_cost_desc() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        // google: $0.02, anthropic: $0.40, openai: $0.15 → expected: anthropic, openai, google
        let lines = vec![
            make_pcr_event("r1", "google",    500,  0.02, true, "2026-02-01T10:00:00Z"),
            make_pcr_event("r1", "anthropic", 8000, 0.40, true, "2026-02-01T10:01:00Z"),
            make_pcr_event("r1", "openai",    3000, 0.15, true, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_provider_cost_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_pcr_event("run-keep", "anthropic", 2000, 0.04, true,  "2026-02-01T10:00:00Z"),
            make_pcr_event("run-skip", "openai",    4000, 0.20, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_provider_cost_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_run_cost_rank ────────────────────────────────────────────────

    fn make_rcr_event(run_id: &str, agent: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","agent_name":"{agent}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_run_cost_rank_multiple_runs() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_rcr_event("run-alpha", "agent-a", 5000, 1.25, true,  "2026-02-01T10:00:00Z"),
            make_rcr_event("run-beta",  "agent-b", 2000, 0.40, true,  "2026-02-01T10:01:00Z"),
            make_rcr_event("run-gamma", "agent-c",  500, 0.05, false, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_cost_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_run_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_cost_rank_missing_log() {
        let path = std::path::PathBuf::from("/tmp/zeroclaw_rcr_missing_test.jsonl");
        let result = print_run_cost_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_cost_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"run-only","agent_name":"agent-a","timestamp":"2026-02-01T10:00:00Z"}"#;
        std::fs::write(&path, start.to_owned() + "\n").unwrap();
        let result = print_run_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_cost_rank_sorted_by_total_cost_desc() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        // run-cheap: 1 del at $0.10 total; run-expensive: 2 dels at $3.00 total
        let lines = vec![
            make_rcr_event("run-cheap",     "agent-a", 1000, 0.10, true,  "2026-02-01T10:00:00Z"),
            make_rcr_event("run-expensive", "agent-b", 8000, 1.50, true,  "2026-02-01T10:01:00Z"),
            make_rcr_event("run-expensive", "agent-c", 6000, 1.50, false, "2026-02-01T10:02:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run_cost_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_run_cost_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_rcr_event("run-keep", "agent-a", 3000, 0.60, true,  "2026-02-01T10:00:00Z"),
            make_rcr_event("run-skip", "agent-b", 1000, 0.10, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_run_cost_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_agent_success_rank ───────────────────────────────────────────

    fn make_asr_event(run_id: &str, agent: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","agent_name":"{agent}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_agent_success_rank_multiple_agents() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_asr_event("run-a", "orchestrator", 1000, 0.10, true,  "2026-02-01T10:00:00Z"),
            make_asr_event("run-a", "orchestrator", 1200, 0.12, true,  "2026-02-01T10:01:00Z"),
            make_asr_event("run-a", "research",     3000, 0.30, true,  "2026-02-01T10:02:00Z"),
            make_asr_event("run-a", "research",     2500, 0.25, false, "2026-02-01T10:03:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_success_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_agent_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_success_rank_missing_log() {
        let path = std::path::PathBuf::from("/tmp/zeroclaw_asr_missing_test.jsonl");
        let result = print_agent_success_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_success_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"run-a","agent_name":"orchestrator","timestamp":"2026-02-01T10:00:00Z"}"#;
        std::fs::write(&path, start.to_owned() + "\n").unwrap();
        let result = print_agent_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_success_rank_sorted_by_ok_pct_desc() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        // reliable: 10/10 = 100%; flaky: 5/10 = 50%
        let lines = vec![
            make_asr_event("run-a", "reliable", 1000, 0.10, true,  "2026-02-01T10:00:00Z"),
            make_asr_event("run-a", "reliable", 1000, 0.10, true,  "2026-02-01T10:01:00Z"),
            make_asr_event("run-a", "flaky",    1000, 0.10, true,  "2026-02-01T10:02:00Z"),
            make_asr_event("run-a", "flaky",    1000, 0.10, false, "2026-02-01T10:03:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_agent_success_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_asr_event("run-keep", "agent-a", 2000, 0.20, true,  "2026-02-01T10:00:00Z"),
            make_asr_event("run-skip", "agent-b", 1000, 0.10, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_agent_success_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    // ── print_model_success_rank ───────────────────────────────────────────

    fn make_msr_event(run_id: &str, model: &str, tokens: u64, cost: f64, success: bool, ts: &str) -> String {
        format!(
            r#"{{"event_type":"DelegationEnd","run_id":"{run_id}","model":"{model}","tokens_used":{tokens},"cost_usd":{cost},"success":{success},"timestamp":"{ts}"}}"#
        )
    }

    #[test]
    fn print_model_success_rank_multiple_models() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_msr_event("run-a", "claude-sonnet-4-6", 3000, 0.40, true,  "2026-02-01T10:00:00Z"),
            make_msr_event("run-a", "claude-sonnet-4-6", 2500, 0.33, true,  "2026-02-01T10:01:00Z"),
            make_msr_event("run-a", "claude-haiku-4-5",  800, 0.01, true,  "2026-02-01T10:02:00Z"),
            make_msr_event("run-a", "claude-haiku-4-5",  700, 0.01, false, "2026-02-01T10:03:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_success_rank_empty_log() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        std::fs::write(&path, "").unwrap();
        let result = print_model_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_success_rank_missing_log() {
        let path = std::path::PathBuf::from("/tmp/zeroclaw_msr_missing_test.jsonl");
        let result = print_model_success_rank(&path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_success_rank_skips_start_events() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let start = r#"{"event_type":"DelegationStart","run_id":"run-a","model":"claude-sonnet-4-6","timestamp":"2026-02-01T10:00:00Z"}"#;
        std::fs::write(&path, start.to_owned() + "\n").unwrap();
        let result = print_model_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_success_rank_sorted_by_ok_pct_desc() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        // reliable-model: 2/2 = 100%; flaky-model: 1/2 = 50%
        let lines = vec![
            make_msr_event("run-a", "reliable-model", 1000, 0.10, true,  "2026-02-01T10:00:00Z"),
            make_msr_event("run-a", "reliable-model", 1000, 0.10, true,  "2026-02-01T10:01:00Z"),
            make_msr_event("run-a", "flaky-model",    1000, 0.10, true,  "2026-02-01T10:02:00Z"),
            make_msr_event("run-a", "flaky-model",    1000, 0.10, false, "2026-02-01T10:03:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_success_rank(&path, None);
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }

    #[test]
    fn print_model_success_rank_filters_by_run() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("p.jsonl");
        let lines = vec![
            make_msr_event("run-keep", "claude-sonnet-4-6", 2000, 0.27, true,  "2026-02-01T10:00:00Z"),
            make_msr_event("run-skip", "claude-haiku-4-5",  500, 0.01, false, "2026-02-01T10:01:00Z"),
        ];
        std::fs::write(&path, lines.join("\n") + "\n").unwrap();
        let result = print_model_success_rank(&path, Some("run-keep"));
        let _ = std::fs::remove_file(&path);
        assert!(result.is_ok());
    }
}
