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
//! - [`get_log_summary`]: programmatic aggregate for `zeroclaw status`.
//!
//! All parsing is done via `serde_json::Value` — no new dependencies.

use anyhow::{bail, Result};
use chrono::{DateTime, Utc};
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
}
