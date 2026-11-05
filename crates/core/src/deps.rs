use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::error::CoreResult;

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
