use std::path::Path;

use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::policy;

#[derive(Serialize)]
struct ExportDoc {
    version: u32,
    external_base: String,
    skip_paths: Vec<String>,
    links: Vec<policy::Link>,
    worktrees: Vec<policy::Worktree>,
    targets: Vec<TargetDoc>,
}

#[derive(Serialize)]
struct TargetDoc {
    name: String,
    kind: String,
    repo: String,
    priority: u32,
    enabled: bool,
}

/// Export policy + backup targets as a portable TOML document.
pub fn export(root: &Path) -> CoreResult<String> {
    let policy = policy::load(root);
    let targets = crate::asset::load_targets(root)
        .into_iter()
        .map(|target| TargetDoc {
            name: target.name,
            kind: target.kind,
            repo: target.repo,
            priority: target.priority,
            enabled: target.enabled,
        })
        .collect();
    let doc = ExportDoc {
        version: 1,
        external_base: policy.external_base,
        skip_paths: policy.skip_paths,
        links: policy.links,
        worktrees: policy.worktrees,
        targets,
    };
    Ok(toml::to_string_pretty(&doc).unwrap_or_default())
}

/// Import policy fields from an exported document (backup targets are printed only:
/// they name machine-specific paths and must be reviewed before use).
pub fn import(root: &Path, source: &Path) -> CoreResult<serde_json::Value> {
    if !source.is_file() {
        return Err(CoreError::new("CONFIG_NOT_FOUND", format!("配置不存在: {}", source.display())));
    }
    let raw = std::fs::read_to_string(source)?;
    let value = toml::from_str::<toml::Value>(&raw)?;
    let mut policy = policy::load(root);
    if let Some(items) = value.get("skip_paths").and_then(|item| item.as_array()) {
        policy.skip_paths = items.iter().filter_map(|item| item.as_str().map(str::to_string)).collect();
    }
    if let Some(base) = value.get("external_base").and_then(|item| item.as_str()) {
        policy.external_base = base.to_string();
    }
    if let Some(items) = value.get("links").and_then(|item| item.as_array()) {
        policy.links.clear();
        for item in items {
            policy.links.push(policy::Link {
                path: item.get("path").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                external: item.get("external").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                kind: item.get("kind").and_then(|v| v.as_str()).unwrap_or("junction").to_string(),
            });
        }
    }
    if let Some(items) = value.get("worktrees").and_then(|item| item.as_array()) {
        policy.worktrees.clear();
        for item in items {
            policy.worktrees.push(policy::Worktree {
                path: item.get("path").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
                branch: item.get("branch").and_then(|v| v.as_str()).unwrap_or_default().to_string(),
            });
        }
    }
    policy::save(root, &policy)?;
    let targets = value
        .get("targets")
        .and_then(|item| item.as_array())
        .map(|items| items.len())
        .unwrap_or(0);
    Ok(serde_json::json!({
        "skip_paths": policy.skip_paths.len(),
        "links": policy.links.len(),
        "worktrees": policy.worktrees.len(),
        "targets_in_file": targets,
        "note": "backup targets are not imported automatically (machine-specific paths)"
    }))
}
