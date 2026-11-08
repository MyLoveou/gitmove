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
        /// Commit only these files (member:path or path; repeatable).
        #[arg(long = "path")]
        paths: Vec<String>,
    },
    Checkout {
        id: i64,
        #[arg(long)]
        force: bool,
    },
    Files {
        sha: String,
        #[arg(long)]
        member: Option<String>,
    },
    SnapshotDiff {
        a: String,
        b: String,
        #[arg(long)]
        target: Option<String>,
    },
    Doctor,
    Diff {
        path: String,
        #[arg(long)]
        member: Option<String>,
        #[arg(long)]
        commit: Option<String>,
    },
    Render {
        #[arg(long)]
        spec_root: String,
        #[arg(long)]
        project: String,
        #[arg(long)]
        target: Option<String>,
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        force: bool,
    },
    Hook {
        #[command(subcommand)]
        action: HookAction,
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
    /// Policy: skip-worktree / links / worktrees.
    #[command(name = "policy")]
    PolicyCmd {
        #[command(subcommand)]
        action: PolicyAction,
    },
    /// Working-tree changes (main + members).
    Changes,
    /// Discard selected changes (member:path or path).
    Discard {
        #[arg(long = "path")]
        paths: Vec<String>,
    },
    /// Commit graph (git log --graph).
    Graph {
        #[arg(long, default_value_t = 200)]
        limit: u32,
        #[arg(long)]
        branch: Option<String>,
        #[arg(long)]
        all: bool,
        #[arg(long)]
        text: bool,
    },
    /// Sync check / fast-forward pull.
    Sync {
        #[command(subcommand)]
        action: SyncAction,
    },
    /// Exclude presets.
    Exclude {
        #[command(subcommand)]
        action: ExcludeAction,
    },
    /// Vendor helpers.
    Vendor {
        #[command(subcommand)]
        action: VendorAction,
    },
    /// Configuration export/import.
    Config {
        #[command(subcommand)]
        action: ConfigAction,
    },
    /// MCP server over stdio (JSON-RPC 2.0).
    Mcp,
}

#[derive(Subcommand)]
enum ProjectsAction {
    List,
    Info,
    Add {
        path: String,
        #[arg(long)]
        alias: Option<String>,
        #[arg(long, default_value = "")]
        group: String,
        #[arg(long, default_value = "")]
        notes: String,
    },
    Remove {
        target: String,
    },
    Scan {
        root: String,
        #[arg(long, default_value_t = 2)]
        depth: u32,
        #[arg(long)]
        register: bool,
    },
}

#[derive(Subcommand)]
enum RevAction {
    #[command(name = "import-git")]
    ImportGit {
        #[arg(long, default_value_t = 200)]
        limit: u32,
    },
    Log {
        #[arg(long, default_value_t = 20)]
        limit: u32,
    },
    Show {
        id: i64,
    },
}

#[derive(Subcommand)]
enum HookAction {
    Status,
    Install {
        #[arg(long = "event")]
        events: Vec<String>,
        #[arg(long)]
        members: bool,
    },
    Uninstall {
        #[arg(long = "event")]
        events: Vec<String>,
        #[arg(long)]
        members: bool,
    },
    Run {
        event: String,
        #[arg(long)]
        no_block: bool,
    },
    Add {
        #[arg(long)]
        event: String,
        #[arg(long)]
        command: String,
        #[arg(long)]
        advisory: bool,
        #[arg(long)]
        global: bool,
    },
    Remove {
        #[arg(long)]
        event: String,
        #[arg(long)]
        command: String,
        #[arg(long)]
        global: bool,
    },
    Enable {
        #[arg(long)]
        event: String,
        #[arg(long)]
        command: String,
        #[arg(long)]
        global: bool,
    },
    Disable {
        #[arg(long)]
        event: String,
        #[arg(long)]
        command: String,
        #[arg(long)]
        global: bool,
    },
}

#[derive(Subcommand)]
enum WsAction {
    Status,
    #[command(name = "branch-list")]
    BranchList,
    #[command(name = "branch-create")]
    BranchCreate {
        name: String,
        /// Limit the new branch to one member. Omitted: every member.
        #[arg(long)]
        member: Option<String>,
    },
    #[command(name = "branch-switch")]
    BranchSwitch {
        name: String,
        /// Limit the checkout to one member. Omitted: every member.
        #[arg(long)]
        member: Option<String>,
    },
    /// Local branch names of one member.
    #[command(name = "branch-refs")]
    BranchRefs { member: String },
    /// Commit one member without creating a workspace revision.
    #[command(name = "member-commit")]
    MemberCommit {
        member: String,
        #[arg(short, long)]
        message: String,
    },
    Merge { branch: String },
    Refs,
    Add {
        name: String,
        #[arg(long)]
        path: String,
        #[arg(long, default_value = "editable")]
        role: String,
        #[arg(long, default_value = "vendor")]
        strategy: String,
        #[arg(long, default_value = "")]
        source: String,
        #[arg(long, default_value = "")]
        pin: String,
        #[arg(long, default_value = "")]
        track: String,
    },
    Sync {
        #[arg(long)]
        member: Option<String>,
    },
    Update {
        #[arg(long)]
        member: Option<String>,
        #[arg(long)]
        to: Option<String>,
    },
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
    Ls {
        snapshot: String,
        #[arg(long)]
        target: Option<String>,
    },
    Merge {
        #[arg(long)]
        base: String,
        #[arg(long)]
        ours: String,
        #[arg(long)]
        theirs: String,
        #[arg(long)]
        target: Option<String>,
        #[arg(long)]
        apply: bool,
        #[arg(long)]
        force: bool,
    },
    Status,
    Test {
        #[arg(long)]
        target: Option<String>,
    },
    Resolve {
        path: String,
        #[arg(long, default_value = "ours")]
        take: String,
    },
    Continue,
    State,
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
    Prune {
        #[arg(long)]
        keep_daily: Option<u32>,
        #[arg(long)]
        keep_weekly: Option<u32>,
        #[arg(long)]
        keep_monthly: Option<u32>,
        #[arg(long)]
        keep_last: Option<u32>,
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        target: Option<String>,
    },
    Guard,
    Restore {
        snapshot: String,
        #[arg(long)]
        target: Option<String>,
        #[arg(long = "path")]
        paths: Vec<String>,
        #[arg(long)]
        to: Option<String>,
    },
    Files {
        snapshot: String,
        #[arg(long)]
        target: Option<String>,
    },
}

#[derive(Subcommand)]
enum PolicyAction {
    Apply,
    Skip {
        #[command(subcommand)]
        action: SkipAction,
    },
    Link {
        #[command(subcommand)]
        action: LinkAction,
    },
    Worktree {
        #[command(subcommand)]
        action: WorktreeAction,
    },
}

#[derive(Subcommand)]
enum SkipAction {
    Add { paths: Vec<String> },
    Remove { paths: Vec<String> },
    List,
}

#[derive(Subcommand)]
enum LinkAction {
    Add {
        path: String,
        #[arg(long)]
        external: String,
        #[arg(long, default_value = "junction")]
        kind: String,
        #[arg(long)]
        migrate: bool,
    },
    List,
    Remove { path: String },
}

#[derive(Subcommand)]
enum WorktreeAction {
    Add {
        path: String,
        #[arg(long)]
        branch: String,
    },
    List,
    Remove { path: String },
}

#[derive(Subcommand)]
enum SyncAction {
    Check,
    Pull {
        #[arg(long)]
        fetch: bool,
        #[arg(long)]
        merge: bool,
        #[arg(long)]
        rebase: bool,
    },
}

#[derive(Subcommand)]
enum ExcludeAction {
    #[command(name = "preset-list")]
    PresetList,
    #[command(name = "preset-enable")]
    PresetEnable { name: String },
    #[command(name = "preset-disable")]
    PresetDisable { name: String },
}

#[derive(Subcommand)]
enum VendorAction {
    #[command(name = "template-list")]
    TemplateList,
}

#[derive(Subcommand)]
enum ConfigAction {
    Export {
        #[arg(long)]
        out: Option<String>,
    },
    Import { path: String },
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
            ProjectsAction::List => Ok(success("gitmove_list_projects", gitmove_core::registry::load()?)),
            ProjectsAction::Info => Ok(success("gitmove_project_info", gitmove_core::registry::load()?)),
            ProjectsAction::Add { path, alias, group, notes } => Ok(success(
                "gitmove_projects_add",
                gitmove_core::registry::add(path, alias.as_deref(), group, notes)?,
            )),
            ProjectsAction::Remove { target } => Ok(success(
                "gitmove_projects_remove",
                serde_json::json!({ "removed": gitmove_core::registry::remove(target)? }),
            )),
            ProjectsAction::Scan { root, depth, register } => {
                let rows = gitmove_core::registry::scan(root, *depth)?;
                if *register {
                    for row in &rows {
                        if !row.registered {
                            let _ = gitmove_core::registry::add(&row.path, Some(&row.alias), "", "");
                        }
                    }
                }
                Ok(success("gitmove_projects_scan", rows))
            }
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
            RevAction::ImportGit { limit } => Ok(success(
                "gitmove_rev_import",
                serde_json::json!({ "imported": gitmove_core::revision::import_git(root, *limit)? }),
            )),
            RevAction::Log { limit } => Ok(success("gitmove_rev_log", gitmove_core::revision::log(root, *limit)?)),
            RevAction::Show { id } => Ok(success("gitmove_rev_show", gitmove_core::revision::show(root, *id)?)),
        },
        Command::Commit { message, members, strict, assets, paths } => {
            if paths.is_empty() {
                let outcome = gitmove_core::revision::commit(root, message, *members, *strict, *assets)?;
                Ok(success("gitmove_commit", outcome))
            } else {
                let mut main_paths = Vec::new();
                let mut member_map: std::collections::BTreeMap<String, Vec<String>> = Default::default();
                for item in paths {
                    match item.split_once(':') {
                        Some((member, path)) => member_map.entry(member.to_string()).or_default().push(path.to_string()),
                        None => main_paths.push(item.clone()),
                    }
                }
                let outcome = gitmove_core::revision::commit_paths(root, message, &main_paths, &member_map)?;
                Ok(success("gitmove_commit", outcome))
            }
        }
        Command::Changes => Ok(success("gitmove_changes", gitmove_core::changes::status(root)?)),
        Command::Discard { paths } => {
            let selections: Vec<(String, String)> = paths
                .iter()
                .map(|item| match item.split_once(':') {
                    Some((member, path)) => (member.to_string(), path.to_string()),
                    None => ("main".to_string(), item.clone()),
                })
                .collect();
            Ok(success("gitmove_discard", gitmove_core::changes::discard(root, &selections)?))
        }
        Command::Checkout { id, force } => Ok(success(
            "gitmove_checkout",
            gitmove_core::revision::checkout(root, *id, *force)?,
        )),
        Command::Files { sha, member } => Ok(success(
            "gitmove_commit_files",
            gitmove_core::revision::commit_files(root, member.as_deref(), sha)?,
        )),
        Command::SnapshotDiff { a, b, target } => Ok(success(
            "gitmove_asset_diff",
            gitmove_core::asset::diff_snapshots(root, target.as_deref(), a, b)?,
        )),
        Command::Doctor => Ok(success("gitmove_doctor", gitmove_core::doctor::run(root)?)),
        Command::Diff { path, member, commit } => {
            let payload = match commit {
                Some(sha) => gitmove_core::diff::commit_diff(root, member.as_deref(), sha, path)?,
                None => gitmove_core::diff::working(root, member.as_deref(), path)?,
            };
            Ok(success("gitmove_diff", payload))
        }
        Command::Render { spec_root, project, target, dry_run, force } => {
            let target_path = target.clone().map(std::path::PathBuf::from).unwrap_or_else(|| root.to_path_buf());
            Ok(success(
                "gitmove_render",
                gitmove_core::spec::render(
                    std::path::Path::new(spec_root),
                    project,
                    &target_path,
                    *force,
                    *dry_run,
                )?,
            ))
        }
        Command::Hook { action } => match action {
            HookAction::Status => Ok(success("gitmove_hook_status", gitmove_core::hooks::status(root)?)),
            HookAction::Install { events, members } => Ok(success(
                "gitmove_hook_install",
                gitmove_core::hooks::install(root, events, *members)?,
            )),
            HookAction::Uninstall { events, members } => Ok(success(
                "gitmove_hook_uninstall",
                gitmove_core::hooks::uninstall(root, events, *members)?,
            )),
            HookAction::Run { event, no_block } => {
                let results = if *no_block {
                    gitmove_core::hooks::run_advisory(root, event)?
                } else {
                    gitmove_core::hooks::run(root, event)?
                };
                Ok(success("gitmove_hook_run", results))
            }
            HookAction::Add { event, command, advisory, global } => {
                gitmove_core::hooks::add(root, event, command, !*advisory, *global)?;
                Ok(success("gitmove_hook_add", gitmove_core::hooks::status(root)?))
            }
            HookAction::Remove { event, command, global } => {
                gitmove_core::hooks::remove(root, event, command, *global)?;
                Ok(success("gitmove_hook_remove", gitmove_core::hooks::status(root)?))
            }
            HookAction::Enable { event, command, global } => {
                gitmove_core::hooks::set_enabled(root, event, command, true, *global)?;
                Ok(success("gitmove_hook_enable", gitmove_core::hooks::status(root)?))
            }
            HookAction::Disable { event, command, global } => {
                gitmove_core::hooks::set_enabled(root, event, command, false, *global)?;
                Ok(success("gitmove_hook_disable", gitmove_core::hooks::status(root)?))
            }
        },
        Command::Workspace { action } => match action {
            WsAction::Status => Ok(success("gitmove_ws_status", gitmove_core::workspace::status(root)?)),
            WsAction::BranchList => Ok(success("gitmove_ws_branch_list", gitmove_core::workspace::branch_list(root)?)),
            WsAction::BranchCreate { name, member } => Ok(success(
                "gitmove_ws_branch_create",
                gitmove_core::workspace::branch_create(root, name, member.as_deref())?,
            )),
            WsAction::BranchSwitch { name, member } => Ok(success(
                "gitmove_ws_branch_switch",
                gitmove_core::workspace::branch_switch(root, name, member.as_deref())?,
            )),
            WsAction::BranchRefs { member } => Ok(success(
                "gitmove_ws_branch_refs",
                gitmove_core::workspace::member_branches(root, member)?,
            )),
            WsAction::MemberCommit { member, message } => Ok(success(
                "gitmove_ws_member_commit",
                gitmove_core::workspace::member_commit(root, member, message)?,
            )),
            WsAction::Merge { branch } => {
                Ok(success("gitmove_ws_merge", gitmove_core::workspace::merge(root, branch)?))
            }
            WsAction::Refs => Ok(success("gitmove_ws_refs", gitmove_core::workspace::refs(root)?)),
            WsAction::Add { name, path, role, strategy, source, pin, track } => Ok(success(
                "gitmove_ws_add",
                gitmove_core::workspace::add_member(root, name, path, role, strategy, source, pin, track)?,
            )),
            WsAction::Sync { member } => Ok(success(
                "gitmove_ws_sync",
                gitmove_core::workspace::sync(root, member.as_deref())?,
            )),
            WsAction::Update { member, to } => Ok(success(
                "gitmove_ws_update",
                gitmove_core::workspace::update(root, member.as_deref(), to.as_deref())?,
            )),
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
            AssetAction::Ls { snapshot, target } => {
                let name = target.clone().unwrap_or_else(|| {
                    gitmove_core::asset::load_targets(root)
                        .first()
                        .map(|item| item.name.clone())
                        .unwrap_or_default()
                });
                Ok(success(
                    "gitmove_asset_ls",
                    gitmove_core::merge::list_files(root, &name, snapshot)?,
                ))
            }
            AssetAction::Merge { base, ours, theirs, target, apply, force } => {
                let name = target.clone().unwrap_or_else(|| {
                    gitmove_core::asset::load_targets(root)
                        .first()
                        .map(|item| item.name.clone())
                        .unwrap_or_default()
                });
                let plan = gitmove_core::merge::plan(root, &name, base, ours, theirs)?;
                if *apply {
                    Ok(success(
                        "gitmove_asset_merge",
                        gitmove_core::merge::apply(root, &name, &plan, *force)?,
                    ))
                } else {
                    Ok(success("gitmove_asset_merge_plan", plan))
                }
            }
            AssetAction::Prune { keep_daily, keep_weekly, keep_monthly, keep_last, dry_run, target } => Ok(success(
                "gitmove_asset_prune",
                gitmove_core::asset::prune(root, *keep_daily, *keep_weekly, *keep_monthly, *keep_last, *dry_run, target.as_deref())?,
            )),
            AssetAction::Guard => Ok(success("gitmove_asset_guard", gitmove_core::asset::guard(root)?)),
            AssetAction::Test { target } => Ok(success(
                "gitmove_asset_test",
                gitmove_core::asset::test_targets(root, target.as_deref())?,
            )),
            AssetAction::Resolve { path, take } => Ok(success(
                "gitmove_asset_resolve",
                gitmove_core::merge::resolve(root, path, take)?,
            )),
            AssetAction::Continue => Ok(success(
                "gitmove_asset_continue",
                gitmove_core::merge::finish_merge(root)?,
            )),
            AssetAction::State => Ok(success(
                "gitmove_asset_state",
                gitmove_core::merge::read_state(root),
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
            AssetAction::Restore { snapshot, target, paths, to } => Ok(success(
                "gitmove_asset_restore",
                gitmove_core::asset::restore_paths(
                    root,
                    snapshot,
                    target.as_deref(),
                    paths,
                    to.as_ref().map(std::path::Path::new),
                )?,
            )),
            AssetAction::Files { snapshot, target } => {
                let name = target
                    .clone()
                    .or_else(|| gitmove_core::asset::load_targets(root).first().map(|item| item.name.clone()))
                    .unwrap_or_default();
                Ok(success(
                    "gitmove_asset_files",
                    gitmove_core::merge::list_files(root, &name, snapshot)?,
                ))
            }
        },
        Command::Graph { limit, branch, all, text } => {
            if *text {
                let branch = if *all { None } else { branch.clone() };
                Ok(success("gitmove_graph", gitmove_core::misc::graph(root, *limit, branch.as_deref())?))
            } else {
                Ok(success(
                    "gitmove_graph",
                    gitmove_core::misc::graph_nodes(root, *limit, branch.as_deref(), *all)?,
                ))
            }
        }
        Command::Sync { action } => match action {
            SyncAction::Check => Ok(success("gitmove_sync_check", gitmove_core::misc::check(root)?)),
            SyncAction::Pull { fetch, merge, rebase } => {
                let mode = if *merge { Some("merge") } else if *rebase { Some("rebase") } else { None };
                Ok(success("gitmove_sync_pull", gitmove_core::misc::pull(root, *fetch, mode)?))
            }
        },
        Command::Exclude { action } => match action {
            ExcludeAction::PresetList => Ok(success(
                "gitmove_exclude_presets",
                serde_json::json!({
                    "presets": gitmove_core::misc::presets(),
                    "active": gitmove_core::misc::preset_active(root)
                }),
            )),
            ExcludeAction::PresetEnable { name } => Ok(success(
                "gitmove_exclude_enable",
                gitmove_core::misc::preset_enable(root, name)?,
            )),
            ExcludeAction::PresetDisable { name } => Ok(success(
                "gitmove_exclude_disable",
                gitmove_core::misc::preset_disable(root, name)?,
            )),
        },
        Command::Vendor { action } => match action {
            VendorAction::TemplateList => Ok(success(
                "gitmove_vendor_templates",
                gitmove_core::misc::vendor_templates(),
            )),
        },
        Command::Config { action } => match action {
            ConfigAction::Export { out } => {
                let text = gitmove_core::config::export(root)?;
                match out {
                    Some(path) => {
                        std::fs::write(path, &text)?;
                        Ok(success("gitmove_config_export", serde_json::json!({ "path": path })))
                    }
                    None => Ok(success("gitmove_config_export", serde_json::json!({ "toml": text }))),
                }
            }
            ConfigAction::Import { path } => Ok(success(
                "gitmove_config_import",
                gitmove_core::config::import(root, std::path::Path::new(path))?,
            )),
        },
        Command::PolicyCmd { action } => match action {
            PolicyAction::Apply => Ok(success("gitmove_policy_apply", gitmove_core::policy::apply(root)?)),
            PolicyAction::Skip { action } => match action {
                SkipAction::Add { paths } => Ok(success("gitmove_skip_add", gitmove_core::policy::skip_add(root, paths)?)),
                SkipAction::Remove { paths } => {
                    Ok(success("gitmove_skip_remove", gitmove_core::policy::skip_remove(root, paths)?))
                }
                SkipAction::List => Ok(success("gitmove_skip_list", gitmove_core::policy::skip_list(root)?)),
            },
            PolicyAction::Link { action } => match action {
                LinkAction::Add { path, external, kind, migrate } => Ok(success(
                    "gitmove_link_add",
                    gitmove_core::policy::link_add(root, path, external, kind, *migrate)?,
                )),
                LinkAction::List => Ok(success("gitmove_link_list", gitmove_core::policy::link_list(root))),
                LinkAction::Remove { path } => {
                    Ok(success("gitmove_link_remove", gitmove_core::policy::link_remove(root, path)?))
                }
            },
            PolicyAction::Worktree { action } => match action {
                WorktreeAction::Add { path, branch } => Ok(success(
                    "gitmove_worktree_add",
                    gitmove_core::policy::worktree_add(root, path, branch)?,
                )),
                WorktreeAction::List => Ok(success("gitmove_worktree_list", gitmove_core::policy::worktree_list(root)?)),
                WorktreeAction::Remove { path } => Ok(success(
                    "gitmove_worktree_remove",
                    gitmove_core::policy::worktree_remove(root, path)?,
                )),
            },
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
            "name": "gitmove_dep_list",
            "description": "Declared dependencies with drift/in-effect flags (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_asset_backup",
            "description": "Back up every asset target (needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": {
                "type": "object",
                "properties": { "confirm": { "type": "boolean" } }
            }
        }),
        serde_json::json!({
            "name": "gitmove_rev_show",
            "description": "Show one revision with member commits (read-only)",
            "inputSchema": { "type": "object", "properties": { "id": { "type": "integer" } }, "required": ["id"] }
        }),
        serde_json::json!({
            "name": "gitmove_changes",
            "description": "Working-tree changes for the workspace and members (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_checkout",
            "description": "Restore a revision (needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": {
                "type": "object",
                "properties": { "id": { "type": "integer" }, "force": { "type": "boolean" }, "confirm": { "type": "boolean" } },
                "required": ["id"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_ws_diff",
            "description": "Preview a member's contribution (read-only)",
            "inputSchema": { "type": "object", "properties": { "member": { "type": "string" } }, "required": ["member"] }
        }),
        serde_json::json!({
            "name": "gitmove_ws_contribute",
            "description": "Push a member's changes upstream (needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": {
                "type": "object",
                "properties": { "member": { "type": "string" }, "no_push": { "type": "boolean" }, "confirm": { "type": "boolean" } },
                "required": ["member"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_asset_merge",
            "description": "Three-way asset merge plan, or apply it (needs confirm=true to apply)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "base": { "type": "string" }, "ours": { "type": "string" }, "theirs": { "type": "string" },
                    "target": { "type": "string" }, "apply": { "type": "boolean" }, "force": { "type": "boolean" },
                    "confirm": { "type": "boolean" }
                },
                "required": ["base", "ours", "theirs"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_sync_check",
            "description": "Ahead/behind/upstream for the workspace (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_config_export",
            "description": "Export workspace policy and backup targets as TOML (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_ws_sync",
            "description": "Check out workspace.lock.toml pins (write; needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": { "type": "object", "properties": { "member": { "type": "string" }, "confirm": { "type": "boolean" } } }
        }),
        serde_json::json!({
            "name": "gitmove_ws_update",
            "description": "Fetch and advance lock pins (write; needs confirm=true and GITMOVE_MCP_ALLOW_WRITE=1)",
            "inputSchema": {
                "type": "object",
                "properties": { "member": { "type": "string" }, "to": { "type": "string" }, "confirm": { "type": "boolean" } }
            }
        }),
        serde_json::json!({
            "name": "gitmove_ws_add",
            "description": "Add a workspace member: vendor/clone/link (write; needs confirm=true)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": { "type": "string" }, "path": { "type": "string" },
                    "role": { "type": "string" }, "strategy": { "type": "string" },
                    "source": { "type": "string" }, "pin": { "type": "string" },
                    "track": { "type": "string" }, "confirm": { "type": "boolean" }
                },
                "required": ["name", "path"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_discard",
            "description": "Discard selected changes (write; needs confirm=true)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "paths": { "type": "array", "items": { "type": "string" } },
                    "confirm": { "type": "boolean" }
                },
                "required": ["paths"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_asset_test",
            "description": "Test backup target reachability/credentials (read-only)",
            "inputSchema": { "type": "object", "properties": { "target": { "type": "string" } } }
        }),
        serde_json::json!({
            "name": "gitmove_asset_resolve",
            "description": "Resolve one asset conflict: ours/theirs/both (write; needs confirm=true)",
            "inputSchema": {
                "type": "object",
                "properties": { "path": { "type": "string" }, "take": { "type": "string" }, "confirm": { "type": "boolean" } },
                "required": ["path", "take"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_asset_continue",
            "description": "Finish an asset merge once conflicts are resolved (write; needs confirm=true)",
            "inputSchema": { "type": "object", "properties": { "confirm": { "type": "boolean" } } }
        }),
        serde_json::json!({
            "name": "gitmove_graph",
            "description": "Structured commit graph (read-only)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": { "type": "integer" }, "branch": { "type": "string" }, "all": { "type": "boolean" }
                }
            }
        }),
        serde_json::json!({
            "name": "gitmove_hook_status",
            "description": "Hook definitions and install matrix (read-only)",
            "inputSchema": { "type": "object", "properties": {} }
        }),
        serde_json::json!({
            "name": "gitmove_hook_install",
            "description": "Install git hooks for selected events (write; needs confirm=true)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "events": { "type": "array", "items": { "type": "string" } },
                    "members": { "type": "boolean" }, "confirm": { "type": "boolean" }
                }
            }
        }),
        serde_json::json!({
            "name": "gitmove_hook_run",
            "description": "Run hooks for an event (executes commands; needs confirm=true)",
            "inputSchema": {
                "type": "object",
                "properties": { "event": { "type": "string" }, "confirm": { "type": "boolean" } },
                "required": ["event"]
            }
        }),
        serde_json::json!({
            "name": "gitmove_doctor",
            "description": "Workspace health checks: members, lock drift, backup targets, guard, hooks, merge state",
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

fn confirm_required(allow_write: bool, args: &serde_json::Value) -> Result<(), (i32, String)> {
    if !allow_write {
        return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
    }
    if !args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false) {
        return Err((-32000, "confirm=true is required for write tools".to_string()));
    }
    Ok(())
}

fn arg_str<'a>(args: &'a serde_json::Value, key: &str) -> &'a str {
    args.get(key).and_then(|value| value.as_str()).unwrap_or_default()
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
        "gitmove_dep_list" => gitmove_core::deps::list(root).map(|rows| serde_json::json!(rows)),
        "gitmove_asset_backup" => {
            if !allow_write {
                return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
            }
            let confirm = args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false);
            if !confirm {
                return Err((-32000, "confirm=true is required for write tools".to_string()));
            }
            gitmove_core::asset::backup(root, None, None).map(|outcome| serde_json::json!(outcome))
        }
        "gitmove_rev_show" => {
            let id = args.get("id").and_then(|value| value.as_i64()).unwrap_or(0);
            gitmove_core::revision::show(root, id).map(|row| serde_json::json!(row))
        }
        "gitmove_changes" => gitmove_core::changes::status(root).map(|rows| serde_json::json!(rows)),
        "gitmove_checkout" => {
            if !allow_write {
                return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
            }
            let confirm = args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false);
            if !confirm {
                return Err((-32000, "confirm=true is required for write tools".to_string()));
            }
            let id = args.get("id").and_then(|value| value.as_i64()).unwrap_or(0);
            let force = args.get("force").and_then(|value| value.as_bool()).unwrap_or(false);
            gitmove_core::revision::checkout(root, id, force).map(|row| serde_json::json!(row))
        }
        "gitmove_ws_diff" => {
            let member = args.get("member").and_then(|value| value.as_str()).unwrap_or_default();
            gitmove_core::contribute::diff(root, member).map(|row| serde_json::json!(row))
        }
        "gitmove_ws_contribute" => {
            if !allow_write {
                return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
            }
            let confirm = args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false);
            if !confirm {
                return Err((-32000, "confirm=true is required for write tools".to_string()));
            }
            let member = args.get("member").and_then(|value| value.as_str()).unwrap_or_default();
            let no_push = args.get("no_push").and_then(|value| value.as_bool()).unwrap_or(false);
            gitmove_core::contribute::contribute(root, member, None, no_push).map(|row| serde_json::json!(row))
        }
        "gitmove_asset_merge" => {
            let base = args.get("base").and_then(|value| value.as_str()).unwrap_or_default();
            let ours = args.get("ours").and_then(|value| value.as_str()).unwrap_or_default();
            let theirs = args.get("theirs").and_then(|value| value.as_str()).unwrap_or_default();
            let target = args.get("target").and_then(|value| value.as_str());
            let name = target.map(str::to_string).unwrap_or_else(|| {
                gitmove_core::asset::load_targets(root).first().map(|item| item.name.clone()).unwrap_or_default()
            });
            let plan = match gitmove_core::merge::plan(root, &name, base, ours, theirs) {
                Ok(plan) => plan,
                Err(err) => return Err((-32000, err.message)),
            };
            let apply = args.get("apply").and_then(|value| value.as_bool()).unwrap_or(false);
            if apply {
                if !allow_write {
                    return Err((-32000, "MCP write disabled: set GITMOVE_MCP_ALLOW_WRITE=1".to_string()));
                }
                let confirm = args.get("confirm").and_then(|value| value.as_bool()).unwrap_or(false);
                if !confirm {
                    return Err((-32000, "confirm=true is required for write tools".to_string()));
                }
                let force = args.get("force").and_then(|value| value.as_bool()).unwrap_or(false);
                gitmove_core::merge::apply(root, &name, &plan, force).map(|row| serde_json::json!(row))
            } else {
                Ok(serde_json::json!(plan))
            }
        }
        "gitmove_sync_check" => gitmove_core::misc::check(root).map(|row| serde_json::json!(row)),
        "gitmove_config_export" => {
            gitmove_core::config::export(root).map(|text| serde_json::json!({ "toml": text }))
        }
        "gitmove_ws_sync" => {
            confirm_required(allow_write, &args)?;
            let member = args.get("member").and_then(|value| value.as_str());
            gitmove_core::workspace::sync(root, member).map(|rows| serde_json::json!(rows))
        }
        "gitmove_ws_update" => {
            confirm_required(allow_write, &args)?;
            let member = args.get("member").and_then(|value| value.as_str());
            let to = args.get("to").and_then(|value| value.as_str());
            gitmove_core::workspace::update(root, member, to).map(|rows| serde_json::json!(rows))
        }
        "gitmove_ws_add" => {
            confirm_required(allow_write, &args)?;
            gitmove_core::workspace::add_member(
                root,
                arg_str(&args, "name"),
                arg_str(&args, "path"),
                if arg_str(&args, "role").is_empty() { "editable" } else { arg_str(&args, "role") },
                if arg_str(&args, "strategy").is_empty() { "vendor" } else { arg_str(&args, "strategy") },
                arg_str(&args, "source"),
                arg_str(&args, "pin"),
                arg_str(&args, "track"),
            )
            .map(|row| serde_json::json!(row))
        }
        "gitmove_discard" => {
            confirm_required(allow_write, &args)?;
            let paths: Vec<(String, String)> = args
                .get("paths")
                .and_then(|value| value.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|item| item.as_str())
                        .map(|item| match item.split_once(':') {
                            Some((member, path)) => (member.to_string(), path.to_string()),
                            None => ("main".to_string(), item.to_string()),
                        })
                        .collect()
                })
                .unwrap_or_default();
            gitmove_core::changes::discard(root, &paths).map(|rows| serde_json::json!(rows))
        }
        "gitmove_asset_test" => {
            let target = args.get("target").and_then(|value| value.as_str());
            gitmove_core::asset::test_targets(root, target).map(|rows| serde_json::json!(rows))
        }
        "gitmove_asset_resolve" => {
            confirm_required(allow_write, &args)?;
            gitmove_core::merge::resolve(root, arg_str(&args, "path"), arg_str(&args, "take"))
                .map(|state| serde_json::json!(state))
        }
        "gitmove_asset_continue" => {
            confirm_required(allow_write, &args)?;
            gitmove_core::merge::finish_merge(root).map(|state| serde_json::json!(state))
        }
        "gitmove_graph" => {
            let limit = args.get("limit").and_then(|value| value.as_u64()).unwrap_or(100) as u32;
            let branch = args.get("branch").and_then(|value| value.as_str());
            let all = args.get("all").and_then(|value| value.as_bool()).unwrap_or(false);
            gitmove_core::misc::graph_nodes(root, limit, branch, all).map(|rows| serde_json::json!(rows))
        }
        "gitmove_hook_status" => gitmove_core::hooks::status(root).map(|row| serde_json::json!(row)),
        "gitmove_hook_install" => {
            confirm_required(allow_write, &args)?;
            let events: Vec<String> = args
                .get("events")
                .and_then(|value| value.as_array())
                .map(|items| items.iter().filter_map(|item| item.as_str().map(str::to_string)).collect())
                .unwrap_or_default();
            let members = args.get("members").and_then(|value| value.as_bool()).unwrap_or(false);
            gitmove_core::hooks::install(root, &events, members).map(|row| serde_json::json!(row))
        }
        "gitmove_hook_run" => {
            confirm_required(allow_write, &args)?;
            gitmove_core::hooks::run(root, arg_str(&args, "event")).map(|rows| serde_json::json!(rows))
        }
        "gitmove_doctor" => gitmove_core::doctor::run(root).map(|rows| serde_json::json!(rows)),
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
