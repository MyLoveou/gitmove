use std::path::{Path, PathBuf};
use std::process::Command;

use crate::error::{CoreError, CoreResult};

/// Run git in `cwd` and return stdout (trimmed by callers when needed).
pub fn run(cwd: &Path, args: &[&str]) -> CoreResult<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .map_err(|err| CoreError::new("GIT_UNAVAILABLE", format!("无法运行 git: {err}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(CoreError::new("GIT_FAILED", format!("git {} 失败: {stderr}", args.join(" "))));
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

pub fn run_allow_fail(cwd: &Path, args: &[&str]) -> Option<String> {
    Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .ok()
        .filter(|out| out.status.success())
        .map(|out| String::from_utf8_lossy(&out.stdout).to_string())
}

pub fn is_repo(path: &Path) -> bool {
    path.join(".git").exists()
}

pub fn toplevel(path: &Path) -> CoreResult<PathBuf> {
    let out = run(path, &["rev-parse", "--show-toplevel"])?;
    let trimmed = out.trim();
    if trimmed.is_empty() {
        return Err(CoreError::new("REPO_NOT_GIT", format!("不是 Git 仓库: {}", path.display())));
    }
    Ok(PathBuf::from(trimmed))
}

pub fn head(cwd: &Path) -> Option<String> {
    run_allow_fail(cwd, &["rev-parse", "HEAD"]).map(|value| value.trim().to_string())
}

pub fn is_dirty(cwd: &Path) -> bool {
    run_allow_fail(cwd, &["status", "--porcelain"])
        .map(|value| !value.trim().is_empty())
        .unwrap_or(false)
}

pub fn dirty_paths(cwd: &Path) -> Vec<String> {
    run_allow_fail(cwd, &["status", "--porcelain", "-z"])
        .map(|raw| {
            raw.split('\0')
                .filter(|record| record.len() > 3)
                .map(|record| record[3..].to_string())
                .collect()
        })
        .unwrap_or_default()
}
