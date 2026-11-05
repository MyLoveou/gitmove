use std::path::Path;

use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::scan;

#[derive(Debug, Clone, Serialize)]
pub struct AuditRow {
    pub alias: String,
    pub path: String,
    pub exists: bool,
    pub status: String,
    pub tracked_files: u64,
    pub tracked_bytes: u64,
    pub skip_paths: u64,
    pub links: u64,
    pub vendors: u64,
    pub worktrees: u64,
    pub env_steps: u64,
    pub depot_configured: bool,
    pub depot_age_days: Option<f64>,
    pub errors: u64,
    pub warns: u64,
    pub unreadable: u64,
    pub dep_label: String,
    pub own_deps: u64,
}

/// NO_INIT means "gitmove never initialised this repo", not "no content".
pub fn project_status(path: &Path) -> String {
    if !path.exists() {
        return "MISSING".to_string();
    }
    if !git::is_repo(path) {
        return "NOT_GIT".to_string();
    }
    if !path.join(".git").join("gitmove.toml").is_file() && !path.join(".gitmove").join("config.toml").is_file()
    {
        return "NO_INIT".to_string();
    }
    "OK".to_string()
}

pub fn own_deps(root: &Path) -> u64 {
    let lock = root.join("project.lock.toml");
    let Ok(raw) = std::fs::read_to_string(lock) else {
        return 0;
    };
    let Ok(parsed) = toml::from_str::<toml::Value>(&raw) else {
        return 0;
    };
    parsed
        .get("dep")
        .and_then(|value| value.as_array())
        .map(|items| items.len() as u64)
        .unwrap_or(0)
}

pub fn audit_all() -> CoreResult<Vec<AuditRow>> {
    let entries = crate::registry::load()?;
    let mut rows = Vec::with_capacity(entries.len());
    for entry in entries {
        rows.push(audit_one(&entry.alias, &entry.path)?);
    }
    Ok(rows)
}

pub fn audit_one(alias: &str, path: &Path) -> CoreResult<AuditRow> {
    let status = project_status(path);
    let exists = path.exists();
    let mut row = AuditRow {
        alias: alias.to_string(),
        path: path.to_string_lossy().replace('\\', "/"),
        exists,
        status: status.clone(),
        tracked_files: 0,
        tracked_bytes: 0,
        skip_paths: 0,
        links: 0,
        vendors: 0,
        worktrees: 0,
        env_steps: 0,
        depot_configured: false,
        depot_age_days: None,
        errors: 0,
        warns: 0,
        unreadable: 0,
        dep_label: "—".to_string(),
        own_deps: 0,
    };

    if exists && git::is_repo(path) {
        if let Ok(summary) = scan::tracked_summary(path) {
            row.tracked_files = summary.files;
            row.tracked_bytes = summary.bytes;
            row.unreadable = summary.unreadable;
        }
        row.own_deps = own_deps(path);
    }

    match status.as_str() {
        "MISSING" => {
            row.warns = 1;
        }
        "NOT_GIT" => {
            row.warns = 1;
        }
        "NO_INIT" => {
            row.warns = 1;
        }
        _ => {}
    }
    Ok(row)
}

pub fn audit_current(root: &Path) -> CoreResult<AuditRow> {
    let alias = root
        .file_name()
        .map(|value| value.to_string_lossy().to_string())
        .unwrap_or_else(|| "workspace".to_string());
    let row = audit_one(&alias, root)?;
    if row.status == "MISSING" {
        return Err(CoreError::new("REPO_NOT_FOUND", format!("路径不存在: {}", root.display())));
    }
    Ok(row)
}
