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
    /// Build and environment information.
    Info,
    /// Registered projects.
    Projects {
        #[command(subcommand)]
        action: ProjectsAction,
    },
    /// Workspace health and measurements.
    Audit {
        #[arg(long)]
        all: bool,
    },
    /// Revisions (commit / log / show / checkout).
    #[command(name = "rev")]
    Revision {
        #[command(subcommand)]
        action: RevAction,
    },
    /// Commit the workspace (git commit + revision row + trailer).
    Commit {
        #[arg(short = 'm', long)]
        message: String,
        /// Also commit dirty members (each with `[rev N]` suffix).
        #[arg(long)]
        members: bool,
        /// Disable the second-attempt escape hatch.
        #[arg(long)]
        strict: bool,
    },
    /// Restore the workspace to a revision.
    Checkout {
        id: i64,
        /// Discard uncommitted changes.
        #[arg(long)]
        force: bool,
    },
    /// Multi-repo workspace status.
    Ws {
        #[command(subcommand)]
        action: WsAction,
    },
    /// Index maintenance.
    Index {
        #[command(subcommand)]
        action: IndexAction,
    },
}

#[derive(Subcommand)]
enum ProjectsAction {
    List,
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
}

#[derive(Subcommand)]
enum IndexAction {
    Rebuild,
}

fn workspace(dir: &Option<PathBuf>) -> PathBuf {
    dir.clone().unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

fn emit(json: bool, envelope: Envelope<serde_json::Value>) {
    if json {
        println!("{}", envelope.to_json());
    } else if envelope.ok {
        let data = envelope.data.unwrap_or(serde_json::Value::Null);
        println!("{}", serde_json::to_string_pretty(&data).unwrap_or_default());
    } else if let Some(error) = &envelope.error {
        eprintln!("{}: {}", error.code, error.message);
        for step in &error.steps {
            eprintln!("  - {step}");
        }
    }
}

fn success(tool: &str, value: impl serde::Serialize) -> Envelope<serde_json::Value> {
    Envelope::success(tool, None, serde_json::to_value(value).unwrap_or(serde_json::Value::Null))
}

fn failure(err: &CoreError) -> Envelope<serde_json::Value> {
    Envelope::failure("gitmove", err.code, &err.message, err.steps.clone())
}

fn run(cli: Cli) -> Result<Envelope<serde_json::Value>, CoreError> {
    let root = workspace(&cli.dir);
    match cli.command {
        Command::Info => {
            let entries = gitmove_core::registry::load().unwrap_or_default();
            let info = serde_json::json!({
                "version": env!("CARGO_PKG_VERSION"),
                "core": "rust",
                "home": gitmove_core::paths::home_dir().to_string_lossy().replace('\\', "/"),
                "registry": gitmove_core::paths::registry_path().to_string_lossy().replace('\\', "/"),
                "projects": entries.len(),
                "workspace": root.to_string_lossy().replace('\\', "/"),
            });
            Ok(success("gitmove_info", info))
        }
        Command::Projects { action: ProjectsAction::List } => {
            let entries = gitmove_core::registry::load()?;
            let rows = gitmove_core::registry::to_rows(&entries);
            Ok(success("gitmove_list_projects", rows))
        }
        Command::Audit { all } => {
            let rows = if all {
                gitmove_core::audit::audit_all()?
            } else {
                vec![gitmove_core::audit::audit_current(&root)?]
            };
            Ok(success("gitmove_audit", rows))
        }
        Command::Revision { action: RevAction::Log { limit } } => {
            let revisions = gitmove_core::revision::log(&root, limit)?;
            Ok(success("gitmove_rev_log", revisions))
        }
        Command::Revision { action: RevAction::Show { id } } => {
            let revision = gitmove_core::revision::show(&root, id)?;
            Ok(success("gitmove_rev_show", revision))
        }
        Command::Commit { message, members, strict } => {
            let outcome = gitmove_core::revision::commit(&root, &message, members, strict)?;
            Ok(success("gitmove_commit", outcome))
        }
        Command::Checkout { id, force } => {
            let outcome = gitmove_core::revision::checkout(&root, id, force)?;
            Ok(success("gitmove_checkout", outcome))
        }
        Command::Ws { action: WsAction::Status } => {
            let status = gitmove_core::workspace::status(&root)?;
            Ok(success("gitmove_ws_status", status))
        }
        Command::Index { action: IndexAction::Rebuild } => {
            let count = gitmove_core::revision::rebuild(&root)?;
            Ok(success("gitmove_index_rebuild", serde_json::json!({ "revisions": count })))
        }
    }
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let json = cli.json;
    let dir = cli.dir.clone();
    let root: &Path = &workspace(&dir);
    match run(cli) {
        Ok(envelope) => {
            emit(json, envelope);
            ExitCode::SUCCESS
        }
        Err(err) => {
            emit(json, failure(&err));
            if err.code == "GIT_UNAVAILABLE" {
                return ExitCode::from(2);
            }
            let _ = root;
            ExitCode::from(1)
        }
    }
}
