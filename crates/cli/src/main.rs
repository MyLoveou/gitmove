use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use gitmove_core::error::CoreError;
use gitmove_core::json::Envelope;

#[derive(Parser)]
#[command(name = "gitmove", version, about = "gitmove v2 core CLI")]
struct Cli {
    /// Workspace path (defaults to the current directory).
    #[arg(short = 'C', long = "dir", global = true)]
    dir: Option<PathBuf>,
    /// Emit the shared JSON envelope.
    #[arg(long, global = true)]
    json: bool,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Info,
    Projects {
        #[command(subcommand)]
        action: ProjectsAction,
    },
    Audit {
        #[arg(long)]
        all: bool,
    },
    #[command(name = "rev")]
    Revision {
        #[command(subcommand)]
        action: RevAction,
    },
    Commit {
        #[arg(short = 'm', long)]
        message: String,
        #[arg(long)]
        members: bool,
        #[arg(long)]
        strict: bool,
        /// Back up every configured asset target as part of the revision.
        #[arg(long)]
        assets: bool,
    },
    Checkout {
        id: i64,
        #[arg(long)]
        force: bool,
    },
    #[command(name = "ws")]
    Workspace {
        #[command(subcommand)]
        action: WsAction,
    },
    #[command(name = "dep")]
    Dependencies {
        #[command(subcommand)]
        action: DepAction,
    },
    Asset {
        #[command(subcommand)]
        action: AssetAction,
    },
    Index {
        #[command(subcommand)]
        action: IndexAction,
    },
    /// MCP server over stdio (JSON-RPC 2.0).
    Mcp,
}

#[derive(Subcommand)]
enum ProjectsAction {
    List,
    Info,
}

#[derive(Subcommand)]
enum RevAction {
    Log {
        #[arg(long, default_value_t = 20)]
        limit: u32,
    },
    Show {
        id: i64,
    },
}

#[derive(Subcommand)]
enum WsAction {
    Status,
    Diff {
        member: String,
    },
    Contribute {
        member: String,
        #[arg(long)]
        branch: Option<String>,
        #[arg(long)]
        no_push: bool,
    },
}

#[derive(Subcommand)]
enum DepAction {
    List,
}

#[derive(Subcommand)]
enum AssetAction {
    Init {
        #[arg(long)]
        target: Option<String>,
    },
    Status,
    Backup {
        #[arg(long)]
        target: Option<String>,
    },
    Snapshots {
        #[arg(long, default_value_t = 20)]
        limit: u32,
    },
    Check {
        #[arg(long)]
        target: Option<String>,
    },
    Restore {
        snapshot: String,
        #[arg(long)]
        target: Option<String>,
    },
}

#[derive(Subcommand)]
enum IndexAction {
    Rebuild,
}

fn workspace(dir: &Option<PathBuf>) -> PathBuf {
    dir.clone().unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

fn success(tool: &str, value: impl serde::Serialize) -> Envelope<serde_json::Value> {
    Envelope::success(tool, None, serde_json::to_value(value).unwrap_or(serde_json::Value::Null))
}

fn run(cli: &Cli, root: &Path) -> Result<Envelope<serde_json::Value>, CoreError> {
    match &cli.command {
        Command::Info => Ok(success(
            "gitmove_info",
            serde_json::json!({
                "version": env!("CARGO_PKG_VERSION"),
                "core": "rust",
                "home": gitmove_core::paths::home_dir().to_string_lossy().replace('\\', "/"),
                "workspace": root.to_string_lossy().replace('\\', "/"),
                "restic": gitmove_core::asset::restic_version(),
            }),
        )),
        Command::Projects { action } => match action {
            ProjectsAction::List => {
                let entries = gitmove_core::registry::load()?;
                Ok(success("gitmove_list_projects", gitmove_core::registry::to_rows(&entries)))
            }
            ProjectsAction::Info => Ok(success(
                "gitmove_projects_info",
                serde_json::json!({ "count": gitmove_core::registry::load()?.len() }),
            )),
        },
        Command::Audit { all } => {
            let rows = if *all {
                gitmove_core::audit::audit_all()?
            } else {
                vec![gitmove_core::audit::audit_current(root)?]
            };
            Ok(success("gitmove_audit", rows))
        }
        Command::Revision { action } => match action {
            RevAction::Log { limit } => Ok(success("gitmove_rev_log", gitmove_core::revision::log(root, *limit)?)),
            RevAction::Show { id } => Ok(success("gitmove_rev_show", gitmove_core::revision::show(root, *id)?)),
        },
        Command::Commit { message, members, strict, assets } => {
            let outcome = gitmove_core::revision::commit(root, message, *members, *strict, *assets)?;
            Ok(success("gitmove_commit", outcome))
        }
        Command::Checkout { id, force } => Ok(success(
            "gitmove_checkout",
            gitmove_core::revision::checkout(root, *id, *force)?,
        )),
        Command::Workspace { action } => match action {
            WsAction::Status => Ok(success("gitmove_ws_status", gitmove_core::workspace::status(root)?)),
            WsAction::Diff { member } => Ok(success("gitmove_ws_diff", gitmove_core::contribute::diff(root, member)?)),
            WsAction::Contribute { member, branch, no_push } => Ok(success(
                "gitmove_ws_contribute",
                gitmove_core::contribute::contribute(root, member, branch.clone(), *no_push)?,
            )),
        },
        Command::Dependencies { action: DepAction::List } => {
            let rows = gitmove_core::deps::list(root)?;
            let payload: Vec<serde_json::Value> = rows
                .iter()
                .map(|dep| {
                    serde_json::json!({
                        "name": dep.name,
                        "kind": dep.kind,
                        "ref": dep.ref_tag,
                        "commit": dep.commit,
                        "installed": dep.installed.first().map(|row| row.version.clone()),
                        "drift": dep.drift,
                        "in_effect": dep.in_effect,
                        "label": gitmove_core::deps::label(dep),
                    })
                })
                .collect();
            Ok(success("gitmove_dep_list", payload))
        }
        Command::Asset { action } => match action {
            AssetAction::Init { target } => Ok(success(
                "gitmove_asset_init",
                gitmove_core::asset::init(root, target.as_deref())?,
            )),
            AssetAction::Status => Ok(success("gitmove_asset_status", gitmove_core::asset::status(root))),
            AssetAction::Backup { target } => {
                let outcome = gitmove_core::asset::backup(root, target.as_deref(), None)?;
                Ok(success("gitmove_asset_backup", outcome))
            }
            AssetAction::Snapshots { limit } => {
                Ok(success("gitmove_asset_snapshots", gitmove_core::asset::snapshots(root, *limit)?))
            }
            AssetAction::Check { target } => {
                Ok(success("gitmove_asset_check", gitmove_core::asset::check(root, target.as_deref())?))
            }
            AssetAction::Restore { snapshot, target } => Ok(success(
                "gitmove_asset_restore",
                gitmove_core::asset::restore(root, snapshot, target.as_deref())?,
            )),
        },
        Command::Index { action: IndexAction::Rebuild } => Ok(success(
            "gitmove_index_rebuild",
            serde_json::json!({ "revisions": gitmove_core::revision::rebuild(root)? }),
        )),
        Command::Mcp => unreachable!("mcp is handled before dispatch"),
    }
}

fn emit(json: bool, envelope: &Envelope<serde_json::Value>) {
    if json {
        println!("{}", envelope.to_json());
    } else if envelope.ok {
        let data = envelope.data.clone().unwrap_or(serde_json::Value::Null);
        println!("{}", serde_json::to_string_pretty(&data).unwrap_or_default());
    } else if let Some(error) = &envelope.error {
        eprintln!("{}: {}", error.code, error.message);
        for step in &error.steps {
            eprintln!("  - {step}");
        }
    }
}

fn failure(err: &CoreError) -> Envelope<serde_json::Value> {
    Envelope::failure("gitmove", err.code, &err.message, err.steps.clone())
}

/// Minimal but protocol-correct MCP server (newline-delimited JSON-RPC 2.0).
fn run_mcp(root: &Path) -> ExitCode {
    let stdin = std::io::stdin();
    let mut stdout = std::io::stdout();
    let allow_write = std::env::var("GITMOVE_MCP_ALLOW_WRITE").ok().as_deref() == Some("1");

    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let line = line.trim().to_string();
        if line.is_empty() {
            continue;
        }
        let Ok(request) = serde_json::from_str::<serde_json::Value>(&line) else {
            continue;
        };
        let id = request.get("id").cloned();
        let method = request.get("method").and_then(|value| value.as_str()).unwrap_or_default();
        let params = request.get("params").cloned().unwrap_or(serde_json::Value::Null);

        if method.starts_with("notifications/") {
            continue;
        }

        let result = match method {
            "initialize" => Ok(serde_json::json!({
                "protocolVersion": "2024-11-05",
                "capabilities": { "tools": {}, "resources": {}, "prompts": {} },
                "serverInfo": { "name": "gitmove", "version": env!("CARGO_PKG_VERSION") }
            })),
            "tools/list" => Ok(serde_json::json!({ "tools": mcp_tools() })),
            "tools/call" => mcp_call(root, &params, allow_write),
            "prompts/list" => Ok(serde_json::json!({ "prompts": [{
                "name": "gitmove_diagnose",
                "description": "Diagnose a workspace with gitmove tools (read-only)",
                "arguments": [{ "name": "workspace", "required": false }]
            }]})),
            "resources/list" => Ok(serde_json::json!({ "resources": [{
                "uri": "gitmove://workspace/status",
                "name": "workspace-status",
                "mimeType": "application/json"
            }]})),
            "resources/read" => Ok(serde_json::json!({ "contents": [{
                "uri": "gitmove://workspace/status",
                "mimeType": "application/json",
                "text": serde_json::to_string(&gitmove_core::asset::status(root)).unwrap_or_default()
            }]})),
            _ => Err((-32601, format!("method not found: {method}"))),
        };

        let payload = match result {
            Ok(value) => serde_json::json!({ "jsonrpc": "2.0", "id": id, "result": value }),
            Err((code, message)) => serde_json::json!({
                "jsonrpc": "2.0", "id": id,
                "error": { "code": code, "message": message }
            }),
        };
        if writeln!(stdout, "{payload}").is_err() {
            break;
        }
        let _ = stdout.flush();
    }
    ExitCode::SUCCESS
}

fn mcp_tools() -> Vec<serde_json::Value> {
    vec![
        serde_json::json!({
            "name": "gitmove_status",
            "description": "Workspace audit + member status (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_log",
            "description": "List revisions (read-only)",
            "inputSchema": { "type": "object", "properties": { "limit": { "type": "integer" } } }
        }),
        serde_json::json!({
            "name": "gitmove_asset_status",
            "description": "Backup targets and snapshots (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_ws_status",
            "description": "Multi-repo workspace members (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_commit",
            "description": "Create a revision (needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": {
                "type": "object",
                "properties": { "message": { "type": "string" }, "confirm": { "type": "boolean" } },
                "required": ["message"]
            }
        }),
    ]
}

fn mcp_text(value: serde_json::Value) -> serde_json::Value {
    serde_json::json!({ "content": [{ "type": "text", "text": value.to_string() }] })
}

fn mcp_call(root: &Path, params: &serde_json::Value, allow_write: bool) -> Result<serde_json::Value, (i32, String)> {
    let name = params.get("name").and_then(|value| value.as_str()).unwrap_or_default();
    let args = params.get("arguments").cloned().unwrap_or(serde_json::Value::Null);
    let result = match name {
        "gitmove_status" => gitmove_core::audit::audit_current(root)
            .and_then(|row| Ok(serde_json::json!({ "audit": row, "workspace": gitmove_core::workspace::status(root)? }))),
        "gitmove_log" => {
            let limit = args.get("limit").and_then(|value| value.as_u64()).unwrap_or(20) as u32;
            gitmove_core::revision::log(root, limit).map(|rows| serde_json::json!(rows))
        }
        "gitmove_asset_status" => Ok(serde_json::json!(gitmove_core::asset::status(root))),
        "gitmove_ws_status" => gitmove_core::workspace::status(root).map(|status| serde_json::json!(status)),
        "gitmove_commit" => {
            if !allow_write {
                return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
            }
            let confirm = args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false);
            if !confirm {
                return Err((-32000, "confirm=true is required for write tools".to_string()));
            }
            let message = args
                .get("message")
                .and_then(|value| value.as_str())
                .unwrap_or("gitmove commit")
                .to_string();
            gitmove_core::revision::commit(root, &message, false, false, false).map(|outcome| serde_json::json!(outcome))
        }
        other => return Err((-32602, format!("unknown tool: {other}"))),
    };
    result.map(mcp_text).map_err(|err| (-32000, err.message))
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let json = cli.json;
    let root = workspace(&cli.dir);

    if matches!(cli.command, Command::Mcp) {
        return run_mcp(&root);
    }

    match run(&cli, &root) {
        Ok(envelope) => {
            let partial = envelope
                .data
                .as_ref()
                .and_then(|data| data.get("partial"))
                .and_then(|value| value.as_bool())
                .unwrap_or(false);
            emit(json, &envelope);
            if partial {
                return ExitCode::from(2);
            }
            ExitCode::SUCCESS
        }
        Err(err) => {
            emit(json, &failure(&err));
            if matches!(err.code, "GIT_UNAVAILABLE" | "RESTIC_MISSING") {
                return ExitCode::from(2);
            }
            ExitCode::from(1)
        }
    }
}
