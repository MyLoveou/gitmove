use std::collections::BTreeMap;
use std::path::Path;
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::asset;
use crate::error::{CoreError, CoreResult};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FileEntry {
    pub path: String,
    pub size: i64,
    pub mtime: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct MergeItem {
    pub path: String,
    pub action: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct MergeConflict {
    pub path: String,
    pub reason: String,
    pub ours: Option<FileEntry>,
    pub theirs: Option<FileEntry>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MergePlan {
    pub base: String,
    pub ours: String,
    pub theirs: String,
    pub merged: Vec<MergeItem>,
    pub conflicts: Vec<MergeConflict>,
    pub apply_from_ours: Vec<String>,
    pub apply_from_theirs: Vec<String>,
    pub delete: Vec<String>,
}

fn restic_ls(target_repo: &str, password: Option<(String, String)>, snapshot: &str) -> CoreResult<Vec<FileEntry>> {
    let restic = asset::restic_path().ok_or_else(|| CoreError::new("RESTIC_MISSING", "restic 不在 PATH"))?;
    let mut command = Command::new(restic);
    command.arg("-r").arg(target_repo);
    if let Some((key, value)) = password {
        if key == "env" {
            command.env("RESTIC_PASSWORD", value);
        } else {
            command.arg("--password-file").arg(value);
        }
    }
    let output = command.args(["ls", snapshot, "--json"]).output()?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(CoreError::new("ASSET_LS_FAILED", format!("restic ls 失败: {stderr}")));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut files = Vec::new();
    for line in stdout.lines() {
        let line = line.trim();
        if !line.starts_with('{') {
            continue;
        }
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if value.get("struct_type").and_then(|item| item.as_str()) != Some("node") {
            continue;
        }
        if value.get("type").and_then(|item| item.as_str()) != Some("file") {
            continue;
        }
        let path = value.get("path").and_then(|item| item.as_str()).unwrap_or_default();
        let path = path.trim_start_matches('/').to_string();
        if path.is_empty() {
            continue;
        }
        let size = value.get("size").and_then(|item| item.as_i64()).unwrap_or(0);
        let mtime = value
            .get("mtime")
            .and_then(|item| item.as_str())
            .unwrap_or_default()
            .to_string();
        files.push(FileEntry { path, size, mtime });
    }
    Ok(files)
}

fn snapshot_password(target_name: &str, root: &Path) -> CoreResult<Option<(String, String)>> {
    for candidate in asset::load_targets(root) {
        if candidate.name != target_name {
            continue;
        }
        if !candidate.password_env.trim().is_empty() {
            let value = std::env::var(&candidate.password_env).map_err(|_| {
                CoreError::new("DEPOT_PASSWORD_MISSING", format!("环境变量 {} 未设置", candidate.password_env))
            })?;
            return Ok(Some(("env".to_string(), value)));
        }
        if !candidate.password_file.trim().is_empty() {
            return Ok(Some(("file".to_string(), candidate.password_file.clone())));
        }
        return Ok(None);
    }
    Err(CoreError::new("ASSET_NO_TARGET", format!("没有备份目标: {target_name}")))
}

fn read_snapshot(root: &Path, target_name: &str, snapshot: &str) -> CoreResult<BTreeMap<String, FileEntry>> {
    let repo = asset::load_targets(root)
        .into_iter()
        .find(|item| item.name == target_name)
        .ok_or_else(|| CoreError::new("ASSET_NO_TARGET", format!("没有备份目标: {target_name}")))?;
    let password = snapshot_password(target_name, root)?;
    let files = restic_ls(&repo.repo, password, snapshot)?;
    Ok(files.into_iter().map(|item| (item.path.clone(), item)).collect())
}

fn same(left: &Option<FileEntry>, right: &Option<FileEntry>) -> bool {
    match (left, right) {
        (None, None) => true,
        (Some(a), Some(b)) => a.size == b.size && a.mtime == b.mtime,
        _ => false,
    }
}

/// Content hash of one file inside a snapshot (only used for ambiguous cases).
fn dump_hash(repo: &str, password: &Option<(String, String)>, snapshot: &str, path: &str) -> Option<u64> {
    use std::hash::{Hash, Hasher};
    let restic = asset::restic_path()?;
    let mut command = Command::new(restic);
    command.arg("-r").arg(repo);
    if let Some((kind, value)) = password {
        if kind == "env" {
            command.env("RESTIC_PASSWORD", value);
        } else {
            command.arg("--password-file").arg(value);
        }
    }
    let output = command.args(["dump", snapshot, path]).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    output.stdout.hash(&mut hasher);
    Some(hasher.finish())
}

/// Equality with a content-hash fallback when size matches but mtime differs.
fn same_with(
    repo: &str,
    password: &Option<(String, String)>,
    base_snapshot: &str,
    base: &Option<FileEntry>,
    base_side_snapshot: &str,
    side: &Option<FileEntry>,
) -> bool {
    if same(base, side) {
        return true;
    }
    match (base, side) {
        (Some(b), Some(s)) if b.size == s.size => match (
            dump_hash(repo, password, base_snapshot, &b.path),
            dump_hash(repo, password, base_side_snapshot, &s.path),
        ) {
            (Some(left), Some(right)) => left == right,
            _ => false,
        },
        _ => false,
    }
}

/// Three-way file-level classification (ADR-0013/0015). Never merges content.
pub fn list_files(root: &Path, target: &str, snapshot: &str) -> CoreResult<Vec<FileEntry>> {
    let map = read_snapshot(root, target, snapshot)?;
    Ok(map.into_values().collect())
}

/// Three-way file-level classification (ADR-0013/0015). Never merges content.
pub fn plan(root: &Path, target: &str, base: &str, ours: &str, theirs: &str) -> CoreResult<MergePlan> {
    let repo = asset::load_targets(root)
        .into_iter()
        .find(|item| item.name == target)
        .ok_or_else(|| CoreError::new("ASSET_NO_TARGET", format!("没有备份目标: {target}")))?;
    let password = snapshot_password(target, root)?;
    let base_map = read_snapshot(root, target, base)?;
    let ours_map = read_snapshot(root, target, ours)?;
    let theirs_map = read_snapshot(root, target, theirs)?;

    let mut paths: Vec<String> = base_map.keys().chain(ours_map.keys()).chain(theirs_map.keys()).cloned().collect();
    paths.sort();
    paths.dedup();

    let mut result = MergePlan {
        base: base.to_string(),
        ours: ours.to_string(),
        theirs: theirs.to_string(),
        merged: Vec::new(),
        conflicts: Vec::new(),
        apply_from_ours: Vec::new(),
        apply_from_theirs: Vec::new(),
        delete: Vec::new(),
    };

    for path in paths {
        let b = base_map.get(&path).cloned();
        let o = ours_map.get(&path).cloned();
        let t = theirs_map.get(&path).cloned();
        let ours_changed = !same_with(&repo.repo, &password, base, &b, ours, &o);
        let theirs_changed = !same_with(&repo.repo, &password, base, &b, theirs, &t);

        let mut action: Option<&str> = None;
        let mut from_theirs = false;
        let mut remove = false;
        let mut conflict: Option<MergeConflict> = None;

        match (&b, &o, &t) {
            (None, Some(_), None) => action = Some("keep_ours"),
            (None, None, Some(_)) => {
                action = Some("take_theirs");
                from_theirs = true;
            }
            (None, Some(a), Some(c)) => {
                if a.size == c.size && a.mtime == c.mtime {
                    action = Some("both_same");
                } else {
                    conflict = Some(MergeConflict {
                        path: path.clone(),
                        reason: "both-added".to_string(),
                        ours: o.clone(),
                        theirs: t.clone(),
                    });
                }
            }
            (Some(_), None, Some(_)) if !theirs_changed => {
                action = Some("delete");
                remove = true;
            }
            (Some(_), Some(_), None) if !ours_changed => {
                action = Some("delete");
                remove = true;
            }
            (Some(_), None, None) => {
                action = Some("delete");
                remove = true;
            }
            (Some(_), None, Some(_)) => {
                conflict = Some(MergeConflict {
                    path: path.clone(),
                    reason: "delete-vs-modify".to_string(),
                    ours: None,
                    theirs: t.clone(),
                });
            }
            (Some(_), Some(_), None) => {
                conflict = Some(MergeConflict {
                    path: path.clone(),
                    reason: "modify-vs-delete".to_string(),
                    ours: o.clone(),
                    theirs: None,
                });
            }
            (None, None, None) => {}
            (Some(_), Some(_), Some(c)) => {
                if ours_changed && !theirs_changed {
                    action = Some("keep_ours");
                } else if !ours_changed && theirs_changed {
                    action = Some("take_theirs");
                    from_theirs = true;
                } else if !ours_changed && !theirs_changed {
                    action = Some("unchanged");
                } else if same_with(&repo.repo, &password, ours, &o, theirs, &t) {
                    action = Some("both_same");
                } else {
                    let _ = c;
                    conflict = Some(MergeConflict {
                        path: path.clone(),
                        reason: "both-modified".to_string(),
                        ours: o.clone(),
                        theirs: t.clone(),
                    });
                }
            }
        }

        if let Some(label) = action {
            result.merged.push(MergeItem { path: path.clone(), action: label.to_string() });
        }
        if from_theirs {
            result.apply_from_theirs.push(path.clone());
        }
        if remove {
            result.delete.push(path.clone());
        }
        if let Some(conflict) = conflict {
            result.conflicts.push(conflict);
        }
    }
    Ok(result)
}

/// Apply the unambiguous parts of a plan; conflicts require manual resolution.
pub fn apply(root: &Path, target: &str, plan: &MergePlan, force: bool) -> CoreResult<MergePlan> {
    if !plan.conflicts.is_empty() && !force {
        return Err(CoreError::new(
            "ASSET_MERGE_CONFLICT",
            format!("有 {} 个资产冲突，解决后再合并（或 --force 只应用无歧义部分）", plan.conflicts.len()),
        )
        .with_steps(vec![
            "查看冲突: gitmove asset merge --json 的 conflicts 字段".to_string(),
            "逐个决定后手动恢复: gitmove asset restore <snapshot> --target <name>".to_string(),
        ]));
    }

    let repo = asset::load_targets(root)
        .into_iter()
        .find(|item| item.name == target)
        .ok_or_else(|| CoreError::new("ASSET_NO_TARGET", format!("没有备份目标: {target}")))?;
    let password = snapshot_password(target, root)?;
    let restic = asset::restic_path().ok_or_else(|| CoreError::new("RESTIC_MISSING", "restic 不在 PATH"))?;

    let restore_from = |snapshot: &str, paths: &[String]| -> CoreResult<()> {
        if paths.is_empty() {
            return Ok(());
        }
        let mut command = Command::new(&restic);
        command.arg("-r").arg(&repo.repo);
        if let Some((kind, value)) = &password {
            if kind == "env" {
                command.env("RESTIC_PASSWORD", value);
            } else {
                command.arg("--password-file").arg(value);
            }
        }
        command.args(["restore", snapshot, "--target", &root.to_string_lossy()]);
        for path in paths {
            command.arg("--include").arg(format!("/{path}"));
        }
        let output = command.output()?;
        if !output.status.success() {
            return Err(CoreError::new(
                "ASSET_RESTORE_FAILED",
                String::from_utf8_lossy(&output.stderr).trim().to_string(),
            ));
        }
        Ok(())
    };

    restore_from(&plan.theirs, &plan.apply_from_theirs)?;
    for path in &plan.delete {
        let file = root.join(path);
        let _ = std::fs::remove_file(&file);
    }
    Ok(plan.clone())
}
