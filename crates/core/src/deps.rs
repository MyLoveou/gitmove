use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, CoreResult};
use crate::{git, paths, workspace};

#[derive(Debug, Clone, Deserialize)]
struct LockFile {
    #[serde(default)]
    dep: Vec<DepDef>,
}

#[derive(Debug, Clone, Deserialize)]
struct DepDef {
    #[serde(default)]
    name: String,
    #[serde(default)]
    kind: String,
    #[serde(default)]
    url: String,
    #[serde(default)]
    ref_tag: Option<String>,
    #[serde(default)]
    commit: Option<String>,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    note: Option<String>,
    #[serde(default)]
    installed: Vec<InstalledDef>,
}

#[derive(Debug, Clone, Deserialize)]
struct InstalledDef {
    #[serde(default)]
    package: String,
    #[serde(default)]
    version: String,
    #[serde(default)]
    env: String,
    #[serde(rename = "match", default = "default_true")]
    match_: bool,
    #[serde(default)]
    note: Option<String>,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize)]
pub struct DepRow {
    pub name: String,
    pub kind: String,
    pub url: String,
    pub ref_tag: Option<String>,
    pub commit: Option<String>,
    pub version: Option<String>,
    pub status: Option<String>,
    pub drift: bool,
    pub in_effect: bool,
    pub installed: Vec<InstalledRow>,
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InstalledRow {
    pub package: String,
    pub version: String,
    pub env: String,
    pub match_: bool,
    pub note: Option<String>,
}

fn parse(root: &Path) -> CoreResult<Vec<DepRow>> {
    let path = root.join("project.lock.toml");
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Ok(Vec::new());
    };
    let parsed: LockFile = toml::from_str(&raw)?;
    Ok(parsed
        .dep
        .into_iter()
        .filter(|item| !item.name.trim().is_empty())
        .map(|item| {
            let installed: Vec<InstalledRow> = item
                .installed
                .iter()
                .map(|inst| InstalledRow {
                    package: inst.package.clone(),
                    version: inst.version.clone(),
                    env: inst.env.clone(),
                    match_: inst.match_,
                    note: inst.note.clone(),
                })
                .collect();
            let drift = installed.iter().any(|row| !row.match_);
            let in_effect = item.status.as_deref().map(|value| value.is_empty() || value == "ok").unwrap_or(true);
            DepRow {
                name: item.name,
                kind: item.kind,
                url: item.url,
                ref_tag: item.ref_tag,
                commit: item.commit,
                version: item.version,
                status: item.status,
                drift,
                in_effect,
                installed,
                note: item.note,
            }
        })
        .collect())
}

pub fn list(root: &Path) -> CoreResult<Vec<DepRow>> {
    parse(root)
}

/// `v0.5.0 → 0.2.1 ✗`, `86cbb8f · 未生效`, `v0.5.0`.
pub fn label(dep: &DepRow) -> String {
    let declared = dep
        .ref_tag
        .clone()
        .or_else(|| dep.commit.as_ref().map(|value| value.chars().take(7).collect()))
        .unwrap_or_else(|| "—".to_string());
    if !dep.in_effect {
        return format!("{declared} · 未生效");
    }
    let mismatched = dep.installed.iter().find(|row| !row.match_);
    let shown = mismatched
        .map(|row| row.version.clone())
        .or_else(|| dep.installed.first().map(|row| row.version.clone()));
    match shown {
        Some(version) if !version.is_empty() => {
            let marker = if dep.drift { " ✗" } else { "" };
            format!("{declared} → {version}{marker}")
        }
        _ => declared,
    }
}


#[derive(Debug, Clone, Serialize)]
pub struct DepStatusRow {
    pub name: String,
    pub kind: String,
    pub url: String,
    pub lock_version: Option<String>,
    pub lock_commit: Option<String>,
    pub upstream_version: Option<String>,
    pub upstream_commit: Option<String>,
    pub behind: Option<u64>,
    pub ahead: Option<u64>,
    pub state: String,
    pub message: String,
    pub repo: Option<String>,
}

fn cache_dir(name: &str) -> PathBuf {
    paths::home_dir().join("cache").join("deps").join(name)
}

fn local_repo(root: &Path, name: &str, url: &str) -> Option<PathBuf> {
    if let Ok((_, members, _)) = workspace::load(root) {
        if let Some(member) = members.iter().find(|item| item.name == name) {
            if member.path.join(".git").exists() {
                return Some(member.path.clone());
            }
        }
    }
    let url_path = PathBuf::from(url);
    if url_path.is_dir() && url_path.join(".git").exists() {
        return Some(url_path);
    }
    let cache = cache_dir(name);
    if cache.join(".git").exists() {
        return Some(cache);
    }
    None
}

fn ensure_repo(root: &Path, name: &str, url: &str, fetch: bool) -> Option<PathBuf> {
    if let Some(repo) = local_repo(root, name, url) {
        if fetch {
            let _ = git::run_allow_fail(&repo, &["fetch", "--tags", "--prune", "--quiet"]);
        }
        return Some(repo);
    }
    if !fetch || url.trim().is_empty() {
        return None;
    }
    let target = cache_dir(name);
    if let Some(parent) = target.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::remove_dir_all(&target);
    let cloned = git::run(
        root,
        &["clone", "--filter=blob:none", "--quiet", url, &target.to_string_lossy()],
    )
    .or_else(|_| git::run(root, &["clone", "--quiet", url, &target.to_string_lossy()]));
    cloned.ok()?;
    Some(target)
}

fn read_version(repo: &Path, reference: &str) -> Option<String> {
    let raw = git::run_allow_fail(repo, &["show", &format!("{reference}:VERSION")])?;
    let value = raw.trim().to_string();
    (!value.is_empty()).then_some(value)
}

fn resolve(repo: &Path, reference: &str) -> Option<String> {
    git::run_allow_fail(repo, &["rev-parse", &format!("{reference}^{{commit}}")])
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn count(repo: &Path, range: &str) -> Option<u64> {
    git::run_allow_fail(repo, &["rev-list", "--count", range])
        .and_then(|value| value.trim().parse::<u64>().ok())
}

/// Compare lock entries with their upstream repositories (local members first, then cache).
pub fn status(root: &Path, fetch: bool) -> CoreResult<Vec<DepStatusRow>> {
    let rows = parse(root)?;
    let mut out = Vec::new();
    for row in rows {
        let repo = ensure_repo(root, &row.name, &row.url, fetch);
        let reference = row
            .ref_tag
            .clone()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "HEAD".to_string());
        let mut status = DepStatusRow {
            name: row.name.clone(),
            kind: row.kind.clone(),
            url: row.url.clone(),
            lock_version: row.version.clone(),
            lock_commit: row.commit.clone(),
            upstream_version: None,
            upstream_commit: None,
            behind: None,
            ahead: None,
            state: "unknown".to_string(),
            message: String::new(),
            repo: repo.as_ref().map(|path| path.to_string_lossy().to_string()),
        };
        if let Some(repo_path) = repo {
            status.upstream_commit = resolve(&repo_path, &reference);
            status.upstream_version = read_version(&repo_path, &reference);
            if let (Some(upstream), Some(lock)) = (&status.upstream_commit, &status.lock_commit) {
                if lock.starts_with(upstream) || upstream.starts_with(lock) {
                    status.behind = Some(0);
                    status.ahead = Some(0);
                } else {
                    status.behind = count(&repo_path, &format!("{lock}..{upstream}"));
                    status.ahead = count(&repo_path, &format!("{upstream}..{lock}"));
                }
            }
            status.state = match (status.behind, status.ahead) {
                (Some(0), Some(0)) => "ok".to_string(),
                (Some(behind), _) if behind > 0 => "outdated".to_string(),
                (_, Some(ahead)) if ahead > 0 => "ahead".to_string(),
                _ => "unknown".to_string(),
            };
            status.message = match (status.state.as_str(), status.behind) {
                ("outdated", Some(behind)) => format!(
                    "lock {} / upstream {} / behind {} commit(s)",
                    status.lock_version.clone().unwrap_or_else(|| "—".to_string()),
                    status.upstream_version.clone().unwrap_or_else(|| "—".to_string()),
                    behind
                ),
                ("ok", _) => "lock matches upstream".to_string(),
                ("ahead", _) => "lock is ahead of the tracked ref".to_string(),
                _ => "cannot compare (unknown lock commit)".to_string(),
            };
        } else {
            status.message = "no local checkout; run with --fetch".to_string();
        }
        out.push(status);
    }
    Ok(out)
}

/// Move a dep pin forward and update `project.lock.toml` (commit/version/installed).
pub fn update(root: &Path, name: &str, to: Option<&str>) -> CoreResult<DepStatusRow> {
    let lock_path = root.join("project.lock.toml");
    let raw = std::fs::read_to_string(&lock_path)
        .map_err(|_| CoreError::new("LOCK_MISSING", "找不到 project.lock.toml"))?;
    let mut parsed: toml::Value = toml::from_str(&raw)
        .map_err(|err| CoreError::new("LOCK_INVALID", err.to_string()))?;

    let deps = parsed
        .get_mut("dep")
        .and_then(|value| value.as_array_mut())
        .ok_or_else(|| CoreError::new("LOCK_INVALID", "project.lock.toml 缺少 [[dep]]"))?;
    let item = deps
        .iter_mut()
        .find(|item| item.get("name").and_then(|value| value.as_str()) == Some(name))
        .ok_or_else(|| CoreError::new("DEP_NOT_FOUND", format!("没有该依赖: {name}")))?;

    let url = item.get("url").and_then(|value| value.as_str()).unwrap_or_default().to_string();
    let reference = to
        .map(str::to_string)
        .or_else(|| item.get("ref").and_then(|value| value.as_str()).map(str::to_string))
        .unwrap_or_else(|| "HEAD".to_string());
    let repo = ensure_repo(root, name, &url, true)
        .ok_or_else(|| CoreError::new("DEP_REPO_MISSING", format!("无法获取仓库: {url}（用 --to 或先配置本地成员）")))?;
    let commit = resolve(&repo, &reference)
        .ok_or_else(|| CoreError::new("DEP_REF_UNKNOWN", format!("无法解析引用: {reference}")))?;
    let version = read_version(&repo, &commit);

    if let Some(table) = item.as_table_mut() {
        table.insert("commit".to_string(), toml::Value::String(commit.clone()));
        if !reference.is_empty() && reference != "HEAD" {
            table.insert("ref".to_string(), toml::Value::String(reference.clone()));
        }
        if let Some(value) = &version {
            table.insert("version".to_string(), toml::Value::String(value.clone()));
        }
        if let Some(list) = table.get_mut("installed").and_then(|value| value.as_array_mut()) {
            for installed in list.iter_mut() {
                if let Some(entry) = installed.as_table_mut() {
                    if let Some(value) = &version {
                        entry.insert("version".to_string(), toml::Value::String(value.clone()));
                    }
                    entry.insert("match".to_string(), toml::Value::Boolean(true));
                }
            }
        }
    }

    let text = toml::to_string_pretty(&parsed)
        .map_err(|err| CoreError::new("LOCK_INVALID", err.to_string()))?;
    std::fs::write(&lock_path, text)?;

    status(root, false)?
        .into_iter()
        .find(|row| row.name == name)
        .ok_or_else(|| CoreError::new("DEP_NOT_FOUND", format!("没有该依赖: {name}")))
}

/// Verify that lock entries are self-consistent and have installed records.
pub fn verify(root: &Path) -> CoreResult<Vec<DepStatusRow>> {
    status(root, false)
}
