use std::path::{Path, PathBuf};
use std::process::Command;

use chrono::Utc;
use rusqlite::params;
use serde::{Deserialize, Serialize};

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::paths;

#[derive(Debug, Clone, Deserialize)]
struct WorkspaceFile {
    #[serde(default)]
    backup: BackupSection,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct BackupSection {
    #[serde(default)]
    target: Vec<TargetDef>,
}

#[derive(Debug, Clone, Deserialize)]
struct TargetDef {
    #[serde(default)]
    name: String,
    #[serde(default = "default_kind")]
    kind: String,
    #[serde(default)]
    repo: String,
    #[serde(default)]
    password_env: String,
    #[serde(default)]
    password_file: String,
    #[serde(default = "default_priority")]
    priority: u32,
    #[serde(default = "default_enabled")]
    enabled: bool,
}

fn default_kind() -> String {
    "local".to_string()
}
fn default_priority() -> u32 {
    10
}
fn default_enabled() -> bool {
    true
}

#[derive(Debug, Clone, Serialize)]
pub struct Target {
    pub name: String,
    pub kind: String,
    pub repo: String,
    pub password_env: String,
    pub password_file: String,
    pub priority: u32,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct TargetStatus {
    pub name: String,
    pub kind: String,
    pub repo: String,
    pub priority: u32,
    pub enabled: bool,
    pub restic: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct SnapshotRow {
    pub target: String,
    pub snapshot_id: String,
    pub files: i64,
    pub bytes: i64,
    pub created_at: String,
    pub revision_id: Option<i64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AssetStatus {
    pub restic_version: Option<String>,
    pub targets: Vec<TargetStatus>,
    pub snapshots: Vec<SnapshotRow>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TargetResult {
    pub target: String,
    pub ok: bool,
    pub snapshot_id: Option<String>,
    pub files: i64,
    pub bytes: i64,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct BackupOutcome {
    pub results: Vec<TargetResult>,
    pub partial: bool,
}

/// `[[backup.target]]` from `workspace.toml`, falling back to `.gitmove/config.toml`.
pub fn load_targets(root: &Path) -> Vec<Target> {
    let mut targets = read_targets(&paths::workspace_manifest(root));
    if targets.is_empty() {
        targets = read_targets(&paths::config_path(root));
    }
    targets.sort_by_key(|target| target.priority);
    targets
}

fn read_targets(path: &Path) -> Vec<Target> {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let Ok(parsed) = toml::from_str::<WorkspaceFile>(&raw) else {
        return Vec::new();
    };
    parsed
        .backup
        .target
        .into_iter()
        .filter(|item| !item.repo.trim().is_empty())
        .map(|item| Target {
            name: if item.name.trim().is_empty() {
                item.repo.clone()
            } else {
                item.name
            },
            kind: item.kind,
            repo: item.repo,
            password_env: item.password_env,
            password_file: item.password_file,
            priority: item.priority,
            enabled: item.enabled,
        })
        .collect()
}

pub fn restic_path() -> Option<String> {
    if let Ok(value) = std::env::var("RESTIC_PATH") {
        if !value.trim().is_empty() {
            return Some(value);
        }
    }
    let output = Command::new("restic").arg("version").output().ok()?;
    if output.status.success() {
        Some("restic".to_string())
    } else {
        None
    }
}

pub fn restic_version() -> Option<String> {
    let path = restic_path()?;
    let output = Command::new(path).arg("version").output().ok()?;
    let text = String::from_utf8_lossy(&output.stdout).to_string();
    text.lines().next().map(|line| line.trim().to_string())
}

fn require_restic() -> CoreResult<String> {
    restic_path().ok_or_else(|| {
        CoreError::new("RESTIC_MISSING", "restic 不在 PATH（gitmove 不捆绑 restic）").with_steps(vec![
            "安装 restic 并加入 PATH：https://restic.net".to_string(),
            "或设置 RESTIC_PATH 指向 restic.exe".to_string(),
        ])
    })
}

fn password_file_arg(target: &Target, root: &Path) -> CoreResult<Option<String>> {
    if !target.password_file.trim().is_empty() {
        let file = PathBuf::from(&target.password_file);
        if !file.is_file() {
            return Err(CoreError::new(
                "DEPOT_PASSWORD_MISSING",
                format!("密码文件不存在: {}", file.display()),
            ));
        }
        if file.ancestors().any(|ancestor| ancestor.join(".git").exists()) {
            return Err(CoreError::new(
                "DEPOT_PASSWORD_IN_REPO",
                format!("密码文件不得位于 Git 仓库内: {}", file.display()),
            ));
        }
        let _ = root;
        return Ok(Some(file.to_string_lossy().to_string()));
    }
    Ok(None)
}

fn excludes(root: &Path) -> Vec<String> {
    let mut patterns = vec![".git".to_string(), ".gitmove".to_string()];
    // A backup repository placed inside the workspace must not back itself up.
    for target in load_targets(root) {
        let repo = PathBuf::from(&target.repo);
        if let Ok(relative) = repo.strip_prefix(root) {
            let value = relative.to_string_lossy().replace('\\', "/");
            if !value.is_empty() {
                patterns.push(value);
            }
        }
    }
    let config = paths::config_path(root);
    if let Ok(raw) = std::fs::read_to_string(config) {
        if let Ok(parsed) = toml::from_str::<toml::Value>(&raw) {
            if let Some(items) = parsed
                .get("depot")
                .and_then(|depot| depot.get("excludes"))
                .and_then(|value| value.as_array())
            {
                patterns.extend(items.iter().filter_map(|item| item.as_str().map(str::to_string)));
            }
        }
    }
    patterns
}

fn run_restic(target: &Target, root: &Path, args: &[&str]) -> CoreResult<(bool, String, String)> {
    // 密码文件在仓库里必须先拒绝。否则没装 restic 的机器只会报 RESTIC_MISSING，把这条金样盖掉。
    let password = password_file_arg(target, root)?;
    let restic = require_restic()?;
    let mut command = Command::new(restic);
    command.arg("-r").arg(&target.repo);
    if let Some(file) = password {
        command.arg("--password-file").arg(file);
    } else if !target.password_env.trim().is_empty() {
        let value = std::env::var(&target.password_env).map_err(|_| {
            CoreError::new(
                "DEPOT_PASSWORD_MISSING",
                format!("环境变量 {} 未设置", target.password_env),
            )
        })?;
        command.env("RESTIC_PASSWORD", value);
    }
    command.args(args).current_dir(root);
    let output = command.output().map_err(|err| CoreError::new("RESTIC_FAILED", err.to_string()))?;
    Ok((
        output.status.success(),
        String::from_utf8_lossy(&output.stdout).to_string(),
        String::from_utf8_lossy(&output.stderr).to_string(),
    ))
}

fn parse_summary(stdout: &str) -> (Option<String>, i64, i64) {
    let mut snapshot = None;
    let mut files = 0;
    let mut bytes = 0;
    for line in stdout.lines().rev() {
        let line = line.trim();
        if !line.starts_with('{') {
            continue;
        }
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if value.get("message_type").and_then(|item| item.as_str()) != Some("summary") {
            continue;
        }
        snapshot = value.get("snapshot_id").and_then(|item| item.as_str()).map(str::to_string);
        files = value.get("files_new").and_then(|item| item.as_i64()).unwrap_or(0);
        bytes = value.get("data_added").and_then(|item| item.as_i64()).unwrap_or(0);
        break;
    }
    (snapshot, files, bytes)
}

pub fn status(root: &Path) -> AssetStatus {
    let targets = load_targets(root)
        .into_iter()
        .map(|target| TargetStatus {
            name: target.name,
            kind: target.kind,
            repo: target.repo,
            priority: target.priority,
            enabled: target.enabled,
            restic: restic_path().is_some(),
        })
        .collect();
    AssetStatus {
        restic_version: restic_version(),
        targets,
        snapshots: snapshots(root, 20).unwrap_or_default(),
    }
}

pub fn snapshots(root: &Path, limit: u32) -> CoreResult<Vec<SnapshotRow>> {
    let conn = crate::revision::connect(root)?;
    let mut stmt = conn.prepare(
        "SELECT target, snapshot_id, files, bytes, created_at, revision_id
         FROM asset_snapshot ORDER BY id DESC LIMIT ?1",
    )?;
    let rows = stmt.query_map(params![limit], |row| {
        Ok(SnapshotRow {
            target: row.get(0)?,
            snapshot_id: row.get(1)?,
            files: row.get(2)?,
            bytes: row.get(3)?,
            created_at: row.get(4)?,
            revision_id: row.get(5)?,
        })
    })?;
    Ok(rows.filter_map(Result::ok).collect())
}

fn record(root: &Path, target: &str, snapshot: &str, files: i64, bytes: i64, revision: Option<i64>) -> CoreResult<()> {
    let conn = crate::revision::connect(root)?;
    conn.execute(
        "INSERT OR REPLACE INTO asset_snapshot(target, snapshot_id, files, bytes, created_at, revision_id)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![target, snapshot, files, bytes, Utc::now().to_rfc3339(), revision],
    )?;
    Ok(())
}

/// One backup per enabled target; a failing target never blocks the others.
pub fn backup(root: &Path, only: Option<&str>, revision: Option<i64>) -> CoreResult<BackupOutcome> {
    let targets: Vec<Target> = load_targets(root)
        .into_iter()
        .filter(|target| only.map(|name| name == target.name).unwrap_or(true))
        .filter(|target| target.enabled)
        .collect();
    if targets.is_empty() {
        return Err(CoreError::new("ASSET_NO_TARGET", "没有配置备份目标（workspace.toml 的 [[backup.target]]）"));
    }
    let pattern_list = excludes(root);
    let exclude_path = std::env::temp_dir().join(format!("gitmove-excludes-{}.txt", std::process::id()));
    std::fs::write(&exclude_path, pattern_list.join("\n") + "\n")?;

    let mut results = Vec::new();
    for target in targets {
        let exclude_arg = exclude_path.to_string_lossy().to_string();
        let outcome = run_restic(&target, root, &["backup", ".", "--json", "--exclude-file", &exclude_arg]);
        let result = match outcome {
            Ok((true, stdout, _)) => {
                let (snapshot, files, bytes) = parse_summary(&stdout);
                if let Some(id) = &snapshot {
                    let _ = record(root, &target.name, id, files, bytes, revision);
                }
                TargetResult {
                    target: target.name,
                    ok: snapshot.is_some(),
                    snapshot_id: snapshot,
                    files,
                    bytes,
                    message: "ok".to_string(),
                }
            }
            Ok((false, _stdout, stderr)) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: stderr.trim().chars().take(300).collect(),
            },
            Err(err) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: err.message,
            },
        };
        results.push(result);
    }
    let _ = std::fs::remove_file(&exclude_path);
    let partial = results.iter().any(|item| !item.ok) && results.iter().any(|item| item.ok);
    Ok(BackupOutcome { results, partial })
}

/// `restic init`: create the repository for every enabled target (idempotent).
pub fn init(root: &Path, only: Option<&str>) -> CoreResult<Vec<TargetResult>> {
    let targets: Vec<Target> = load_targets(root)
        .into_iter()
        .filter(|target| only.map(|name| name == target.name).unwrap_or(true))
        .filter(|target| target.enabled)
        .collect();
    if targets.is_empty() {
        return Err(CoreError::new("ASSET_NO_TARGET", "没有配置备份目标"));
    }
    let mut results = Vec::new();
    for target in targets {
        let outcome = run_restic(&target, root, &["init"]);
        let result = match outcome {
            Ok((true, stdout, _)) => TargetResult {
                target: target.name,
                ok: true,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: if stdout.trim().is_empty() { "created".to_string() } else { stdout.trim().to_string() },
            },
            Ok((false, _stdout, stderr)) => {
                let text = stderr.trim().to_string();
                let already = text.to_lowercase().contains("already initialized")
                    || text.to_lowercase().contains("config file already exists");
                TargetResult {
                    target: target.name,
                    ok: already,
                    snapshot_id: None,
                    files: 0,
                    bytes: 0,
                    message: if already { "already initialized".to_string() } else { text.chars().take(300).collect() },
                }
            }
            Err(err) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: err.message,
            },
        };
        results.push(result);
    }
    Ok(results)
}

pub fn check(root: &Path, only: Option<&str>) -> CoreResult<Vec<TargetResult>> {
    let targets: Vec<Target> = load_targets(root)
        .into_iter()
        .filter(|target| only.map(|name| name == target.name).unwrap_or(true))
        .filter(|target| target.enabled)
        .collect();
    let mut results = Vec::new();
    for target in targets {
        let outcome = run_restic(&target, root, &["check", "--read-data=false"]);
        let result = match outcome {
            Ok((true, stdout, _)) => TargetResult {
                target: target.name,
                ok: true,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: if stdout.trim().is_empty() { "ok".to_string() } else { "ok".to_string() },
            },
            Ok((false, _stdout, stderr)) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: stderr.trim().chars().take(300).collect(),
            },
            Err(err) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: err.message,
            },
        };
        results.push(result);
    }
    Ok(results)
}

pub fn restore(root: &Path, snapshot: &str, only: Option<&str>) -> CoreResult<TargetResult> {
    restore_paths(root, snapshot, only, &[], None)
}

/// Restore selected paths (empty = whole snapshot) into `destination` (default: workspace root).
pub fn restore_paths(
    root: &Path,
    snapshot: &str,
    only: Option<&str>,
    paths: &[String],
    destination: Option<&Path>,
) -> CoreResult<TargetResult> {
    let targets = load_targets(root);
    let ordered: Vec<Target> = match only {
        Some(name) => targets.into_iter().filter(|target| target.name == name).collect(),
        None => targets.into_iter().filter(|target| target.enabled).collect(),
    };
    let dest = destination.unwrap_or(root).to_string_lossy().to_string();
    let mut last_error = String::new();
    for target in ordered {
        let mut args: Vec<String> = vec![
            "restore".to_string(),
            snapshot.to_string(),
            "--target".to_string(),
            dest.clone(),
        ];
        for path in paths {
            args.push("--include".to_string());
            args.push(format!("/{}", path.trim_start_matches('/')));
        }
        let borrowed: Vec<&str> = args.iter().map(String::as_str).collect();
        match run_restic(&target, root, &borrowed) {
            Ok((true, _stdout, _stderr)) => {
                return Ok(TargetResult {
                    target: target.name,
                    ok: true,
                    snapshot_id: Some(snapshot.to_string()),
                    files: paths.len() as i64,
                    bytes: 0,
                    message: if paths.is_empty() {
                        format!("restored to {dest}")
                    } else {
                        format!("restored {} path(s) to {dest}", paths.len())
                    },
                })
            }
            Ok((false, _stdout, stderr)) => last_error = stderr,
            Err(err) => last_error = err.message,
        }
    }
    Err(CoreError::new(
        "ASSET_RESTORE_FAILED",
        format!("所有目标都无法恢复快照 {snapshot}: {last_error}"),
    ))
}

#[derive(Debug, Clone, Serialize)]
pub struct GuardRow {
    pub path: String,
    pub mb: f64,
}

/// Retention passthrough: gitmove never re-implements restic's policy language.
pub fn prune(
    root: &Path,
    keep_daily: Option<u32>,
    keep_weekly: Option<u32>,
    keep_monthly: Option<u32>,
    keep_last: Option<u32>,
    dry_run: bool,
    only: Option<&str>,
) -> CoreResult<Vec<TargetResult>> {
    if keep_daily.is_none() && keep_weekly.is_none() && keep_monthly.is_none() && keep_last.is_none() {
        return Err(CoreError::new(
            "PRUNE_POLICY_REQUIRED",
            "至少给一个 --keep-daily/--keep-weekly/--keep-monthly/--keep-last",
        ));
    }
    let targets: Vec<Target> = load_targets(root)
        .into_iter()
        .filter(|target| only.map(|name| name == target.name).unwrap_or(true))
        .filter(|target| target.enabled)
        .collect();
    let mut results = Vec::new();
    for target in targets {
        let mut args: Vec<String> = vec!["forget".into(), "--prune".into()];
        for (flag, value) in [
            ("--keep-daily", keep_daily),
            ("--keep-weekly", keep_weekly),
            ("--keep-monthly", keep_monthly),
            ("--keep-last", keep_last),
        ] {
            if let Some(value) = value {
                args.push(flag.to_string());
                args.push(value.to_string());
            }
        }
        if dry_run {
            args.push("--dry-run".into());
        }
        let refs: Vec<&str> = args.iter().map(String::as_str).collect();
        let outcome = run_restic(&target, root, &refs);
        let result = match outcome {
            Ok((true, stdout, _)) => TargetResult {
                target: target.name,
                ok: true,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: stdout.trim().chars().take(300).collect(),
            },
            Ok((false, _stdout, stderr)) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: stderr.trim().chars().take(300).collect(),
            },
            Err(err) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: err.message,
            },
        };
        results.push(result);
    }
    Ok(results)
}

fn max_file_mb(root: &Path) -> u64 {
    let Ok(raw) = std::fs::read_to_string(paths::config_path(root)) else {
        return 5;
    };
    let Ok(parsed) = toml::from_str::<toml::Value>(&raw) else {
        return 5;
    };
    parsed
        .get("depot")
        .and_then(|depot| depot.get("max_file_mb"))
        .and_then(|value| value.as_integer())
        .map(|value| value as u64)
        .unwrap_or(5)
}

/// Staged files above `[depot] max_file_mb` must never enter git history.
pub fn guard(root: &Path) -> CoreResult<Vec<GuardRow>> {
    let limit = max_file_mb(root) * 1024 * 1024;
    let raw = git::run(root, &["diff", "--cached", "--name-only", "-z"])?;
    let mut rows = Vec::new();
    for path in raw.split('\0').filter(|value| !value.is_empty()) {
        let file = root.join(path);
        let Ok(meta) = file.metadata() else { continue };
        if meta.len() as u64 > limit {
            rows.push(GuardRow {
                path: path.to_string(),
                mb: meta.len() as f64 / (1024.0 * 1024.0),
            });
        }
    }
    Ok(rows)
}


/// Validate repository access and credentials without writing anything.
pub fn test_targets(root: &Path, only: Option<&str>) -> CoreResult<Vec<TargetResult>> {
    let targets: Vec<Target> = load_targets(root)
        .into_iter()
        .filter(|target| only.map(|name| name == target.name).unwrap_or(true))
        .collect();
    let mut results = Vec::new();
    for target in targets {
        let outcome = run_restic(&target, root, &["cat", "config"]);
        let result = match outcome {
            Ok((true, _stdout, _stderr)) => TargetResult {
                target: target.name,
                ok: true,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: "reachable".to_string(),
            },
            Ok((false, _stdout, stderr)) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: stderr.trim().chars().take(300).collect(),
            },
            Err(err) => TargetResult {
                target: target.name,
                ok: false,
                snapshot_id: None,
                files: 0,
                bytes: 0,
                message: err.message,
            },
        };
        results.push(result);
    }
    Ok(results)
}


#[derive(Debug, Clone, Serialize)]
pub struct SnapshotDiffRow {
    pub modifier: String,
    pub path: String,
}

/// Compare two snapshots with restic diff (text output parsed).
pub fn diff_snapshots(root: &Path, target_name: Option<&str>, a: &str, b: &str) -> CoreResult<Vec<SnapshotDiffRow>> {
    let targets = load_targets(root);
    let target = match target_name {
        Some(name) => targets.into_iter().find(|item| item.name == name),
        None => targets.into_iter().next(),
    }
    .ok_or_else(|| CoreError::new("ASSET_NO_TARGET", "没有配置备份目标"))?;
    let (ok, stdout, stderr) = run_restic(&target, root, &["diff", a, b])?;
    if !ok {
        return Err(CoreError::new("ASSET_DIFF_FAILED", stderr));
    }
    let mut rows = Vec::new();
    for line in stdout.lines() {
        let trimmed = line.trim_end();
        if trimmed.is_empty() || trimmed.starts_with("comparing") {
            continue;
        }
        let modifier = trimmed.chars().next().unwrap_or(' ');
        if !"+-MT".contains(modifier) {
            continue;
        }
        let path = trimmed[1..].trim();
        if path.is_empty() {
            continue;
        }
        rows.push(SnapshotDiffRow {
            modifier: modifier.to_string(),
            path: path.to_string(),
        });
    }
    Ok(rows)
}
