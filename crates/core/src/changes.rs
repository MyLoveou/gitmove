use std::path::Path;

use serde::Serialize;

use crate::error::CoreResult;
use crate::git;
use crate::workspace;

#[derive(Debug, Clone, Serialize)]
pub struct ChangeRow {
    pub member: String,
    pub code: String,
    pub path: String,
}

fn parse(repo: &Path, member: &str) -> Vec<ChangeRow> {
    let mut rows = Vec::new();
    let Some(raw) = git::run_allow_fail(repo, &["status", "--porcelain", "-z"]) else {
        return rows;
    };
    for record in raw.split('\0') {
        if record.len() < 4 {
            continue;
        }
        let code = record[..2].trim().to_string();
        let path = record[3..].to_string();
        if path.is_empty() {
            continue;
        }
        rows.push(ChangeRow { member: member.to_string(), code, path });
    }
    rows
}

/// Working-tree changes for the workspace root plus every member.
pub fn status(root: &Path) -> CoreResult<Vec<ChangeRow>> {
    let mut rows = parse(root, "main");
    if let Ok((_, members, _)) = workspace::load(root) {
        for member in members {
            if member.path == root {
                continue;
            }
            if member.path.exists() && git::is_repo(&member.path) {
                rows.extend(parse(&member.path, &member.name));
            }
        }
    }
    Ok(rows)
}

fn member_path(root: &Path, name: &str) -> Option<std::path::PathBuf> {
    let (_, members, _) = workspace::load(root).ok()?;
    members
        .into_iter()
        .find(|item| item.name == name)
        .map(|item| item.path)
}

/// Discard selected changes: tracked files are restored from HEAD, untracked removed.
pub fn discard(root: &Path, selections: &[(String, String)]) -> CoreResult<Vec<String>> {
    let mut done = Vec::new();
    for (member, path) in selections {
        let repo = if member == "main" { root.to_path_buf() } else { match member_path(root, member) { Some(p) => p, None => continue } };
        let untracked = git::run_allow_fail(&repo, &["ls-files", "--error-unmatch", path]).is_none();
        if untracked {
            let target = repo.join(path);
            if target.is_file() {
                let _ = std::fs::remove_file(&target);
            }
        } else {
            let _ = git::run(&repo, &["checkout", "--", path]);
        }
        done.push(format!("{member}:{path}"));
    }
    Ok(done)
}

/// Commit only the selected files (member:path), plus the main repo selection.
pub fn commit_paths(
    root: &Path,
    message: &str,
    selections: &[(String, String)],
) -> CoreResult<crate::revision::CommitOutcome> {
    let mut main_paths: Vec<String> = Vec::new();
    let mut member_map: std::collections::BTreeMap<String, Vec<String>> = std::collections::BTreeMap::new();
    for (member, path) in selections {
        if member == "main" {
            main_paths.push(path.clone());
        } else {
            member_map.entry(member.clone()).or_default().push(path.clone());
        }
    }
    crate::revision::commit_paths(root, message, &main_paths, &member_map)
}
