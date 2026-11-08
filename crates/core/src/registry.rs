use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, CoreResult};
use crate::paths;

#[derive(Debug, Clone, Deserialize, Serialize)]
struct RegistryFile {
    #[serde(default)]
    projects: Vec<RegistryProject>,
    #[serde(default)]
    settings: RegistrySettings,
}

#[derive(Debug, Clone, Deserialize, Serialize, Default)]
struct RegistrySettings {
    #[serde(default)]
    default_project: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, Default)]
struct RegistryProject {
    #[serde(default)]
    path: String,
    #[serde(default)]
    alias: String,
    #[serde(default)]
    group: String,
    #[serde(default)]
    last_used: String,
    #[serde(default)]
    notes: String,
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


fn read_file() -> RegistryFile {
    let path = paths::registry_path();
    let Ok(raw) = std::fs::read_to_string(&path) else {
        return RegistryFile { projects: Vec::new(), settings: RegistrySettings::default() };
    };
    toml::from_str(&raw).unwrap_or(RegistryFile { projects: Vec::new(), settings: RegistrySettings::default() })
}

fn write_file(file: &RegistryFile) -> CoreResult<()> {
    let path = paths::registry_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let text = toml::to_string_pretty(file)
        .map_err(|err| CoreError::new("REGISTRY_INVALID", err.to_string()))?;
    std::fs::write(path, text)?;
    Ok(())
}

fn normalize(path: &str) -> String {
    path.trim().replace('\\', "/")
}

fn derive_alias(path: &str) -> String {
    PathBuf::from(path)
        .file_name()
        .map(|value| value.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string())
}

#[derive(Debug, Clone, Serialize)]
pub struct ScanRow {
    pub path: String,
    pub alias: String,
    pub registered: bool,
}

/// Register a project directory (must be a git repository).
pub fn add(path: &str, alias: Option<&str>, group: &str, notes: &str) -> CoreResult<ProjectEntry> {
    let normalized = normalize(path);
    let root = PathBuf::from(&normalized);
    if !root.is_dir() {
        return Err(CoreError::new("PATH_MISSING", format!("目录不存在: {normalized}")));
    }
    if !root.join(".git").exists() {
        return Err(CoreError::new("NOT_A_REPO", format!("不是 git 仓库: {normalized}")));
    }
    let mut file = read_file();
    let alias_value = alias
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| derive_alias(&normalized));
    let mut saved = None;
    let mut replaced = false;
    for project in file.projects.iter_mut() {
        if normalize(&project.path) == normalized {
            project.alias = alias_value.clone();
            if !group.is_empty() {
                project.group = group.to_string();
            }
            if !notes.is_empty() {
                project.notes = notes.to_string();
            }
            replaced = true;
            saved = Some(project.clone());
            break;
        }
    }
    if !replaced {
        let project = RegistryProject {
            path: normalized.clone(),
            alias: alias_value.clone(),
            group: group.to_string(),
            notes: notes.to_string(),
            last_used: String::new(),
        };
        saved = Some(project.clone());
        file.projects.push(project);
    }
    write_file(&file)?;
    let project = saved.unwrap();
    Ok(ProjectEntry {
        alias: project.alias,
        path: PathBuf::from(&project.path),
        group: project.group,
        last_used: project.last_used,
    })
}

pub fn remove(target: &str) -> CoreResult<usize> {
    let normalized = normalize(target);
    let mut file = read_file();
    let before = file.projects.len();
    file.projects.retain(|project| {
        project.alias != target && normalize(&project.path) != normalized
    });
    let removed = before - file.projects.len();
    if removed > 0 {
        write_file(&file)?;
    }
    Ok(removed)
}

/// Find git repositories under `root` (depth-limited), skipping heavy directories.
pub fn scan(root: &str, depth: u32) -> CoreResult<Vec<ScanRow>> {
    let base = PathBuf::from(root);
    if !base.is_dir() {
        return Err(CoreError::new("PATH_MISSING", format!("目录不存在: {root}")));
    }
    let existing: Vec<String> = read_file()
        .projects
        .iter()
        .map(|project| normalize(&project.path))
        .collect();
    let mut rows = Vec::new();
    let mut stack = vec![(base.clone(), 0u32)];
    while let Some((dir, level)) = stack.pop() {
        if level > depth {
            continue;
        }
        if dir.join(".git").exists() {
            let path = dir.to_string_lossy().replace('\\', "/");
            rows.push(ScanRow {
                alias: derive_alias(&path),
                registered: existing.iter().any(|item| item == &path),
                path,
            });
            continue;
        }
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for entry in entries.filter_map(|item| item.ok()) {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            let name = entry.file_name().to_string_lossy().to_string();
            if matches!(name.as_str(), "node_modules" | "target" | "dist" | ".git" | "temp" | ".cache" | "vendor") {
                continue;
            }
            stack.push((path, level + 1));
        }
    }
    rows.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(rows)
}
