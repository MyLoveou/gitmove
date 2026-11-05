use std::path::Path;

use chrono::Local;
use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::workspace;

#[derive(Debug, Clone, Serialize)]
pub struct DiffOutcome {
    pub member: String,
    pub stat: String,
    pub dirty_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ContributeOutcome {
    pub member: String,
    pub branch: String,
    pub commits: u32,
    pub pushed: bool,
    pub bundle: Option<String>,
    pub message: String,
}

fn member_path(root: &Path, name: &str) -> CoreResult<std::path::PathBuf> {
    let (_, members, _) = workspace::load(root)?;
    let member = members
        .into_iter()
        .find(|item| item.name == name)
        .ok_or_else(|| CoreError::new("MEMBER_NOT_FOUND", format!("工作区没有成员: {name}")))?;
    if !workspace::is_contributable(&member.role) {
        return Err(CoreError::new(
            "MEMBER_READONLY",
            format!("成员 {name} 的角色是 {}，只有 editable 可以回推", member.role),
        ));
    }
    if !member.path.exists() || !git::is_repo(&member.path) {
        return Err(CoreError::new("MEMBER_NOT_GIT", format!("成员不是 Git 仓库: {}", member.path.display())));
    }
    Ok(member.path)
}

pub fn diff(root: &Path, name: &str) -> CoreResult<DiffOutcome> {
    let path = member_path(root, name)?;
    let (_, members, _) = workspace::load(root)?;
    let member = members.iter().find(|item| item.name == name).unwrap();
    let base = if !member.pin.is_empty() {
        member.pin.clone()
    } else if !member.track.is_empty() {
        format!("origin/{}", member.track)
    } else {
        "HEAD".to_string()
    };
    let stat = git::run_allow_fail(&path, &["diff", "--stat", &format!("{base}..HEAD")]).unwrap_or_default();
    Ok(DiffOutcome {
        member: name.to_string(),
        stat: stat.trim().to_string(),
        dirty_files: git::dirty_paths(&path),
    })
}

fn ahead_count(path: &Path, upstream: &str) -> u32 {
    git::run_allow_fail(path, &["rev-list", "--count", &format!("{upstream}..HEAD")])
        .and_then(|value| value.trim().parse::<u32>().ok())
        .unwrap_or(0)
}

/// Push a member's local edits back upstream; never resolves conflicts.
pub fn contribute(
    root: &Path,
    name: &str,
    branch: Option<String>,
    no_push: bool,
) -> CoreResult<ContributeOutcome> {
    let path = member_path(root, name)?;
    let (_, members, _) = workspace::load(root)?;
    let member = members.iter().find(|item| item.name == name).unwrap();

    let dirty = git::dirty_paths(&path);
    let upstream = if member.track.is_empty() {
        "origin/HEAD".to_string()
    } else {
        format!("origin/{}", member.track)
    };
    let ahead = ahead_count(&path, &upstream);
    if dirty.is_empty() && ahead == 0 {
        return Err(CoreError::new(
            "NOTHING_TO_CONTRIBUTE",
            format!("{name} 没有可回推的改动"),
        ));
    }

    let branch = branch.unwrap_or_else(|| {
        let project = root
            .file_name()
            .map(|value| value.to_string_lossy().to_string())
            .unwrap_or_else(|| "workspace".to_string());
        format!("contrib/{project}-{}", Local::now().format("%Y%m%d"))
    });

    if !dirty.is_empty() {
        git::run(&path, &["checkout", "-b", &branch])?;
        git::run(&path, &["add", "-A"])?;
        let message = format!("gitmove: contribute changes from {name}");
        if git::run(&path, &["commit", "-m", &message]).is_err() {
            return Err(CoreError::new("CONTRIBUTE_FAILED", "提交失败（可能没有可提交内容）"));
        }
    }

    let _ = git::run_allow_fail(&path, &["fetch", "origin"]);
    let has_upstream = git::run_allow_fail(&path, &["rev-parse", "--verify", &upstream]).is_some();
    if has_upstream {
        if git::run(&path, &["rebase", &upstream]).is_err() {
            let conflicts = git::run_allow_fail(&path, &["diff", "--name-only", "--diff-filter=U"])
                .unwrap_or_default();
            let _ = git::run_allow_fail(&path, &["rebase", "--abort"]);
            return Err(CoreError::new(
                "REBASE_CONFLICT",
                format!("rebase 冲突，已中止并保留现场；冲突文件: {conflicts}"),
            ));
        }
    }

    let commits = ahead_count(&path, &upstream);
    let mut outcome = ContributeOutcome {
        member: name.to_string(),
        branch: branch.clone(),
        commits,
        pushed: false,
        bundle: None,
        message: String::new(),
    };

    if no_push {
        outcome.message = "已本地提交（--no-push）".to_string();
        return Ok(outcome);
    }

    match git::run(&path, &["push", "-u", "origin", &branch]) {
        Ok(_) => {
            outcome.pushed = true;
            outcome.message = format!("已推送到 origin/{branch}");
        }
        Err(_) => {
            let bundle = root.join(format!("contrib-{name}-{}.bundle", Local::now().format("%Y%m%d")));
            let bundle_arg = bundle.to_string_lossy().to_string();
            git::run(&path, &["bundle", "create", &bundle_arg, "--all"]).map_err(|_| {
                CoreError::new("PUSH_FAILED", "推送失败，且无法生成 bundle")
            })?;
            outcome.bundle = Some(bundle.to_string_lossy().replace('\\', "/"));
            outcome.message = format!("推送失败，已降级为 bundle: {}", bundle.display());
        }
    }
    Ok(outcome)
}
