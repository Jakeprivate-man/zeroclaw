#![warn(clippy::all, clippy::pedantic)]
#![allow(
    clippy::assigning_clones,
    clippy::bool_to_int_with_if,
    clippy::case_sensitive_file_extension_comparisons,
    clippy::cast_possible_wrap,
    clippy::doc_markdown,
    clippy::field_reassign_with_default,
    clippy::float_cmp,
    clippy::implicit_clone,
    clippy::items_after_statements,
    clippy::map_unwrap_or,
    clippy::manual_let_else,
    clippy::missing_errors_doc,
    clippy::missing_panics_doc,
    clippy::module_name_repetitions,
    clippy::needless_pass_by_value,
    clippy::needless_raw_string_hashes,
    clippy::redundant_closure_for_method_calls,
    clippy::similar_names,
    clippy::single_match_else,
    clippy::struct_field_names,
    clippy::too_many_lines,
    clippy::uninlined_format_args,
    clippy::unused_self,
    clippy::cast_precision_loss,
    clippy::unnecessary_cast,
    clippy::unnecessary_lazy_evaluations,
    clippy::unnecessary_literal_bound,
    clippy::unnecessary_map_or,
    clippy::unnecessary_wraps,
    dead_code
)]

use anyhow::{bail, Result};
use clap::{CommandFactory, Parser, Subcommand, ValueEnum};
use dialoguer::{Input, Password};
use serde::{Deserialize, Serialize};
use std::io::Write;
use tracing::{info, warn};
use tracing_subscriber::{fmt, EnvFilter};

fn parse_temperature(s: &str) -> std::result::Result<f64, String> {
    let t: f64 = s.parse().map_err(|e| format!("{e}"))?;
    if !(0.0..=2.0).contains(&t) {
        return Err("temperature must be between 0.0 and 2.0".to_string());
    }
    Ok(t)
}

mod agent;
mod approval;
mod auth;
mod channels;
mod rag {
    pub use zeroclaw::rag::*;
}
mod config;
mod cron;
mod daemon;
mod doctor;
mod gateway;
mod hardware;
mod health;
mod heartbeat;
mod identity;
mod integrations;
mod memory;
mod migration;
mod multimodal;
mod observability;
mod onboard;
mod peripherals;
mod providers;
mod runtime;
mod security;
mod service;
mod skillforge;
mod skills;
mod tools;
mod tunnel;
mod util;

use config::Config;

// Re-export so binary's hardware/peripherals modules can use crate::HardwareCommands etc.
pub use zeroclaw::{HardwareCommands, PeripheralCommands};

/// `ZeroClaw` - Zero overhead. Zero compromise. 100% Rust.
#[derive(Parser, Debug)]
#[command(name = "zeroclaw")]
#[command(author = "theonlyhennygod")]
#[command(version = "0.1.0")]
#[command(about = "The fastest, smallest AI assistant.", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum ServiceCommands {
    /// Install daemon service unit for auto-start and restart
    Install,
    /// Start daemon service
    Start,
    /// Stop daemon service
    Stop,
    /// Restart daemon service to apply latest config
    Restart,
    /// Check daemon service status
    Status,
    /// Uninstall daemon service unit
    Uninstall,
}

#[derive(Copy, Clone, Debug, Eq, PartialEq, ValueEnum)]
enum CompletionShell {
    #[value(name = "bash")]
    Bash,
    #[value(name = "fish")]
    Fish,
    #[value(name = "zsh")]
    Zsh,
    #[value(name = "powershell")]
    PowerShell,
    #[value(name = "elvish")]
    Elvish,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Initialize your workspace and configuration
    Onboard {
        /// Run the full interactive wizard (default is quick setup)
        #[arg(long)]
        interactive: bool,

        /// Reconfigure channels only (fast repair flow)
        #[arg(long)]
        channels_only: bool,

        /// API key (used in quick mode, ignored with --interactive)
        #[arg(long)]
        api_key: Option<String>,

        /// Provider name (used in quick mode, default: openrouter)
        #[arg(long)]
        provider: Option<String>,
        /// Model ID override (used in quick mode)
        #[arg(long)]
        model: Option<String>,
        /// Memory backend (sqlite, lucid, markdown, none) - used in quick mode, default: sqlite
        #[arg(long)]
        memory: Option<String>,
    },

    /// Start the AI agent loop
    #[command(long_about = "\
Start the AI agent loop.

Launches an interactive chat session with the configured AI provider. \
Use --message for single-shot queries without entering interactive mode.

Examples:
  zeroclaw agent                              # interactive session
  zeroclaw agent -m \"Summarize today's logs\"  # single message
  zeroclaw agent -p anthropic --model claude-sonnet-4-20250514
  zeroclaw agent --peripheral nucleo-f401re:/dev/ttyACM0")]
    Agent {
        /// Single message mode (don't enter interactive mode)
        #[arg(short, long)]
        message: Option<String>,

        /// Provider to use (openrouter, anthropic, openai, openai-codex)
        #[arg(short, long)]
        provider: Option<String>,

        /// Model to use
        #[arg(long)]
        model: Option<String>,

        /// Temperature (0.0 - 2.0)
        #[arg(short, long, default_value = "0.7", value_parser = parse_temperature)]
        temperature: f64,

        /// Attach a peripheral (board:path, e.g. nucleo-f401re:/dev/ttyACM0)
        #[arg(long)]
        peripheral: Vec<String>,
    },

    /// Start the gateway server (webhooks, websockets)
    #[command(long_about = "\
Start the gateway server (webhooks, websockets).

Runs the HTTP/WebSocket gateway that accepts incoming webhook events \
and WebSocket connections. Bind address defaults to the values in \
your config file (gateway.host / gateway.port).

Examples:
  zeroclaw gateway                  # use config defaults
  zeroclaw gateway -p 8080          # listen on port 8080
  zeroclaw gateway --host 0.0.0.0   # bind to all interfaces
  zeroclaw gateway -p 0             # random available port")]
    Gateway {
        /// Port to listen on (use 0 for random available port); defaults to config gateway.port
        #[arg(short, long)]
        port: Option<u16>,

        /// Host to bind to; defaults to config gateway.host
        #[arg(long)]
        host: Option<String>,
    },

    /// Start long-running autonomous runtime (gateway + channels + heartbeat + scheduler)
    #[command(long_about = "\
Start the long-running autonomous daemon.

Launches the full ZeroClaw runtime: gateway server, all configured \
channels (Telegram, Discord, Slack, etc.), heartbeat monitor, and \
the cron scheduler. This is the recommended way to run ZeroClaw in \
production or as an always-on assistant.

Use 'zeroclaw service install' to register the daemon as an OS \
service (systemd/launchd) for auto-start on boot.

Examples:
  zeroclaw daemon                   # use config defaults
  zeroclaw daemon -p 9090           # gateway on port 9090
  zeroclaw daemon --host 127.0.0.1  # localhost only")]
    Daemon {
        /// Port to listen on (use 0 for random available port); defaults to config gateway.port
        #[arg(short, long)]
        port: Option<u16>,

        /// Host to bind to; defaults to config gateway.host
        #[arg(long)]
        host: Option<String>,
    },

    /// Manage OS service lifecycle (launchd/systemd user service)
    Service {
        #[command(subcommand)]
        service_command: ServiceCommands,
    },

    /// Run diagnostics for daemon/scheduler/channel freshness
    Doctor {
        #[command(subcommand)]
        doctor_command: Option<DoctorCommands>,
    },

    /// Show system status (full details)
    Status,

    /// Configure and manage scheduled tasks
    #[command(long_about = "\
Configure and manage scheduled tasks.

Schedule recurring, one-shot, or interval-based tasks using cron \
expressions, RFC 3339 timestamps, durations, or fixed intervals.

Cron expressions use the standard 5-field format: \
'min hour day month weekday'. Timezones default to UTC; \
override with --tz and an IANA timezone name.

Examples:
  zeroclaw cron list
  zeroclaw cron add '0 9 * * 1-5' 'Good morning' --tz America/New_York
  zeroclaw cron add '*/30 * * * *' 'Check system health'
  zeroclaw cron add-at 2025-01-15T14:00:00Z 'Send reminder'
  zeroclaw cron add-every 60000 'Ping heartbeat'
  zeroclaw cron once 30m 'Run backup in 30 minutes'
  zeroclaw cron pause <task-id>
  zeroclaw cron update <task-id> --expression '0 8 * * *' --tz Europe/London")]
    Cron {
        #[command(subcommand)]
        cron_command: CronCommands,
    },

    /// Manage provider model catalogs
    Models {
        #[command(subcommand)]
        model_command: ModelCommands,
    },

    /// List supported AI providers
    Providers,

    /// Manage channels (telegram, discord, slack)
    #[command(long_about = "\
Manage communication channels.

Add, remove, list, and health-check channels that connect ZeroClaw \
to messaging platforms. Supported channel types: telegram, discord, \
slack, whatsapp, matrix, imessage, email.

Examples:
  zeroclaw channel list
  zeroclaw channel doctor
  zeroclaw channel add telegram '{\"bot_token\":\"...\",\"name\":\"my-bot\"}'
  zeroclaw channel remove my-bot
  zeroclaw channel bind-telegram zeroclaw_user")]
    Channel {
        #[command(subcommand)]
        channel_command: ChannelCommands,
    },

    /// Browse 50+ integrations
    Integrations {
        #[command(subcommand)]
        integration_command: IntegrationCommands,
    },

    /// Manage skills (user-defined capabilities)
    Skills {
        #[command(subcommand)]
        skill_command: SkillCommands,
    },

    /// Migrate data from other agent runtimes
    Migrate {
        #[command(subcommand)]
        migrate_command: MigrateCommands,
    },

    /// Manage provider subscription authentication profiles
    Auth {
        #[command(subcommand)]
        auth_command: AuthCommands,
    },

    /// Discover and introspect USB hardware
    #[command(long_about = "\
Discover and introspect USB hardware.

Enumerate connected USB devices, identify known development boards \
(STM32 Nucleo, Arduino, ESP32), and retrieve chip information via \
probe-rs / ST-Link.

Examples:
  zeroclaw hardware discover
  zeroclaw hardware introspect /dev/ttyACM0
  zeroclaw hardware info --chip STM32F401RETx")]
    Hardware {
        #[command(subcommand)]
        hardware_command: zeroclaw::HardwareCommands,
    },

    /// Manage hardware peripherals (STM32, RPi GPIO, etc.)
    #[command(long_about = "\
Manage hardware peripherals.

Add, list, flash, and configure hardware boards that expose tools \
to the agent (GPIO, sensors, actuators). Supported boards: \
nucleo-f401re, rpi-gpio, esp32, arduino-uno.

Examples:
  zeroclaw peripheral list
  zeroclaw peripheral add nucleo-f401re /dev/ttyACM0
  zeroclaw peripheral add rpi-gpio native
  zeroclaw peripheral flash --port /dev/cu.usbmodem12345
  zeroclaw peripheral flash-nucleo")]
    Peripheral {
        #[command(subcommand)]
        peripheral_command: zeroclaw::PeripheralCommands,
    },

    /// Manage configuration
    #[command(long_about = "\
Manage ZeroClaw configuration.

Inspect and export configuration settings. Use 'schema' to dump \
the full JSON Schema for the config file, which documents every \
available key, type, and default value.

Examples:
  zeroclaw config schema              # print JSON Schema to stdout
  zeroclaw config schema > schema.json")]
    Config {
        #[command(subcommand)]
        config_command: ConfigCommands,
    },

    /// Inspect agent delegation history from the local log
    #[command(long_about = "\
Inspect agent delegation history from the local log.

Reads `~/.zeroclaw/state/delegation.jsonl` and prints summaries,
run lists, and per-run delegation trees without starting the agent.

Examples:
  zeroclaw delegations               # overall summary
  zeroclaw delegations list          # all runs, newest first
  zeroclaw delegations show          # tree for most recent run
  zeroclaw delegations show --run <id>  # tree for a specific run
  zeroclaw delegations stats         # per-agent stats (all runs)
  zeroclaw delegations stats --run <id>  # per-agent stats for one run
  zeroclaw delegations export        # stream all events as JSONL
  zeroclaw delegations export --format csv --run <id>  # CSV for one run
  zeroclaw delegations diff <run_a>  # compare run_a vs most recent other run
  zeroclaw delegations diff <run_a> <run_b>  # compare two specific runs
  zeroclaw delegations top           # global leaderboard by tokens (top 10)
  zeroclaw delegations top --by cost --limit 5  # top 5 by cost
  zeroclaw delegations prune         # keep 20 most recent runs, remove the rest
  zeroclaw delegations prune --keep 5  # keep only 5 most recent runs
  zeroclaw delegations models        # model breakdown: tokens and cost per model
  zeroclaw delegations models --run <id>  # model breakdown for one run
  zeroclaw delegations providers     # provider breakdown: tokens and cost per provider
  zeroclaw delegations providers --run <id>  # provider breakdown for one run
  zeroclaw delegations depth         # depth breakdown: delegations per nesting level
  zeroclaw delegations depth --run <id>  # depth breakdown for one run
  zeroclaw delegations errors        # list all failed delegations with error messages
  zeroclaw delegations errors --run <id>  # failures for one run
  zeroclaw delegations slow          # top 10 slowest delegations across all runs
  zeroclaw delegations slow --limit 5  # top 5 slowest
  zeroclaw delegations slow --run <id>  # slowest within one run
  zeroclaw delegations cost          # per-run cost breakdown, most expensive first
  zeroclaw delegations cost --run <id>  # cost breakdown for one run
  zeroclaw delegations recent        # 10 most recently completed delegations
  zeroclaw delegations recent --limit 5  # 5 most recent
  zeroclaw delegations recent --run <id>  # most recent within one run
  zeroclaw delegations active             # all currently in-flight delegations
  zeroclaw delegations active --run <id>  # in-flight within one run
  zeroclaw delegations agent research              # history for agent research
  zeroclaw delegations agent research --run <id>  # history within one run
  zeroclaw delegations model claude-sonnet-4              # history for model
  zeroclaw delegations model claude-sonnet-4 --run <id>   # history within one run
  zeroclaw delegations provider anthropic             # history for provider
  zeroclaw delegations provider anthropic --run <id>  # history within one run
  zeroclaw delegations run <id>                        # full chronological report for one run
  zeroclaw delegations depth-view 0                   # all root-level delegations, newest first
  zeroclaw delegations depth-view 1 --run <id>        # depth-1 delegations for one run
  zeroclaw delegations daily                           # per-day breakdown across all runs
  zeroclaw delegations daily --run <id>               # per-day breakdown for one run")]
    Delegations {
        #[command(subcommand)]
        delegation_command: Option<DelegationCommands>,
    },

    /// Generate shell completion script to stdout
    #[command(long_about = "\
Generate shell completion scripts for `zeroclaw`.

The script is printed to stdout so it can be sourced directly:

Examples:
  source <(zeroclaw completions bash)
  zeroclaw completions zsh > ~/.zfunc/_zeroclaw
  zeroclaw completions fish > ~/.config/fish/completions/zeroclaw.fish")]
    Completions {
        /// Target shell
        #[arg(value_enum)]
        shell: CompletionShell,
    },
}

#[derive(Subcommand, Debug)]
enum DelegationCommands {
    /// List all stored runs, newest first
    List,
    /// Show delegation tree for a run (default: most recent)
    Show {
        /// Run ID to display (default: most recent run)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show per-agent statistics: count, success rate, avg duration, tokens, cost
    Stats {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Export delegation events as JSONL (default) or CSV to stdout
    Export {
        /// Filter to a specific run ID (default: all runs)
        #[arg(long)]
        run: Option<String>,
        /// Output format: jsonl (one event per line) or csv (DelegationEnd rows only)
        #[arg(long, value_enum, default_value = "jsonl")]
        format: DelegationExportFormat,
    },
    /// Show global agent leaderboard ranked by tokens or cost (all runs)
    #[command(long_about = "\
Aggregate all stored delegation events across every run and rank agents
by cumulative token usage or cost.

Output columns: # | agent | runs | delegations | tokens | cost

Examples:
  zeroclaw delegations top                    # top 10 by tokens
  zeroclaw delegations top --by cost          # top 10 by cost
  zeroclaw delegations top --limit 5          # top 5 by tokens
  zeroclaw delegations top --by cost --limit 3  # top 3 by cost")]
    Top {
        /// Rank agents by tokens (default) or cost
        #[arg(long, value_enum, default_value = "tokens")]
        by: DelegationTopBy,
        /// Maximum number of agents to show
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
    /// Remove old runs from the log, keeping the N most recent
    #[command(long_about = "\
Remove old runs from the delegation log, keeping the N most recent.

Reads all stored runs, sorts them newest-first, and rewrites the log
retaining only the `--keep` most recent. The write is atomic (temp file
then rename), so a crash mid-write leaves the original intact.

Use this to cap log growth between ZeroClaw's automatic rotation cycles.

Examples:
  zeroclaw delegations prune              # keep 20 most recent runs
  zeroclaw delegations prune --keep 5    # keep only 5 most recent runs
  zeroclaw delegations prune --keep 0    # remove all stored runs")]
    Prune {
        /// Number of most-recent runs to keep (older runs are removed)
        #[arg(long, default_value_t = 20)]
        keep: usize,
    },
    /// Show per-model token and cost breakdown (all runs or one run)
    #[command(long_about = "\
Aggregate delegation events by model and print a breakdown table.

Rows are sorted by cumulative tokens descending.  Use `--run` to scope
to a single process invocation; omit it to aggregate across all runs.

Output columns: # | model | runs | delegations | tokens | cost

Examples:
  zeroclaw delegations models              # all runs, sorted by tokens
  zeroclaw delegations models --run <id>  # scope to one run")]
    Models {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show per-provider token and cost breakdown (all runs or one run)
    #[command(long_about = "\
Aggregate delegation events by provider and print a breakdown table.

Rows are sorted by cumulative tokens descending.  Use `--run` to scope
to a single process invocation; omit it to aggregate across all runs.

Output columns: # | provider | runs | delegations | tokens | cost

Examples:
  zeroclaw delegations providers              # all runs, sorted by tokens
  zeroclaw delegations providers --run <id>  # scope to one run")]
    Providers {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show per-depth-level delegation breakdown (all runs or one run)
    #[command(long_about = "\
Aggregate delegation events by depth level and print a breakdown table.

Depth 0 is the root (top-level) agent; each additional level represents
a nested sub-agent delegation. Rows are sorted by depth ascending.

Output columns: depth | delegations | ended | success% | tokens | cost

Examples:
  zeroclaw delegations depth              # all runs, depth 0 first
  zeroclaw delegations depth --run <id>  # scope to one run")]
    Depth {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// List failed delegations with agent, depth, duration, and error message
    #[command(long_about = "\
List all failed delegations from the log, ordered by timestamp (oldest first).

Only `DelegationEnd` events where `success` is false are shown. Error messages
are truncated to 80 characters. Use `--run` to focus on a single invocation.

Output columns: # | run (prefix) | agent | depth | duration | error

Examples:
  zeroclaw delegations errors              # all runs, oldest failure first
  zeroclaw delegations errors --run <id>  # failures for one run")]
    Errors {
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// List the N slowest delegations ranked by duration descending
    #[command(long_about = "\
List the N slowest completed delegations from the log, ranked by duration (longest first).

Only `DelegationEnd` events that carry a `duration_ms` value are included. Use `--run` to
scope to a single invocation. `--limit` controls how many rows to display (default: 10).

Output columns: # | run (prefix) | agent | depth | duration | tokens | cost

Examples:
  zeroclaw delegations slow                        # top 10 slowest across all runs
  zeroclaw delegations slow --limit 5              # top 5 slowest
  zeroclaw delegations slow --run <id>             # slowest within one run
  zeroclaw delegations slow --run <id> --limit 3   # top 3 slowest in one run")]
    Slow {
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
        /// Number of rows to display (default: 10)
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
    /// Show per-run cost breakdown sorted by total cost descending
    #[command(long_about = "\
Show a per-run cost breakdown table, sorted by total cost descending (most expensive first).

One row per stored run. Use `--run` to show only a single run. For each run the table
shows the 8-character run prefix, start timestamp, total delegations, tokens, cost, and
the average cost per completed delegation.

Output columns: # | run (prefix) | start (UTC) | delegations | tokens | cost | avg/del

Examples:
  zeroclaw delegations cost              # all runs, most expensive first
  zeroclaw delegations cost --run <id>   # cost breakdown for one run")]
    Cost {
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// List the N most recently completed delegations, newest first
    #[command(long_about = "\
List the N most recently completed delegations from the log, sorted by finish
timestamp descending (newest first). Only `DelegationEnd` events are shown.
Use `--run` to scope to a single invocation. `--limit` controls how many rows
to display (default: 10).

Output columns: # | run (prefix) | agent | depth | duration | tokens | cost | finished (UTC)

Examples:
  zeroclaw delegations recent                        # 10 most recent across all runs
  zeroclaw delegations recent --limit 5              # 5 most recent
  zeroclaw delegations recent --run <id>             # most recent within one run
  zeroclaw delegations recent --run <id> --limit 3   # top 3 most recent in one run")]
    Recent {
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
        /// Number of rows to display (default: 10)
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
    /// List currently in-flight delegations (started but not yet finished)
    #[command(long_about = "\
List delegations that are currently in-flight: `DelegationStart` events that have
no matching `DelegationEnd` in the log. Starts are matched to ends FIFO per
(run_id, agent_name, depth) key, so concurrent delegations of the same agent are
handled correctly.

Use `--run` to scope to a single invocation. Results are sorted oldest-start first
so the longest-running delegation appears at the top.

Output columns: # | run (prefix) | agent | depth | started (UTC) | elapsed

Examples:
  zeroclaw delegations active              # all in-flight across all runs
  zeroclaw delegations active --run <id>   # in-flight within one run")]
    Active {
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show all completed delegations for a named agent, newest first
    #[command(long_about = "\
Show every completed delegation for a specific agent name, sorted by finish
timestamp descending (most recent first).  Only `DelegationEnd` events whose
`agent_name` field exactly matches <agent> are shown.  Use `--run` to scope
to a single invocation.

Output columns: # | run | depth | duration | tokens | cost | ok | finished (UTC)

The footer shows total occurrences, success count, cumulative tokens, and
cumulative cost for the queried agent.

Examples:
  zeroclaw delegations agent research             # all runs, newest first
  zeroclaw delegations agent research --run <id>  # one run only")]
    Agent {
        /// Agent name to filter (exact match, case-sensitive)
        name: String,
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show all completed delegations for a named model, newest first
    #[command(long_about = "\
Show every completed delegation for a specific model name, sorted by finish
timestamp descending (most recent first).  Only `DelegationEnd` events whose
`model` field exactly matches <model> are shown.  Use `--run` to scope to a
single invocation.

Output columns: # | run | agent | depth | duration | tokens | cost | ok | finished (UTC)

The footer shows total occurrences, success count, cumulative tokens, and
cumulative cost for the queried model.

Examples:
  zeroclaw delegations model claude-sonnet-4              # all runs, newest first
  zeroclaw delegations model claude-sonnet-4 --run <id>   # one run only")]
    Model {
        /// Model name to filter (exact match, case-sensitive)
        name: String,
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show all completed delegations for a named provider, newest first
    #[command(long_about = "\
Show every completed delegation for a specific provider name, sorted by finish
timestamp descending (most recent first).  Only `DelegationEnd` events whose
`provider` field exactly matches <provider> are shown.  Use `--run` to scope
to a single invocation.

Output columns: # | run | agent | model | depth | duration | tokens | cost | ok | finished (UTC)

The footer shows total occurrences, success count, cumulative tokens, and
cumulative cost for the queried provider.

Examples:
  zeroclaw delegations provider anthropic             # all runs, newest first
  zeroclaw delegations provider anthropic --run <id>  # one run only")]
    Provider {
        /// Provider name to filter (exact match, case-sensitive)
        name: String,
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show all completed delegations for a specific run in chronological order
    #[command(long_about = "\
Show all completed delegations for a specific run in chronological order.

Filters `DelegationEnd` events whose `run_id` matches <id> (exact match).
Results are sorted oldest-first so you can trace the sequence of delegations
in the order they completed.  Unlike `recent --run`, there is no row limit.

Output columns: # | agent | depth | duration | tokens | cost | ok | finished (UTC)

The footer shows total completions, success count, cumulative tokens, and
cumulative cost for the run.

Examples:
  zeroclaw delegations run f47ac10b-1234-5678-abcd-ef0123456789  # full run ID
  zeroclaw delegations run f47ac10b                               # unique prefix")]
    Run {
        /// Run ID to report on (exact match)
        id: String,
    },
    /// Show all completed delegations at a specific nesting depth, newest first
    #[command(long_about = "\
Show every completed delegation at a specific nesting depth, sorted by finish
timestamp descending (most recent first).  Only `DelegationEnd` events whose
`depth` field equals <level> are shown.  Use `--run` to scope to a single
invocation.

Depth 0 = root-level delegations (orchestrated directly by the main agent).
Depth 1 = sub-delegations spawned by depth-0 agents, and so on.

Output columns: # | run | agent | duration | tokens | cost | ok | finished (UTC)

The footer shows total occurrences, success count, cumulative tokens, and
cumulative cost for the queried depth level.

Examples:
  zeroclaw delegations depth-view 0             # all root-level delegations
  zeroclaw delegations depth-view 1             # all depth-1 sub-delegations
  zeroclaw delegations depth-view 0 --run <id>  # root delegations for one run")]
    DepthView {
        /// Nesting depth level to filter (0 = root, 1 = sub-delegations, …)
        level: u32,
        /// Scope to a specific run ID (default: show all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Per-calendar-day delegation breakdown, oldest day first
    #[command(long_about = "\
Aggregate all completed delegations by UTC calendar date (YYYY-MM-DD),
sorted oldest-first so the table reads chronologically.  Use `--run` to
scope to a single run.

Output columns: date | count | ok% | tokens | cost

The footer shows total days, total delegation count, success count, and
cumulative cost.

Examples:
  zeroclaw delegations daily              # all runs, per-day breakdown
  zeroclaw delegations daily --run <id>   # one run only")]
    Daily {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Per-UTC-hour delegation breakdown, lowest hour first
    #[command(long_about = "\
Aggregate all completed delegations by UTC hour-of-day (00–23),
sorted lowest-hour first so the table reveals peak activity windows.
Use `--run` to scope to a single run.

The hour key is extracted from the ISO-8601 timestamp (e.g. the event at
2026-01-15T14:30:00Z contributes to hour \"14:xx\").

Output columns: hour (UTC) | count | ok% | tokens | cost

The footer shows active hours, total delegation count, success count, and
cumulative cost.

Examples:
  zeroclaw delegations hourly              # all runs, per-hour breakdown
  zeroclaw delegations hourly --run <id>   # one run only")]
    Hourly {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Per-calendar-month delegation breakdown, oldest month first
    #[command(long_about = "\
Aggregate all completed delegations by UTC calendar month (YYYY-MM),
sorted oldest-first so the table reads chronologically.  Use `--run` to
scope to a single run.

The month key is extracted from the first 7 characters of the ISO-8601
timestamp (e.g. 2026-01 from 2026-01-15T14:30:00Z).

Output columns: month | count | ok% | tokens | cost

The footer shows total months, total delegation count, success count, and
cumulative cost.

Examples:
  zeroclaw delegations monthly              # all runs, per-month breakdown
  zeroclaw delegations monthly --run <id>   # one run only")]
    Monthly {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Per-calendar-quarter delegation breakdown, oldest quarter first
    #[command(long_about = "\
Aggregate all completed delegations by UTC calendar quarter (YYYY-QN),
sorted oldest-first so the table reads chronologically.  Use `--run` to
scope to a single run.

Quarter boundaries are derived from the month in the ISO-8601 timestamp:
  Jan–Mar → Q1 · Apr–Jun → Q2 · Jul–Sep → Q3 · Oct–Dec → Q4

Output columns: quarter | count | ok% | tokens | cost

The footer shows total quarters, total delegation count, success count, and
cumulative cost.

Examples:
  zeroclaw delegations quarterly              # all runs, per-quarter breakdown
  zeroclaw delegations quarterly --run <id>   # one run only")]
    Quarterly {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Cross-product (agent × model) breakdown ranked by tokens consumed
    #[command(long_about = "\
Aggregate all completed delegations by the (agent_name × model) cross-product
and rank pairs by total tokens consumed (descending).  Use `--run` to scope
to a single run.

Output columns: # | agent | model | delegations | tokens | cost

The footer shows total distinct combinations, total delegation count, and
cumulative cost.

Examples:
  zeroclaw delegations agent-model              # all runs, cross-product breakdown
  zeroclaw delegations agent-model --run <id>   # one run only")]
    AgentModel {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Cross-product (provider × model) breakdown ranked by tokens consumed
    #[command(long_about = "\
Aggregate all completed delegations by the (provider × model) cross-product
and rank pairs by total tokens consumed (descending).  Use `--run` to scope
to a single run.

Output columns: # | provider | model | delegations | tokens | cost

The footer shows total distinct combinations, total delegation count, and
cumulative cost.

Examples:
  zeroclaw delegations provider-model              # all runs, cross-product breakdown
  zeroclaw delegations provider-model --run <id>   # one run only")]
    ProviderModel {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Cross-product (agent × provider) breakdown ranked by tokens consumed
    #[command(long_about = "\
Aggregate all completed delegations by the (agent_name × provider) cross-product
and rank pairs by total tokens consumed (descending).  Use `--run` to scope
to a single run.

Output columns: # | agent | provider | delegations | tokens | cost

The footer shows total distinct combinations, total delegation count, and
cumulative cost.

Examples:
  zeroclaw delegations agent-provider              # all runs, cross-product breakdown
  zeroclaw delegations agent-provider --run <id>   # one run only")]
    AgentProvider {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Delegation count, ok%, tokens, and cost grouped by duration bucket
    #[command(long_about = "\
Aggregate all completed delegations into five duration buckets and show
statistics per bucket, ordered fastest-first.  Empty buckets are omitted.

Bucket boundaries:
  instant  <500 ms
  fast     500 ms – 2 s
  normal   2 s – 10 s
  slow     10 s – 60 s
  very slow  ≥ 60 s

Output columns: bucket | count | ok% | tokens | cost

Examples:
  zeroclaw delegations duration-bucket              # all runs
  zeroclaw delegations duration-bucket --run <id>   # one run only")]
    DurationBucket {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Histogram of delegations grouped by token-usage bucket (0–99, 100–999, 1k–9.9k, 10k–99.9k, 100k+)
    TokenBucket {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Histogram of delegations grouped by cost bucket (<$0.001, $0.001–$0.01, $0.01–$0.10, $0.10–$1.00, ≥$1.00)
    CostBucket {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Breakdown of delegations by ISO weekday (Mon–Sun, UTC), showing which days are most active
    Weekday {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Per-ISO-week delegation breakdown (YYYY-WXX), oldest week first
    #[command(long_about = "\
Aggregate all completed delegations by ISO 8601 week (YYYY-WXX),
sorted oldest-first so the table reads chronologically.  Use `--run` to
scope to a single run.

The week key is derived from the RFC-3339 timestamp using chrono's
iso_week() (e.g. 2026-01-05T14:30:00Z → 2026-W02).

Output columns: week | count | ok% | tokens | cost

The footer shows total weeks, total delegation count, success count, and
cumulative cost.

Examples:
  zeroclaw delegations weekly              # all runs, per-week breakdown
  zeroclaw delegations weekly --run <id>   # one run only")]
    Weekly {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Delegation count, ok%, tokens, and cost grouped by nesting depth bucket
    #[command(long_about = "\
Aggregate all completed delegations into five depth buckets and show
statistics per bucket, ordered shallowest-first.  Empty buckets are omitted.

Bucket boundaries:
  root      depth 0   (top-level, orchestrated by the main agent)
  sub       depth 1   (first-level sub-agents)
  deep      depth 2
  deeper    depth 3
  very deep depth 4+

Output columns: depth | count | ok% | tokens | cost

Examples:
  zeroclaw delegations depth-bucket              # all runs
  zeroclaw delegations depth-bucket --run <id>   # one run only")]
    DepthBucket {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Aggregate delegations by model-family tier (haiku / sonnet / opus / other)
    #[command(long_about = "\
Aggregate all completed delegations by model-family tier and print a
breakdown table ordered haiku → sonnet → opus → other.  Empty tiers are omitted.

Tier assignment uses a case-insensitive substring match on the model field:
  haiku   model name contains \"haiku\"
  sonnet  model name contains \"sonnet\"
  opus    model name contains \"opus\"
  other   everything else (including missing/null)

Output columns: tier | count | ok% | tokens | cost

Examples:
  zeroclaw delegations model-tier              # all runs
  zeroclaw delegations model-tier --run <id>   # one run only")]
    ModelTier {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show delegation counts, success rate, token usage, and cost bucketed by provider
    ProviderTier {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show delegation counts, success rate, token usage, and cost bucketed by time of day
    TimeOfDay {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show delegation counts, success rate, token usage, and cost grouped by day of month
    DayOfMonth {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show delegation counts, success rate, token usage, and cost bucketed by cost per 1k tokens
    TokenEfficiency {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Show delegation counts, token usage, and cost split by outcome: succeeded vs. failed
    SuccessBreakdown {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank agents by average cost per delegation (most expensive per call first)
    AgentCostRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank models by average cost per delegation (most expensive per call first)
    ModelCostRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank providers by average cost per delegation (most expensive per call first)
    ProviderCostRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank runs by total cost (most expensive run first)
    RunCostRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank agents by success rate (most reliable first)
    AgentSuccessRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank models by success rate (most reliable first)
    ModelSuccessRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank providers by success rate (most reliable first)
    ProviderSuccessRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank agents by average tokens per delegation (most token-hungry first)
    AgentTokenRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank models by avg tokens per delegation (most token-hungry first)
    ModelTokenRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank providers by avg tokens per delegation (most token-hungry first)
    ProviderTokenRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Rank agents by avg duration per delegation (slowest first)
    AgentDurationRank {
        /// Scope to a specific run ID (default: aggregate across all runs)
        #[arg(long)]
        run: Option<String>,
    },
    /// Compare per-agent stats between two runs side by side
    #[command(long_about = "\
Compare per-agent delegation statistics between two runs side-by-side.

Run IDs may be given as a full UUID or any unique prefix.  When <run_b>
is omitted the most recent stored run that is not <run_a> is used.

Output columns: agent | del_A | del_B | tok_A | tok_B | Δtok | cost_A | cost_B | Δcost

Examples:
  zeroclaw delegations diff f47ac10b          # vs most recent other run
  zeroclaw delegations diff f47ac10b bbb1bbb2 # explicit pair")]
    Diff {
        /// First run ID or unique prefix (the baseline)
        run_a: String,
        /// Second run ID or unique prefix (default: most recent other run)
        run_b: Option<String>,
    },
}

#[derive(Copy, Clone, Debug, Eq, PartialEq, clap::ValueEnum)]
enum DelegationTopBy {
    /// Rank by cumulative token usage (highest first)
    #[value(name = "tokens")]
    Tokens,
    /// Rank by cumulative cost in USD (highest first)
    #[value(name = "cost")]
    Cost,
}

#[derive(Copy, Clone, Debug, Eq, PartialEq, clap::ValueEnum)]
enum DelegationExportFormat {
    /// Newline-delimited JSON — one raw event object per line
    #[value(name = "jsonl")]
    Jsonl,
    /// RFC 4180 CSV — one row per DelegationEnd event
    #[value(name = "csv")]
    Csv,
}

#[derive(Subcommand, Debug)]
enum ConfigCommands {
    /// Dump the full configuration JSON Schema to stdout
    Schema,
}

#[derive(Subcommand, Debug)]
enum AuthCommands {
    /// Login with OpenAI Codex OAuth
    Login {
        /// Provider (`openai-codex`)
        #[arg(long)]
        provider: String,
        /// Profile name (default: default)
        #[arg(long, default_value = "default")]
        profile: String,
        /// Use OAuth device-code flow
        #[arg(long)]
        device_code: bool,
    },
    /// Complete OAuth by pasting redirect URL or auth code
    PasteRedirect {
        /// Provider (`openai-codex`)
        #[arg(long)]
        provider: String,
        /// Profile name (default: default)
        #[arg(long, default_value = "default")]
        profile: String,
        /// Full redirect URL or raw OAuth code
        #[arg(long)]
        input: Option<String>,
    },
    /// Paste setup token / auth token (for Anthropic subscription auth)
    PasteToken {
        /// Provider (`anthropic`)
        #[arg(long)]
        provider: String,
        /// Profile name (default: default)
        #[arg(long, default_value = "default")]
        profile: String,
        /// Token value (if omitted, read interactively)
        #[arg(long)]
        token: Option<String>,
        /// Auth kind override (`authorization` or `api-key`)
        #[arg(long)]
        auth_kind: Option<String>,
    },
    /// Alias for `paste-token` (interactive by default)
    SetupToken {
        /// Provider (`anthropic`)
        #[arg(long)]
        provider: String,
        /// Profile name (default: default)
        #[arg(long, default_value = "default")]
        profile: String,
    },
    /// Refresh OpenAI Codex access token using refresh token
    Refresh {
        /// Provider (`openai-codex`)
        #[arg(long)]
        provider: String,
        /// Profile name or profile id
        #[arg(long)]
        profile: Option<String>,
    },
    /// Remove auth profile
    Logout {
        /// Provider
        #[arg(long)]
        provider: String,
        /// Profile name (default: default)
        #[arg(long, default_value = "default")]
        profile: String,
    },
    /// Set active profile for a provider
    Use {
        /// Provider
        #[arg(long)]
        provider: String,
        /// Profile name or full profile id
        #[arg(long)]
        profile: String,
    },
    /// List auth profiles
    List,
    /// Show auth status with active profile and token expiry info
    Status,
}

#[derive(Subcommand, Debug)]
enum MigrateCommands {
    /// Import memory from an `OpenClaw` workspace into this `ZeroClaw` workspace
    Openclaw {
        /// Optional path to `OpenClaw` workspace (defaults to ~/.openclaw/workspace)
        #[arg(long)]
        source: Option<std::path::PathBuf>,

        /// Validate and preview migration without writing any data
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Subcommand, Debug)]
enum CronCommands {
    /// List all scheduled tasks
    List,
    /// Add a new scheduled task
    Add {
        /// Cron expression
        expression: String,
        /// Optional IANA timezone (e.g. America/Los_Angeles)
        #[arg(long)]
        tz: Option<String>,
        /// Command to run
        command: String,
    },
    /// Add a one-shot scheduled task at an RFC3339 timestamp
    AddAt {
        /// One-shot timestamp in RFC3339 format
        at: String,
        /// Command to run
        command: String,
    },
    /// Add a fixed-interval scheduled task
    AddEvery {
        /// Interval in milliseconds
        every_ms: u64,
        /// Command to run
        command: String,
    },
    /// Add a one-shot delayed task (e.g. "30m", "2h", "1d")
    Once {
        /// Delay duration
        delay: String,
        /// Command to run
        command: String,
    },
    /// Remove a scheduled task
    Remove {
        /// Task ID
        id: String,
    },
    /// Update a scheduled task
    Update {
        /// Task ID
        id: String,
        /// New cron expression
        #[arg(long)]
        expression: Option<String>,
        /// New IANA timezone
        #[arg(long)]
        tz: Option<String>,
        /// New command to run
        #[arg(long)]
        command: Option<String>,
        /// New job name
        #[arg(long)]
        name: Option<String>,
    },
    /// Pause a scheduled task
    Pause {
        /// Task ID
        id: String,
    },
    /// Resume a paused task
    Resume {
        /// Task ID
        id: String,
    },
}

#[derive(Subcommand, Debug)]
enum ModelCommands {
    /// Refresh and cache provider models
    Refresh {
        /// Provider name (defaults to configured default provider)
        #[arg(long)]
        provider: Option<String>,

        /// Force live refresh and ignore fresh cache
        #[arg(long)]
        force: bool,
    },
}

#[derive(Subcommand, Debug)]
enum DoctorCommands {
    /// Probe model catalogs across providers and report availability
    Models {
        /// Probe a specific provider only (default: all known providers)
        #[arg(long)]
        provider: Option<String>,

        /// Prefer cached catalogs when available (skip forced live refresh)
        #[arg(long)]
        use_cache: bool,
    },
}

#[derive(Subcommand, Debug)]
enum ChannelCommands {
    /// List configured channels
    List,
    /// Start all configured channels (Telegram, Discord, Slack)
    Start,
    /// Run health checks for configured channels
    Doctor,
    /// Add a new channel
    Add {
        /// Channel type
        channel_type: String,
        /// Configuration JSON
        config: String,
    },
    /// Remove a channel
    Remove {
        /// Channel name
        name: String,
    },
    /// Bind a Telegram identity (username or numeric user ID) into allowlist
    BindTelegram {
        /// Telegram identity to allow (username without '@' or numeric user ID)
        identity: String,
    },
}

#[derive(Subcommand, Debug)]
enum SkillCommands {
    /// List installed skills
    List,
    /// Install a skill from a git URL (HTTPS/SSH) or local path
    Install {
        /// Git URL (HTTPS/SSH) or local path
        source: String,
    },
    /// Remove an installed skill
    Remove {
        /// Skill name
        name: String,
    },
}

#[derive(Subcommand, Debug)]
enum IntegrationCommands {
    /// Show details about a specific integration
    Info {
        /// Integration name
        name: String,
    },
}

#[tokio::main]
#[allow(clippy::too_many_lines)]
async fn main() -> Result<()> {
    // Install default crypto provider for Rustls TLS.
    // This prevents the error: "could not automatically determine the process-level CryptoProvider"
    // when both aws-lc-rs and ring features are available (or neither is explicitly selected).
    if let Err(e) = rustls::crypto::ring::default_provider().install_default() {
        eprintln!("Warning: Failed to install default crypto provider: {e:?}");
    }

    let cli = Cli::parse();

    // Completions must remain stdout-only and should not load config or initialize logging.
    // This avoids warnings/log lines corrupting sourced completion scripts.
    if let Commands::Completions { shell } = &cli.command {
        let mut stdout = std::io::stdout().lock();
        write_shell_completion(*shell, &mut stdout)?;
        return Ok(());
    }

    // Initialize logging - respects RUST_LOG env var, defaults to INFO
    let subscriber = fmt::Subscriber::builder()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .finish();

    tracing::subscriber::set_global_default(subscriber).expect("setting default subscriber failed");

    // Onboard runs quick setup by default, or the interactive wizard with --interactive.
    // The onboard wizard uses reqwest::blocking internally, which creates its own
    // Tokio runtime. To avoid "Cannot drop a runtime in a context where blocking is
    // not allowed", we run the wizard on a blocking thread via spawn_blocking.
    if let Commands::Onboard {
        interactive,
        channels_only,
        api_key,
        provider,
        model,
        memory,
    } = &cli.command
    {
        let interactive = *interactive;
        let channels_only = *channels_only;
        let api_key = api_key.clone();
        let provider = provider.clone();
        let model = model.clone();
        let memory = memory.clone();

        if interactive && channels_only {
            bail!("Use either --interactive or --channels-only, not both");
        }
        if channels_only
            && (api_key.is_some() || provider.is_some() || model.is_some() || memory.is_some())
        {
            bail!("--channels-only does not accept --api-key, --provider, --model, or --memory");
        }
        let config = if channels_only {
            onboard::run_channels_repair_wizard().await
        } else if interactive {
            onboard::run_wizard().await
        } else {
            onboard::run_quick_setup(
                api_key.as_deref(),
                provider.as_deref(),
                model.as_deref(),
                memory.as_deref(),
            )
            .await
        }?;
        // Auto-start channels if user said yes during wizard
        if std::env::var("ZEROCLAW_AUTOSTART_CHANNELS").as_deref() == Ok("1") {
            channels::start_channels(config).await?;
        }
        return Ok(());
    }

    // All other commands need config loaded first
    let mut config = Config::load_or_init().await?;
    config.apply_env_overrides();

    match cli.command {
        Commands::Onboard { .. } => unreachable!(),
        Commands::Completions { .. } => unreachable!(),

        Commands::Agent {
            message,
            provider,
            model,
            temperature,
            peripheral,
        } => agent::run(config, message, provider, model, temperature, peripheral)
            .await
            .map(|_| ()),

        Commands::Gateway { port, host } => {
            let port = port.unwrap_or(config.gateway.port);
            let host = host.unwrap_or_else(|| config.gateway.host.clone());
            if port == 0 {
                info!("🚀 Starting ZeroClaw Gateway on {host} (random port)");
            } else {
                info!("🚀 Starting ZeroClaw Gateway on {host}:{port}");
            }
            gateway::run_gateway(&host, port, config).await
        }

        Commands::Daemon { port, host } => {
            let port = port.unwrap_or(config.gateway.port);
            let host = host.unwrap_or_else(|| config.gateway.host.clone());
            if port == 0 {
                info!("🧠 Starting ZeroClaw Daemon on {host} (random port)");
            } else {
                info!("🧠 Starting ZeroClaw Daemon on {host}:{port}");
            }
            daemon::run(config, host, port).await
        }

        Commands::Status => {
            println!("🦀 ZeroClaw Status");
            println!();
            println!("Version:     {}", env!("CARGO_PKG_VERSION"));
            println!("Workspace:   {}", config.workspace_dir.display());
            println!("Config:      {}", config.config_path.display());
            println!();
            println!(
                "🤖 Provider:      {}",
                config.default_provider.as_deref().unwrap_or("openrouter")
            );
            println!(
                "   Model:         {}",
                config.default_model.as_deref().unwrap_or("(default)")
            );
            println!("📊 Observability:  {}", config.observability.backend);
            println!("🛡️  Autonomy:      {:?}", config.autonomy.level);
            println!("⚙️  Runtime:       {}", config.runtime.kind);
            let effective_memory_backend = memory::effective_memory_backend_name(
                &config.memory.backend,
                Some(&config.storage.provider.config),
            );
            println!(
                "💓 Heartbeat:      {}",
                if config.heartbeat.enabled {
                    format!("every {}min", config.heartbeat.interval_minutes)
                } else {
                    "disabled".into()
                }
            );
            println!(
                "🧠 Memory:         {} (auto-save: {})",
                effective_memory_backend,
                if config.memory.auto_save { "on" } else { "off" }
            );

            println!();
            println!("Security:");
            println!("  Workspace only:    {}", config.autonomy.workspace_only);
            println!(
                "  Allowed commands:  {}",
                config.autonomy.allowed_commands.join(", ")
            );
            println!(
                "  Max actions/hour:  {}",
                config.autonomy.max_actions_per_hour
            );
            println!(
                "  Max cost/day:      ${:.2}",
                f64::from(config.autonomy.max_cost_per_day_cents) / 100.0
            );
            println!();
            println!("Channels:");
            println!("  CLI:      ✅ always");
            for (name, configured) in [
                ("Telegram", config.channels_config.telegram.is_some()),
                ("Discord", config.channels_config.discord.is_some()),
                ("Slack", config.channels_config.slack.is_some()),
                ("Webhook", config.channels_config.webhook.is_some()),
            ] {
                println!(
                    "  {name:9} {}",
                    if configured {
                        "✅ configured"
                    } else {
                        "❌ not configured"
                    }
                );
            }
            println!();
            println!("Peripherals:");
            println!(
                "  Enabled:   {}",
                if config.peripherals.enabled {
                    "yes"
                } else {
                    "no"
                }
            );
            println!("  Boards:    {}", config.peripherals.boards.len());

            println!();
            let delegation_log = std::path::PathBuf::from(
                shellexpand::tilde("~/.zeroclaw/state/delegation.jsonl").as_ref(),
            );
            println!("Delegations:");
            match observability::delegation_report::get_log_summary(&delegation_log) {
                Ok(Some(s)) => {
                    println!("  Runs stored:      {}", s.run_count);
                    println!("  Delegations:      {}", s.total_delegations);
                    println!(
                        "  Total tokens:     {}",
                        if s.total_tokens > 0 {
                            s.total_tokens.to_string()
                        } else {
                            "—".to_owned()
                        }
                    );
                    println!(
                        "  Total cost:       {}",
                        if s.total_cost_usd > 0.0 {
                            format!("${:.4}", s.total_cost_usd)
                        } else {
                            "—".to_owned()
                        }
                    );
                    if let Some(ts) = s.latest_run_time {
                        println!("  Latest run:       {}", ts.format("%Y-%m-%d %H:%M:%S UTC"));
                    }
                }
                Ok(None) => println!("  No delegation data recorded yet."),
                Err(e) => println!("  (could not read log: {e})"),
            }

            Ok(())
        }

        Commands::Cron { cron_command } => cron::handle_command(cron_command, &config),

        Commands::Models { model_command } => match model_command {
            ModelCommands::Refresh { provider, force } => {
                let config_for_refresh = config.clone();
                tokio::task::spawn_blocking(move || {
                    onboard::run_models_refresh(&config_for_refresh, provider.as_deref(), force)
                })
                .await
                .map_err(|e| anyhow::anyhow!("models refresh task failed: {e}"))?
            }
        },

        Commands::Providers => {
            let providers = providers::list_providers();
            let current = config
                .default_provider
                .as_deref()
                .unwrap_or("openrouter")
                .trim()
                .to_ascii_lowercase();
            println!("Supported providers ({} total):\n", providers.len());
            println!("  ID (use in config)  DESCRIPTION");
            println!("  ─────────────────── ───────────");
            for p in &providers {
                let is_active = p.name.eq_ignore_ascii_case(&current)
                    || p.aliases
                        .iter()
                        .any(|alias| alias.eq_ignore_ascii_case(&current));
                let marker = if is_active { " (active)" } else { "" };
                let local_tag = if p.local { " [local]" } else { "" };
                let aliases = if p.aliases.is_empty() {
                    String::new()
                } else {
                    format!("  (aliases: {})", p.aliases.join(", "))
                };
                println!(
                    "  {:<19} {}{}{}{}",
                    p.name, p.display_name, local_tag, marker, aliases
                );
            }
            println!("\n  custom:<URL>   Any OpenAI-compatible endpoint");
            println!("  anthropic-custom:<URL>  Any Anthropic-compatible endpoint");
            Ok(())
        }

        Commands::Service { service_command } => service::handle_command(&service_command, &config),

        Commands::Doctor { doctor_command } => match doctor_command {
            Some(DoctorCommands::Models {
                provider,
                use_cache,
            }) => {
                let config_for_models = config.clone();
                tokio::task::spawn_blocking(move || {
                    doctor::run_models(&config_for_models, provider.as_deref(), use_cache)
                })
                .await
                .map_err(|e| anyhow::anyhow!("doctor models task failed: {e}"))?
            }
            None => doctor::run(&config),
        },

        Commands::Channel { channel_command } => match channel_command {
            ChannelCommands::Start => channels::start_channels(config).await,
            ChannelCommands::Doctor => channels::doctor_channels(config).await,
            other => channels::handle_command(other, &config).await,
        },

        Commands::Integrations {
            integration_command,
        } => integrations::handle_command(integration_command, &config),

        Commands::Skills { skill_command } => skills::handle_command(skill_command, &config),

        Commands::Migrate { migrate_command } => {
            migration::handle_command(migrate_command, &config).await
        }

        Commands::Auth { auth_command } => handle_auth_command(auth_command, &config).await,

        Commands::Hardware { hardware_command } => {
            hardware::handle_command(hardware_command.clone(), &config)
        }

        Commands::Peripheral { peripheral_command } => {
            peripherals::handle_command(peripheral_command.clone(), &config).await
        }

        Commands::Config { config_command } => match config_command {
            ConfigCommands::Schema => {
                let schema = schemars::schema_for!(config::Config);
                println!(
                    "{}",
                    serde_json::to_string_pretty(&schema).expect("failed to serialize JSON Schema")
                );
                Ok(())
            }
        },

        Commands::Delegations { delegation_command } => {
            let log_path = std::path::PathBuf::from(
                shellexpand::tilde("~/.zeroclaw/state/delegation.jsonl").as_ref(),
            );
            match delegation_command {
                None => observability::delegation_report::print_summary(&log_path),
                Some(DelegationCommands::List) => {
                    observability::delegation_report::print_runs(&log_path)
                }
                Some(DelegationCommands::Show { run }) => {
                    observability::delegation_report::print_tree(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Stats { run }) => {
                    observability::delegation_report::print_stats(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Export { run, format }) => {
                    let fmt = match format {
                        DelegationExportFormat::Jsonl => {
                            observability::delegation_report::ExportFormat::Jsonl
                        }
                        DelegationExportFormat::Csv => {
                            observability::delegation_report::ExportFormat::Csv
                        }
                    };
                    observability::delegation_report::print_export(&log_path, run.as_deref(), fmt)
                }
                Some(DelegationCommands::Top { by, limit }) => {
                    let top_by = match by {
                        DelegationTopBy::Tokens => observability::delegation_report::TopBy::Tokens,
                        DelegationTopBy::Cost => observability::delegation_report::TopBy::Cost,
                    };
                    observability::delegation_report::print_top(&log_path, top_by, limit)
                }
                Some(DelegationCommands::Prune { keep }) => {
                    observability::delegation_report::print_prune(&log_path, keep)
                }
                Some(DelegationCommands::Models { run }) => {
                    observability::delegation_report::print_models(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Providers { run }) => {
                    observability::delegation_report::print_providers(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Depth { run }) => {
                    observability::delegation_report::print_depth(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Errors { run }) => {
                    observability::delegation_report::print_errors(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Slow { run, limit }) => {
                    observability::delegation_report::print_slow(&log_path, run.as_deref(), limit)
                }
                Some(DelegationCommands::Cost { run }) => {
                    observability::delegation_report::print_cost(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Recent { run, limit }) => {
                    observability::delegation_report::print_recent(&log_path, run.as_deref(), limit)
                }
                Some(DelegationCommands::Active { run }) => {
                    observability::delegation_report::print_active(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Agent { name, run }) => {
                    observability::delegation_report::print_agent(&log_path, &name, run.as_deref())
                }
                Some(DelegationCommands::Model { name, run }) => {
                    observability::delegation_report::print_model(&log_path, &name, run.as_deref())
                }
                Some(DelegationCommands::Provider { name, run }) => {
                    observability::delegation_report::print_provider(
                        &log_path,
                        &name,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::Run { id }) => {
                    observability::delegation_report::print_run(&log_path, &id)
                }
                Some(DelegationCommands::DepthView { level, run }) => {
                    observability::delegation_report::print_depth_view(
                        &log_path,
                        level,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::Daily { run }) => {
                    observability::delegation_report::print_daily(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Hourly { run }) => {
                    observability::delegation_report::print_hourly(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Monthly { run }) => {
                    observability::delegation_report::print_monthly(&log_path, run.as_deref())
                }
                Some(DelegationCommands::Quarterly { run }) => {
                    observability::delegation_report::print_quarterly(&log_path, run.as_deref())
                }
                Some(DelegationCommands::AgentModel { run }) => {
                    observability::delegation_report::print_agent_model(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ProviderModel { run }) => {
                    observability::delegation_report::print_provider_model(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::AgentProvider { run }) => {
                    observability::delegation_report::print_agent_provider(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::DurationBucket { run }) => {
                    observability::delegation_report::print_duration_bucket(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::TokenBucket { run }) => {
                    observability::delegation_report::print_token_bucket(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::CostBucket { run }) => {
                    observability::delegation_report::print_cost_bucket(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::Weekday { run }) => {
                    observability::delegation_report::print_weekday(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::Weekly { run }) => {
                    observability::delegation_report::print_weekly(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::DepthBucket { run }) => {
                    observability::delegation_report::print_depth_bucket(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ModelTier { run }) => {
                    observability::delegation_report::print_model_tier(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ProviderTier { run }) => {
                    observability::delegation_report::print_provider_tier(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::TimeOfDay { run }) => {
                    observability::delegation_report::print_time_of_day(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::DayOfMonth { run }) => {
                    observability::delegation_report::print_day_of_month(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::TokenEfficiency { run }) => {
                    observability::delegation_report::print_token_efficiency(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::SuccessBreakdown { run }) => {
                    observability::delegation_report::print_success_breakdown(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::AgentCostRank { run }) => {
                    observability::delegation_report::print_agent_cost_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ModelCostRank { run }) => {
                    observability::delegation_report::print_model_cost_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ProviderCostRank { run }) => {
                    observability::delegation_report::print_provider_cost_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::RunCostRank { run }) => {
                    observability::delegation_report::print_run_cost_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::AgentSuccessRank { run }) => {
                    observability::delegation_report::print_agent_success_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ModelSuccessRank { run }) => {
                    observability::delegation_report::print_model_success_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ProviderSuccessRank { run }) => {
                    observability::delegation_report::print_provider_success_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::AgentTokenRank { run }) => {
                    observability::delegation_report::print_agent_token_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ModelTokenRank { run }) => {
                    observability::delegation_report::print_model_token_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::ProviderTokenRank { run }) => {
                    observability::delegation_report::print_provider_token_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::AgentDurationRank { run }) => {
                    observability::delegation_report::print_agent_duration_rank(
                        &log_path,
                        run.as_deref(),
                    )
                }
                Some(DelegationCommands::Diff { run_a, run_b }) => {
                    observability::delegation_report::print_diff(
                        &log_path,
                        &run_a,
                        run_b.as_deref(),
                    )
                }
            }
        }
    }
}

fn write_shell_completion<W: Write>(shell: CompletionShell, writer: &mut W) -> Result<()> {
    use clap_complete::generate;
    use clap_complete::shells;

    let mut cmd = Cli::command();
    let bin_name = cmd.get_name().to_string();

    match shell {
        CompletionShell::Bash => generate(shells::Bash, &mut cmd, bin_name.clone(), writer),
        CompletionShell::Fish => generate(shells::Fish, &mut cmd, bin_name.clone(), writer),
        CompletionShell::Zsh => generate(shells::Zsh, &mut cmd, bin_name.clone(), writer),
        CompletionShell::PowerShell => {
            generate(shells::PowerShell, &mut cmd, bin_name.clone(), writer);
        }
        CompletionShell::Elvish => generate(shells::Elvish, &mut cmd, bin_name, writer),
    }

    writer.flush()?;
    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PendingOpenAiLogin {
    profile: String,
    code_verifier: String,
    state: String,
    created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PendingOpenAiLoginFile {
    profile: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    code_verifier: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    encrypted_code_verifier: Option<String>,
    state: String,
    created_at: String,
}

fn pending_openai_login_path(config: &Config) -> std::path::PathBuf {
    auth::state_dir_from_config(config).join("auth-openai-pending.json")
}

fn pending_openai_secret_store(config: &Config) -> security::secrets::SecretStore {
    security::secrets::SecretStore::new(
        &auth::state_dir_from_config(config),
        config.secrets.encrypt,
    )
}

#[cfg(unix)]
fn set_owner_only_permissions(path: &std::path::Path) -> Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    Ok(())
}

#[cfg(not(unix))]
fn set_owner_only_permissions(_path: &std::path::Path) -> Result<()> {
    Ok(())
}

fn save_pending_openai_login(config: &Config, pending: &PendingOpenAiLogin) -> Result<()> {
    let path = pending_openai_login_path(config);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let secret_store = pending_openai_secret_store(config);
    let encrypted_code_verifier = secret_store.encrypt(&pending.code_verifier)?;
    let persisted = PendingOpenAiLoginFile {
        profile: pending.profile.clone(),
        code_verifier: None,
        encrypted_code_verifier: Some(encrypted_code_verifier),
        state: pending.state.clone(),
        created_at: pending.created_at.clone(),
    };
    let tmp = path.with_extension(format!(
        "tmp.{}.{}",
        std::process::id(),
        chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
    ));
    let json = serde_json::to_vec_pretty(&persisted)?;
    std::fs::write(&tmp, json)?;
    set_owner_only_permissions(&tmp)?;
    std::fs::rename(tmp, &path)?;
    set_owner_only_permissions(&path)?;
    Ok(())
}

fn load_pending_openai_login(config: &Config) -> Result<Option<PendingOpenAiLogin>> {
    let path = pending_openai_login_path(config);
    if !path.exists() {
        return Ok(None);
    }
    let bytes = std::fs::read(path)?;
    if bytes.is_empty() {
        return Ok(None);
    }
    let persisted: PendingOpenAiLoginFile = serde_json::from_slice(&bytes)?;
    let secret_store = pending_openai_secret_store(config);
    let code_verifier = if let Some(encrypted) = persisted.encrypted_code_verifier {
        secret_store.decrypt(&encrypted)?
    } else if let Some(plaintext) = persisted.code_verifier {
        plaintext
    } else {
        bail!("Pending OpenAI login is missing code verifier");
    };
    Ok(Some(PendingOpenAiLogin {
        profile: persisted.profile,
        code_verifier,
        state: persisted.state,
        created_at: persisted.created_at,
    }))
}

fn clear_pending_openai_login(config: &Config) {
    let path = pending_openai_login_path(config);
    if let Ok(file) = std::fs::OpenOptions::new().write(true).open(&path) {
        let _ = file.set_len(0);
        let _ = file.sync_all();
    }
    let _ = std::fs::remove_file(path);
}

fn read_auth_input(prompt: &str) -> Result<String> {
    let input = Password::new()
        .with_prompt(prompt)
        .allow_empty_password(false)
        .interact()?;
    Ok(input.trim().to_string())
}

fn read_plain_input(prompt: &str) -> Result<String> {
    let input: String = Input::new().with_prompt(prompt).interact_text()?;
    Ok(input.trim().to_string())
}

fn extract_openai_account_id_for_profile(access_token: &str) -> Option<String> {
    let account_id = auth::openai_oauth::extract_account_id_from_jwt(access_token);
    if account_id.is_none() {
        warn!(
            "Could not extract OpenAI account id from OAuth access token; \
             requests may fail until re-authentication."
        );
    }
    account_id
}

fn format_expiry(profile: &auth::profiles::AuthProfile) -> String {
    match profile
        .token_set
        .as_ref()
        .and_then(|token_set| token_set.expires_at)
    {
        Some(ts) => {
            let now = chrono::Utc::now();
            if ts <= now {
                format!("expired at {}", ts.to_rfc3339())
            } else {
                let mins = (ts - now).num_minutes();
                format!("expires in {mins}m ({})", ts.to_rfc3339())
            }
        }
        None => "n/a".to_string(),
    }
}

#[allow(clippy::too_many_lines)]
async fn handle_auth_command(auth_command: AuthCommands, config: &Config) -> Result<()> {
    let auth_service = auth::AuthService::from_config(config);

    match auth_command {
        AuthCommands::Login {
            provider,
            profile,
            device_code,
        } => {
            let provider = auth::normalize_provider(&provider)?;
            if provider != "openai-codex" {
                bail!("`auth login` currently supports only --provider openai-codex");
            }

            let client = reqwest::Client::new();

            if device_code {
                match auth::openai_oauth::start_device_code_flow(&client).await {
                    Ok(device) => {
                        println!("OpenAI device-code login started.");
                        println!("Visit: {}", device.verification_uri);
                        println!("Code:  {}", device.user_code);
                        if let Some(uri_complete) = &device.verification_uri_complete {
                            println!("Fast link: {uri_complete}");
                        }
                        if let Some(message) = &device.message {
                            println!("{message}");
                        }

                        let token_set =
                            auth::openai_oauth::poll_device_code_tokens(&client, &device).await?;
                        let account_id =
                            extract_openai_account_id_for_profile(&token_set.access_token);

                        auth_service.store_openai_tokens(&profile, token_set, account_id, true)?;
                        clear_pending_openai_login(config);

                        println!("Saved profile {profile}");
                        println!("Active profile for openai-codex: {profile}");
                        return Ok(());
                    }
                    Err(e) => {
                        println!(
                            "Device-code flow unavailable: {e}. Falling back to browser/paste flow."
                        );
                    }
                }
            }

            let pkce = auth::openai_oauth::generate_pkce_state();
            let pending = PendingOpenAiLogin {
                profile: profile.clone(),
                code_verifier: pkce.code_verifier.clone(),
                state: pkce.state.clone(),
                created_at: chrono::Utc::now().to_rfc3339(),
            };
            save_pending_openai_login(config, &pending)?;

            let authorize_url = auth::openai_oauth::build_authorize_url(&pkce);
            println!("Open this URL in your browser and authorize access:");
            println!("{authorize_url}");
            println!();
            println!("Waiting for callback at http://localhost:1455/auth/callback ...");

            let code = match auth::openai_oauth::receive_loopback_code(
                &pkce.state,
                std::time::Duration::from_secs(180),
            )
            .await
            {
                Ok(code) => code,
                Err(e) => {
                    println!("Callback capture failed: {e}");
                    println!(
                            "Run `zeroclaw auth paste-redirect --provider openai-codex --profile {profile}`"
                        );
                    return Ok(());
                }
            };

            let token_set =
                auth::openai_oauth::exchange_code_for_tokens(&client, &code, &pkce).await?;
            let account_id = extract_openai_account_id_for_profile(&token_set.access_token);

            auth_service.store_openai_tokens(&profile, token_set, account_id, true)?;
            clear_pending_openai_login(config);

            println!("Saved profile {profile}");
            println!("Active profile for openai-codex: {profile}");
            Ok(())
        }

        AuthCommands::PasteRedirect {
            provider,
            profile,
            input,
        } => {
            let provider = auth::normalize_provider(&provider)?;
            if provider != "openai-codex" {
                bail!("`auth paste-redirect` currently supports only --provider openai-codex");
            }

            let pending = load_pending_openai_login(config)?.ok_or_else(|| {
                anyhow::anyhow!(
                    "No pending OpenAI login found. Run `zeroclaw auth login --provider openai-codex` first."
                )
            })?;

            if pending.profile != profile {
                bail!(
                    "Pending login profile mismatch: pending={}, requested={}",
                    pending.profile,
                    profile
                );
            }

            let redirect_input = match input {
                Some(value) => value,
                None => read_plain_input("Paste redirect URL or OAuth code")?,
            };

            let code = auth::openai_oauth::parse_code_from_redirect(
                &redirect_input,
                Some(&pending.state),
            )?;

            let pkce = auth::openai_oauth::PkceState {
                code_verifier: pending.code_verifier.clone(),
                code_challenge: String::new(),
                state: pending.state.clone(),
            };

            let client = reqwest::Client::new();
            let token_set =
                auth::openai_oauth::exchange_code_for_tokens(&client, &code, &pkce).await?;
            let account_id = extract_openai_account_id_for_profile(&token_set.access_token);

            auth_service.store_openai_tokens(&profile, token_set, account_id, true)?;
            clear_pending_openai_login(config);

            println!("Saved profile {profile}");
            println!("Active profile for openai-codex: {profile}");
            Ok(())
        }

        AuthCommands::PasteToken {
            provider,
            profile,
            token,
            auth_kind,
        } => {
            let provider = auth::normalize_provider(&provider)?;
            let token = match token {
                Some(token) => token.trim().to_string(),
                None => read_auth_input("Paste token")?,
            };
            if token.is_empty() {
                bail!("Token cannot be empty");
            }

            let kind = auth::anthropic_token::detect_auth_kind(&token, auth_kind.as_deref());
            let mut metadata = std::collections::HashMap::new();
            metadata.insert(
                "auth_kind".to_string(),
                kind.as_metadata_value().to_string(),
            );

            auth_service.store_provider_token(&provider, &profile, &token, metadata, true)?;
            println!("Saved profile {profile}");
            println!("Active profile for {provider}: {profile}");
            Ok(())
        }

        AuthCommands::SetupToken { provider, profile } => {
            let provider = auth::normalize_provider(&provider)?;
            let token = read_auth_input("Paste token")?;
            if token.is_empty() {
                bail!("Token cannot be empty");
            }

            let kind = auth::anthropic_token::detect_auth_kind(&token, Some("authorization"));
            let mut metadata = std::collections::HashMap::new();
            metadata.insert(
                "auth_kind".to_string(),
                kind.as_metadata_value().to_string(),
            );

            auth_service.store_provider_token(&provider, &profile, &token, metadata, true)?;
            println!("Saved profile {profile}");
            println!("Active profile for {provider}: {profile}");
            Ok(())
        }

        AuthCommands::Refresh { provider, profile } => {
            let provider = auth::normalize_provider(&provider)?;
            if provider != "openai-codex" {
                bail!("`auth refresh` currently supports only --provider openai-codex");
            }

            match auth_service
                .get_valid_openai_access_token(profile.as_deref())
                .await?
            {
                Some(_) => {
                    println!("OpenAI Codex token is valid (refresh completed if needed).");
                    Ok(())
                }
                None => {
                    bail!(
                        "No OpenAI Codex auth profile found. Run `zeroclaw auth login --provider openai-codex`."
                    )
                }
            }
        }

        AuthCommands::Logout { provider, profile } => {
            let provider = auth::normalize_provider(&provider)?;
            let removed = auth_service.remove_profile(&provider, &profile)?;
            if removed {
                println!("Removed auth profile {provider}:{profile}");
            } else {
                println!("Auth profile not found: {provider}:{profile}");
            }
            Ok(())
        }

        AuthCommands::Use { provider, profile } => {
            let provider = auth::normalize_provider(&provider)?;
            auth_service.set_active_profile(&provider, &profile)?;
            println!("Active profile for {provider}: {profile}");
            Ok(())
        }

        AuthCommands::List => {
            let data = auth_service.load_profiles()?;
            if data.profiles.is_empty() {
                println!("No auth profiles configured.");
                return Ok(());
            }

            for (id, profile) in &data.profiles {
                let active = data
                    .active_profiles
                    .get(&profile.provider)
                    .is_some_and(|active_id| active_id == id);
                let marker = if active { "*" } else { " " };
                println!("{marker} {id}");
            }

            Ok(())
        }

        AuthCommands::Status => {
            let data = auth_service.load_profiles()?;
            if data.profiles.is_empty() {
                println!("No auth profiles configured.");
                return Ok(());
            }

            for (id, profile) in &data.profiles {
                let active = data
                    .active_profiles
                    .get(&profile.provider)
                    .is_some_and(|active_id| active_id == id);
                let marker = if active { "*" } else { " " };
                println!(
                    "{} {} kind={:?} account={} expires={}",
                    marker,
                    id,
                    profile.kind,
                    crate::security::redact(profile.account_id.as_deref().unwrap_or("unknown")),
                    format_expiry(profile)
                );
            }

            println!();
            println!("Active profiles:");
            for (provider, profile_id) in &data.active_profiles {
                println!("  {provider}: {profile_id}");
            }

            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::{CommandFactory, Parser};

    #[test]
    fn cli_definition_has_no_flag_conflicts() {
        Cli::command().debug_assert();
    }

    #[test]
    fn onboard_help_includes_model_flag() {
        let cmd = Cli::command();
        let onboard = cmd
            .get_subcommands()
            .find(|subcommand| subcommand.get_name() == "onboard")
            .expect("onboard subcommand must exist");

        let has_model_flag = onboard
            .get_arguments()
            .any(|arg| arg.get_id().as_str() == "model" && arg.get_long() == Some("model"));

        assert!(
            has_model_flag,
            "onboard help should include --model for quick setup overrides"
        );
    }

    #[test]
    fn onboard_cli_accepts_model_provider_and_api_key_in_quick_mode() {
        let cli = Cli::try_parse_from([
            "zeroclaw",
            "onboard",
            "--provider",
            "openrouter",
            "--model",
            "custom-model-946",
            "--api-key",
            "sk-issue946",
        ])
        .expect("quick onboard invocation should parse");

        match cli.command {
            Commands::Onboard {
                interactive,
                channels_only,
                api_key,
                provider,
                model,
                ..
            } => {
                assert!(!interactive);
                assert!(!channels_only);
                assert_eq!(provider.as_deref(), Some("openrouter"));
                assert_eq!(model.as_deref(), Some("custom-model-946"));
                assert_eq!(api_key.as_deref(), Some("sk-issue946"));
            }
            other => panic!("expected onboard command, got {other:?}"),
        }
    }

    #[test]
    fn completions_cli_parses_supported_shells() {
        for shell in ["bash", "fish", "zsh", "powershell", "elvish"] {
            let cli = Cli::try_parse_from(["zeroclaw", "completions", shell])
                .expect("completions invocation should parse");
            match cli.command {
                Commands::Completions { .. } => {}
                other => panic!("expected completions command, got {other:?}"),
            }
        }
    }

    #[test]
    fn completion_generation_mentions_binary_name() {
        let mut output = Vec::new();
        write_shell_completion(CompletionShell::Bash, &mut output)
            .expect("completion generation should succeed");
        let script = String::from_utf8(output).expect("completion output should be valid utf-8");
        assert!(
            script.contains("zeroclaw"),
            "completion script should reference binary name"
        );
    }
}
