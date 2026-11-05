use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::error::CoreResult;
use crate::paths;

#[derive(Debug, Clone, Deserialize)]
struct RegistryFile {
    #[serde(default)]
    projects: Vec<RegistryProject>,
    #[serde(default)]
    settings: RegistrySettings,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct RegistrySettings {
    #[serde(default)]
    default_project: String,
}

#[derive(Debug, Clone, Deserialize)]
struct RegistryProject {
    #[serde(default)]
    path: String,
    #[serde(default)]
    alias: String,
    #[serde(default)]
    group: String,
    #[serde(default)]
    last_used: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProjectEntry {
    pub alias: String,
    pub path: PathBuf,
    pub group: String,
    pub last_used: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProjectRow {
    pub alias: String,
    pub path: String,
    pub group: String,
    pub init: bool,
    pub status: String,
}

pub fn load() -> CoreResult<Vec<ProjectEntry>> {
    let path = paths::registry_path();
    if !path.is_file() {
        return Ok(Vec::new());
    }
    let raw = std::fs::read_to_string(&path)?;
    let parsed: RegistryFile = toml::from_str(&raw)?;
    Ok(parsed
        .projects
        .into_iter()
        .map(|entry| {
            let name = if entry.alias.trim().is_empty() {
                PathBuf::from(&entry.path)
                    .file_name()
                    .map(|value| value.to_string_lossy().to_string())
                    .unwrap_or_else(|| entry.path.clone())
            } else {
                entry.alias.clone()
            };
            ProjectEntry {
                alias: name,
                path: PathBuf::from(entry.path.replace('/', std::path::MAIN_SEPARATOR_STR)),
                group: entry.group,
                last_used: entry.last_used,
            }
        })
        .collect())
}

pub fn default_alias() -> String {
    let path = paths::registry_path();
    if !path.is_file() {
        return String::new();
    }
    std::fs::read_to_string(path)
        .ok()
        .and_then(|raw| toml::from_str::<RegistryFile>(&raw).ok())
        .map(|parsed| parsed.settings.default_project)
        .unwrap_or_default()
}

pub fn to_rows(entries: &[ProjectEntry]) -> Vec<ProjectRow> {
    entries
        .iter()
        .map(|entry| {
            let status = crate::audit::project_status(&entry.path);
            ProjectRow {
                alias: entry.alias.clone(),
                path: entry.path.to_string_lossy().replace('\\', "/"),
                group: entry.group.clone(),
                init: status == "OK",
                status,
            }
        })
        .collect()
}
