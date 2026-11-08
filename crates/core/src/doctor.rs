
use std::path::Path;

use serde::Serialize;

use crate::error::CoreResult;
use crate::{asset, deps, git, hooks, merge, workspace};

#[derive(Debug, Clone, Serialize)]
pub struct Check {
    pub id: String,
    pub level: String,
    pub title: String,
    pub detail: String,
}

fn check(id: &str, level: &str, title: impl Into<String>, detail: impl Into<String>) -> Check {
    Check {
        id: id.to_string(),
        level: level.to_string(),
        title: title.into(),
        detail: detail.into(),
    }
}

pub fn run(root: &Path) -> CoreResult<Vec<Check>> {
    let mut rows = Vec::new();

    if !git::is_repo(root) {
        rows.push(check("repo", "error", "不是 git 仓库", root.display().to_string()));
        return Ok(rows);
    }
    rows.push(check("repo", "ok", "git 仓库", root.display().to_string()));

    match workspace::load(root) {
        Ok((_, members, _)) => {
            for member in &members {
                if !member.path.exists() {
                    rows.push(check("member", "error", format!("成员缺失: {}", member.name), member.path.display().to_string()));
                } else if git::is_dirty(&member.path) {
                    rows.push(check("member", "warn", format!("成员有未提交改动: {}", member.name), member.path.display().to_string()));
                }
            }
            rows.push(check("member", "ok", "成员检查", format!("{} 个成员", members.len())));
        }
        Err(err) => rows.push(check("member", "error", "工作区无法加载", err.message)),
    }

    if let Ok(raw) = std::fs::read_to_string(root.join("workspace.lock.toml")) {
        if let Ok(parsed) = toml::from_str::<toml::Value>(&raw) {
            if let Some(items) = parsed.get("member").and_then(|value| value.as_array()) {
                for item in items {
                    let name = item.get("name").and_then(|value| value.as_str()).unwrap_or_default();
                    let commit = item.get("commit").and_then(|value| value.as_str()).unwrap_or_default();
                    if let Ok((_, members, _)) = workspace::load(root) {
                        if let Some(member) = members.iter().find(|entry| entry.name == name) {
                            if let Some(head) = git::head(&member.path) {
                                if !commit.is_empty() && !head.starts_with(commit) {
                                    rows.push(check("lock", "warn", format!("lock 漂移: {name}"), format!("lock {} / HEAD {}", &commit[..7.min(commit.len())], &head[..7.min(head.len())])));
                                }
                            }
                        }
                    }
                }
            }
        }
    } else {
        rows.push(check("lock", "warn", "没有 workspace.lock.toml", "运行 ws update 生成锁定版本"));
    }

    let targets = asset::load_targets(root);
    if targets.is_empty() {
        rows.push(check("backup", "warn", "未配置备份目标", "workspace.toml 的 [[backup.target]]"));
    } else {
        for target in &targets {
            let local = !target.repo.contains(':') && !target.repo.starts_with("s3:");
            if local && !Path::new(&target.repo).exists() {
                rows.push(check("backup", "error", format!("备份目标不可用: {}", target.name), target.repo.clone()));
            }
        }
        rows.push(check("backup", "ok", "备份目标", format!("{} 个", targets.len())));
    }

    if let Ok(guard) = asset::guard(root) {
        for row in guard.iter().take(5) {
            rows.push(check("guard", "warn", "暂存区有大文件", format!("{} ({:.1} MB)", row.path, row.mb)));
        }
    }

    if let Ok(status) = hooks::status(root) {
        let configured = status.hooks.iter().filter(|hook| hook.enabled).count();
        if configured > 0 && status.repos.iter().all(|repo| repo.events.is_empty()) {
            rows.push(check("hooks", "warn", "钩子已配置但未安装", "gitmove hook install"));
        }
    }

    if let Ok(dep_rows) = deps::status(root, false) {
        for row in dep_rows.iter().filter(|row| row.state == "outdated") {
            rows.push(check(
                "deps",
                "warn",
                format!("依赖落后: {}", row.name),
                row.message.clone(),
            ));
        }
    }

    if let Some(state) = merge::read_state(root) {
        if !state.pending.is_empty() {
            rows.push(check("merge", "error", "资产合并未完成", format!("{} 个冲突待解决", state.pending.len())));
        }
    }

    Ok(rows)
}
