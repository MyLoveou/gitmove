
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::workspace;

#[derive(Debug, Clone, Serialize)]
pub struct DiffPayload {
    pub member: String,
    pub path: String,
    pub diff: String,
    pub untracked: bool,
    pub truncated: bool,
}

const MAX_CHARS: usize = 200_000;

fn repo_for(root: &Path, member: &str) -> CoreResult<PathBuf> {
    if member == "main" || member.is_empty() {
        return Ok(root.to_path_buf());
    }
    let (_, members, _) = workspace::load(root)?;
    members
        .into_iter()
        .find(|item| item.name == member)
        .map(|item| item.path)
        .ok_or_else(|| CoreError::new("MEMBER_NOT_FOUND", format!("没有成员: {member}")))
}

fn clip(text: String) -> (String, bool) {
    if text.chars().count() <= MAX_CHARS {
        return (text, false);
    }
    (text.chars().take(MAX_CHARS).collect(), true)
}

/// Working-tree diff for one path (untracked files get a synthetic new-file diff).
pub fn working(root: &Path, member: Option<&str>, path: &str) -> CoreResult<DiffPayload> {
    let member = member.unwrap_or("main");
    let repo = repo_for(root, member)?;
    let status = git::run_allow_fail(&repo, &["status", "--porcelain", "--", path]).unwrap_or_default();
    let untracked = status.lines().any(|line| line.starts_with("??"));

    if untracked {
        let file = repo.join(path);
        let content = std::fs::read_to_string(&file).unwrap_or_else(|_| "（二进制或无法读取）".to_string());
        let mut diff = format!("--- /dev/null\n+++ b/{path}\n");
        for line in content.lines().take(2000) {
            diff.push('+');
            diff.push_str(line);
            diff.push('\n');
        }
        let (text, truncated) = clip(diff);
        return Ok(DiffPayload {
            member: member.to_string(),
            path: path.to_string(),
            diff: text,
            untracked,
            truncated,
        });
    }

    let raw = git::run(&repo, &["diff", "--no-color", "--no-ext-diff", "--", path])?;
    let (text, truncated) = clip(raw);
    Ok(DiffPayload {
        member: member.to_string(),
        path: path.to_string(),
        diff: text,
        untracked,
        truncated,
    })
}

/// Diff of one path inside a commit.
pub fn commit_diff(root: &Path, member: Option<&str>, sha: &str, path: &str) -> CoreResult<DiffPayload> {
    let member = member.unwrap_or("main");
    let repo = repo_for(root, member)?;
    let raw = git::run(&repo, &["show", "--no-color", "--no-ext-diff", "--format=", sha, "--", path])?;
    let (text, truncated) = clip(raw);
    Ok(DiffPayload {
        member: member.to_string(),
        path: path.to_string(),
        diff: text,
        untracked: false,
        truncated,
    })
}
