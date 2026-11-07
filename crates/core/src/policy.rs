use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::paths;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Link {
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub external: String,
    #[serde(default = "default_kind")]
    pub kind: String,
}

fn default_kind() -> String {
    "junction".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Worktree {
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub branch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Policy {
    #[serde(default)]
    pub skip_paths: Vec<String>,
    #[serde(default)]
    pub external_base: String,
    #[serde(default)]
    pub links: Vec<Link>,
    #[serde(default)]
    pub worktrees: Vec<Worktree>,
}

fn config_file(root: &Path) -> PathBuf {
    root.join(".gitmove").join("config.toml")
}

/// Read `.gitmove/config.toml`, falling back to the legacy `.git/gitmove.toml`.
/// Both `[[links]]`/`[[link]]` spellings are accepted.
pub fn load(root: &Path) -> Policy {
    for path in [config_file(root), root.join(".git").join("gitmove.toml")] {
        let Ok(raw) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Ok(value) = toml::from_str::<toml::Value>(&raw) else {
            continue;
        };
        let mut policy = Policy::default();
        policy.skip_paths = string_array(&value, "skip_paths");
        policy.external_base = value
            .get("external_base")
            .and_then(|item| item.as_str())
            .unwrap_or_default()
            .to_string();
        let link_items = value
            .get("links")
            .or_else(|| value.get("link"))
            .and_then(|item| item.as_array());
        if let Some(items) = link_items {
            for item in items {
                policy.links.push(Link {
                    path: item.get("path").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                    external: item
                        .get("external")
                        .or_else(|| item.get("external_path"))
                        .and_then(|v| v.as_str())
                        .unwrap_or_default()
                        .to_string(),
                    kind: item.get("kind").and_then(|v| v.as_str()).unwrap_or("junction").to_string(),
                });
            }
        }
        let worktree_items = value
            .get("worktrees")
            .or_else(|| value.get("worktree"))
            .and_then(|item| item.as_array());
        if let Some(items) = worktree_items {
            for item in items {
                policy.worktrees.push(Worktree {
                    path: item.get("path").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                    branch: item.get("branch").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                });
            }
        }
        return policy;
    }
    Policy::default()
}

fn string_array(value: &toml::Value, key: &str) -> Vec<String> {
    value
        .get(key)
        .and_then(|item| item.as_array())
        .map(|items| items.iter().filter_map(|item| item.as_str().map(str::to_string)).collect())
        .unwrap_or_default()
}

pub fn save(root: &Path, policy: &Policy) -> CoreResult<()> {
    let path = config_file(root);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    // Keep one previous version so a bad edit can be recovered.
    if path.is_file() {
        let _ = std::fs::copy(&path, path.with_extension("toml.bak"));
    }
    std::fs::write(path, toml::to_string_pretty(policy).unwrap_or_default())?;
    Ok(())
}

pub fn skip_list(root: &Path) -> CoreResult<Vec<String>> {
    let raw = git::run(root, &["ls-files", "-v", "-z"])?;
    Ok(raw
        .split('\0')
        .filter(|record| record.starts_with("S "))
        .map(|record| record[2..].replace('\\', "/"))
        .collect())
}

pub fn skip_add(root: &Path, items: &[String]) -> CoreResult<Vec<String>> {
    for item in items {
        git::run(root, &["update-index", "--add", "--skip-worktree", item])?;
    }
    let mut policy = load(root);
    for item in items {
        if !policy.skip_paths.contains(item) {
            policy.skip_paths.push(item.clone());
        }
    }
    policy.skip_paths.sort();
    save(root, &policy)?;
    Ok(policy.skip_paths)
}

pub fn skip_remove(root: &Path, items: &[String]) -> CoreResult<Vec<String>> {
    for item in items {
        let _ = git::run_allow_fail(root, &["update-index", "--no-skip-worktree", item]);
    }
    let mut policy = load(root);
    policy.skip_paths.retain(|value| !items.contains(value));
    save(root, &policy)?;
    Ok(policy.skip_paths)
}

fn is_link(path: &Path) -> bool {
    std::fs::symlink_metadata(path)
        .map(|meta| meta.file_type().is_symlink() || meta.file_type().is_dir())
        .unwrap_or(false)
}

pub fn link_add(
    root: &Path,
    relative: &str,
    external: &str,
    kind: &str,
    migrate: bool,
) -> CoreResult<Vec<Link>> {
    let link_path = root.join(relative);
    let external_path = PathBuf::from(external);
    if !external_path.exists() {
        std::fs::create_dir_all(&external_path)?;
    }
    if lock_exists(&link_path) && !migrate {
        return Err(CoreError::new(
            "LINK_TARGET_EXISTS",
            format!("目标已存在: {}", link_path.display()),
        )
        .with_steps(vec!["先移走该目录，或使用 --migrate".to_string()]));
    }
    if migrate && link_path.exists() {
        let entries = std::fs::read_dir(&link_path)?.count();
        if entries > 0 {
            return Err(CoreError::new(
                "LINK_TARGET_NOT_EMPTY",
                "迁移要求目标目录为空（先手工移动数据）".to_string(),
            ));
        }
        let _ = std::fs::remove_dir(&link_path);
    }

    create_link(&link_path, &external_path, kind)?;

    let mut policy = load(root);
    policy.links.retain(|item| item.path != relative);
    policy.links.push(Link {
        path: relative.to_string(),
        external: external.to_string(),
        kind: kind.to_string(),
    });
    save(root, &policy)?;
    Ok(policy.links)
}


pub fn create_link(link_path: &Path, external: &Path, kind: &str) -> CoreResult<()> {
    if let Some(parent) = link_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    #[cfg(windows)]
    {
        if kind == "symlink" {
            std::os::windows::fs::symlink_dir(external, link_path).map_err(|err| {
                CoreError::new("LINK_CREATE_FAILED", format!("创建目录符号链接失败: {err}"))
                    .with_steps(vec!["Windows 创建 symlink 需要开发者模式或管理员权限".to_string()])
            })?;
        } else {
            // mklink /J needs native separators and an existing target directory.
            let link = link_path.to_string_lossy().replace('/', "\\");
            let target = external.to_string_lossy().replace('/', "\\");
            if !external.is_dir() {
                return Err(CoreError::new(
                    "LINK_TARGET_MISSING",
                    format!("链接目标不存在或不是目录: {}", external.display()),
                ));
            }
            let output = Command::new("cmd")
                .args(["/C", "mklink", "/J", &link, &target])
                .output()
                .map_err(|err| CoreError::new("LINK_CREATE_FAILED", format!("无法运行 mklink: {err}")))?;
            if !output.status.success() {
                let stderr = String::from_utf8_lossy(&output.stderr);
                let stdout = String::from_utf8_lossy(&output.stdout);
                return Err(CoreError::new(
                    "LINK_CREATE_FAILED",
                    format!(
                        "mklink /J 失败 (exit {:?}): {}{}",
                        output.status.code(),
                        stdout.trim(),
                        stderr.trim()
                    ),
                )
                .with_steps(vec![
                    format!("link = {link}"),
                    format!("target = {target}"),
                    "确认目标目录存在且链接路径未被占用".to_string(),
                ]));
            }
        }
    }
    #[cfg(not(windows))]
    {
        let _ = kind;
        std::os::unix::fs::symlink(external, link_path)
            .map_err(|err| CoreError::new("LINK_CREATE_FAILED", format!("创建符号链接失败: {err}")))?;
    }
    Ok(())
}

fn lock_exists(path: &Path) -> bool {
    std::fs::symlink_metadata(path).is_ok()
}

pub fn link_list(root: &Path) -> Vec<serde_json::Value> {
    load(root)
        .links
        .into_iter()
        .map(|item| {
            let path = root.join(&item.path);
            serde_json::json!({
                "path": item.path,
                "external": item.external,
                "kind": item.kind,
                "exists": path.exists(),
                "is_link": is_link(&path),
            })
        })
        .collect()
}

pub fn link_remove(root: &Path, relative: &str) -> CoreResult<Vec<Link>> {
    let link_path = root.join(relative);
    if lock_exists(&link_path) {
        #[cfg(windows)]
        {
            let _ = Command::new("cmd")
                .args(["/C", "rmdir", &link_path.to_string_lossy().to_string()])
                .status();
        }
        #[cfg(not(windows))]
        {
            let _ = std::fs::remove_file(&link_path);
        }
        if lock_exists(&link_path) {
            let _ = std::fs::remove_dir(&link_path);
        }
    }
    let mut policy = load(root);
    policy.links.retain(|item| item.path != relative);
    save(root, &policy)?;
    Ok(policy.links)
}

pub fn worktree_add(root: &Path, path: &str, branch: &str) -> CoreResult<Vec<Worktree>> {
    git::run(root, &["worktree", "add", path, branch])?;
    let mut policy = load(root);
    policy.worktrees.retain(|item| item.path != path);
    policy.worktrees.push(Worktree { path: path.to_string(), branch: branch.to_string() });
    save(root, &policy)?;
    Ok(policy.worktrees)
}

pub fn worktree_list(root: &Path) -> CoreResult<Vec<serde_json::Value>> {
    let raw = git::run(root, &["worktree", "list", "--porcelain"])?;
    let mut rows = Vec::new();
    let mut current_path = String::new();
    for line in raw.lines() {
        if let Some(value) = line.strip_prefix("worktree ") {
            if !current_path.is_empty() {
                rows.push(serde_json::json!({ "path": current_path }));
            }
            current_path = value.to_string();
        }
    }
    if !current_path.is_empty() {
        rows.push(serde_json::json!({ "path": current_path }));
    }
    Ok(rows)
}

pub fn worktree_remove(root: &Path, path: &str) -> CoreResult<Vec<Worktree>> {
    git::run(root, &["worktree", "remove", path])?;
    let mut policy = load(root);
    policy.worktrees.retain(|item| item.path != path);
    save(root, &policy)?;
    Ok(policy.worktrees)
}

/// Re-apply skip-worktree flags and links recorded in the policy.
pub fn apply(root: &Path) -> CoreResult<serde_json::Value> {
    let policy = load(root);
    let mut applied_skips = 0;
    for item in &policy.skip_paths {
        if git::run_allow_fail(root, &["update-index", "--add", "--skip-worktree", item]).is_some() {
            applied_skips += 1;
        }
    }
    let mut fixed_links = 0;
    let mut broken_links = 0;
    for item in &policy.links {
        let path = root.join(&item.path);
        if path.exists() {
            continue;
        }
        let external = PathBuf::from(&item.external);
        if !external.exists() {
            broken_links += 1;
            continue;
        }
        if link_add(root, &item.path, &item.external, &item.kind, false).is_ok() {
            fixed_links += 1;
        } else {
            broken_links += 1;
        }
    }
    Ok(serde_json::json!({
        "skip_applied": applied_skips,
        "links_fixed": fixed_links,
        "links_broken": broken_links,
        "skip_paths": policy.skip_paths.len(),
        "links": policy.links.len(),
        "worktrees": policy.worktrees.len(),
    }))
}
