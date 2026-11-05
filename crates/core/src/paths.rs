use std::path::PathBuf;

/// `GITMOVE_HOME` wins (tests and portable installs), else `~/.gitmove`.
pub fn home_dir() -> PathBuf {
    if let Ok(value) = std::env::var("GITMOVE_HOME") {
        if !value.trim().is_empty() {
            return PathBuf::from(value);
        }
    }
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".gitmove")
}

pub fn registry_path() -> PathBuf {
    home_dir().join("projects.toml")
}

pub fn index_path(workspace: &std::path::Path) -> PathBuf {
    workspace.join(".gitmove").join("index.sqlite")
}

pub fn config_path(workspace: &std::path::Path) -> PathBuf {
    let legacy = workspace.join(".git").join("gitmove.toml");
    let current = workspace.join(".gitmove").join("config.toml");
    if current.is_file() {
        current
    } else if legacy.is_file() {
        legacy
    } else {
        current
    }
}

pub fn workspace_manifest(workspace: &std::path::Path) -> PathBuf {
    workspace.join("workspace.toml")
}

pub fn workspace_lock(workspace: &std::path::Path) -> PathBuf {
    workspace.join("workspace.lock.toml")
}
