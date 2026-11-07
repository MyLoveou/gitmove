
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::error::{CoreError, CoreResult};
use crate::paths;
use crate::workspace;

/// `post-pull` 只由 `sync pull` 在拉取成功后调用。Git 没有这个钩子文件，
/// 快进和变基也不会稳定地走 `post-merge`，所以不要把它写进 `.git/hooks`。
pub const EVENTS: [&str; 4] = ["pre-commit", "post-commit", "pre-push", "post-pull"];
const GIT_EVENTS: [&str; 3] = ["pre-commit", "post-commit", "pre-push"];
const BEGIN: &str = "# >>> gitmove hooks >>>";
const END: &str = "# <<< gitmove hooks <<<";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Entry {
    event: String,
    command: String,
    #[serde(default = "default_true")]
    blocking: bool,
    #[serde(default = "default_true")]
    enabled: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct File {
    #[serde(default)]
    hook: Vec<Entry>,
}

#[derive(Debug, Clone, Serialize)]
pub struct HookDef {
    pub event: String,
    pub command: String,
    pub blocking: bool,
    pub enabled: bool,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct HookRun {
    pub event: String,
    pub command: String,
    pub ok: bool,
    pub code: i32,
    pub output: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RepoInstall {
    pub repo: String,
    pub path: String,
    pub events: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct HookStatus {
    pub global_config: String,
    pub workspace_config: String,
    pub hooks: Vec<HookDef>,
    pub repos: Vec<RepoInstall>,
    pub scripts: Vec<ScriptPreview>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScriptPreview {
    pub repo: String,
    pub event: String,
    pub text: String,
}

pub fn global_path() -> PathBuf {
    paths::home_dir().join(".gitmove").join("hooks.toml")
}

pub fn workspace_path(root: &Path) -> PathBuf {
    root.join(".gitmove").join("hooks.toml")
}

fn read_file(path: &Path) -> Vec<Entry> {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    toml::from_str::<File>(&raw).map(|file| file.hook).unwrap_or_default()
}

fn write_file(path: &Path, entries: &[Entry]) -> CoreResult<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File { hook: entries.to_vec() };
    let text = toml::to_string_pretty(&file).map_err(|err| CoreError::new("HOOK_CONFIG_INVALID", err.to_string()))?;
    std::fs::write(path, text)?;
    Ok(())
}

/// Global hooks first, workspace hooks override entries with the same event+command.
pub fn load(root: &Path) -> Vec<HookDef> {
    let mut merged: Vec<HookDef> = Vec::new();
    for (path, source) in [(global_path(), "global"), (workspace_path(root), "workspace")] {
        for entry in read_file(&path) {
            if !EVENTS.contains(&entry.event.as_str()) || entry.command.trim().is_empty() {
                continue;
            }
            merged.retain(|item| !(item.event == entry.event && item.command == entry.command));
            merged.push(HookDef {
                event: entry.event,
                command: entry.command,
                blocking: entry.blocking,
                enabled: entry.enabled,
                source: source.to_string(),
            });
        }
    }
    merged
}

pub fn add(root: &Path, event: &str, command: &str, blocking: bool, global: bool) -> CoreResult<()> {
    if !EVENTS.contains(&event) {
        return Err(CoreError::new("HOOK_EVENT_UNKNOWN", format!("未知事件: {event}")));
    }
    if command.trim().is_empty() {
        return Err(CoreError::new("HOOK_COMMAND_EMPTY", "命令不能为空"));
    }
    let path = if global { global_path() } else { workspace_path(root) };
    let mut entries = read_file(&path);
    entries.retain(|entry| !(entry.event == event && entry.command == command));
    entries.push(Entry {
        event: event.to_string(),
        command: command.to_string(),
        blocking,
        enabled: true,
    });
    write_file(&path, &entries)
}

pub fn remove(root: &Path, event: &str, command: &str, global: bool) -> CoreResult<()> {
    let path = if global { global_path() } else { workspace_path(root) };
    let mut entries = read_file(&path);
    entries.retain(|entry| !(entry.event == event && entry.command == command));
    write_file(&path, &entries)
}

pub fn set_enabled(root: &Path, event: &str, command: &str, enabled: bool, global: bool) -> CoreResult<()> {
    let path = if global { global_path() } else { workspace_path(root) };
    let mut entries = read_file(&path);
    let mut found = false;
    for entry in entries.iter_mut() {
        if entry.event == event && entry.command == command {
            entry.enabled = enabled;
            found = true;
        }
    }
    if !found {
        return Err(CoreError::new("HOOK_NOT_FOUND", "没有该钩子"));
    }
    write_file(&path, &entries)
}

fn run_command(root: &Path, command: &str) -> (bool, i32, String) {
    #[cfg(windows)]
    let mut shell = {
        let mut cmd = Command::new("cmd");
        cmd.args(["/C", command]);
        cmd
    };
    #[cfg(not(windows))]
    let mut shell = {
        let mut cmd = Command::new("sh");
        cmd.args(["-c", command]);
        cmd
    };
    match shell.current_dir(root).output() {
        Ok(output) => {
            let code = output.status.code().unwrap_or(-1);
            let mut text = String::from_utf8_lossy(&output.stdout).to_string();
            text.push_str(&String::from_utf8_lossy(&output.stderr));
            (output.status.success(), code, text)
        }
        Err(err) => (false, -1, err.to_string()),
    }
}

fn active(root: &Path, event: &str) -> Vec<HookDef> {
    load(root)
        .into_iter()
        .filter(|hook| hook.event == event && hook.enabled)
        .collect()
}

pub fn run(root: &Path, event: &str) -> CoreResult<Vec<HookRun>> {
    let mut results = Vec::new();
    for hook in active(root, event) {
        let (ok, code, output) = run_command(root, &hook.command);
        let trimmed: String = output.chars().take(4000).collect();
        results.push(HookRun {
            event: hook.event.clone(),
            command: hook.command.clone(),
            ok,
            code,
            output: trimmed.clone(),
        });
        if !ok && hook.blocking {
            return Err(CoreError::new(
                "HOOK_FAILED",
                format!("{} 钩子失败（exit {code}）: {}", hook.event, hook.command),
            )
            .with_steps(vec![
                if trimmed.trim().is_empty() { "（命令无输出）".to_string() } else { trimmed.trim().to_string() },
                format!("跳过办法: gitmove hook run {event} --no-block"),
            ]));
        }
    }
    Ok(results)
}

pub fn run_advisory(root: &Path, event: &str) -> CoreResult<Vec<HookRun>> {
    let mut results = Vec::new();
    for hook in active(root, event) {
        let (ok, code, output) = run_command(root, &hook.command);
        results.push(HookRun {
            event: hook.event.clone(),
            command: hook.command.clone(),
            ok,
            code,
            output: output.chars().take(4000).collect(),
        });
    }
    Ok(results)
}

fn script_for(root: &Path, event: &str) -> String {
    let exe = std::env::current_exe()
        .map(|value| value.to_string_lossy().to_string())
        .unwrap_or_else(|_| "gitmove-core".to_string());
    format!(
        "{BEGIN}\n\"{exe}\" -C \"{}\" hook run {event} || exit 1\n{END}\n",
        root.to_string_lossy()
    )
}

fn hook_file(repo: &Path, event: &str) -> PathBuf {
    repo.join(".git").join("hooks").join(event)
}

fn write_block(repo: &Path, event: &str, block: &str) -> CoreResult<()> {
    let path = hook_file(repo, event);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut text = std::fs::read_to_string(&path).unwrap_or_default();
    if text.trim().is_empty() {
        text = "#!/bin/sh\n".to_string();
    }
    if let (Some(start), Some(end)) = (text.find(BEGIN), text.find(END)) {
        let end = end + END.len();
        text = format!("{}{}{}", &text[..start], block, &text[end..]);
    } else {
        if !text.ends_with('\n') {
            text.push('\n');
        }
        text.push_str(block);
    }
    std::fs::write(&path, text)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755));
    }
    Ok(())
}

fn remove_block(repo: &Path, event: &str) -> CoreResult<()> {
    let path = hook_file(repo, event);
    if !path.is_file() {
        return Ok(());
    }
    let text = std::fs::read_to_string(&path)?;
    if let (Some(start), Some(end)) = (text.find(BEGIN), text.find(END)) {
        let end = end + END.len();
        let mut cleaned = format!("{}{}", &text[..start], &text[end..]);
        if cleaned.trim() == "#!/bin/sh" || cleaned.trim().is_empty() {
            let _ = std::fs::remove_file(&path);
        } else {
            cleaned = cleaned.trim_end().to_string() + "\n";
            std::fs::write(&path, cleaned)?;
        }
    }
    Ok(())
}

fn repos(root: &Path, members: bool) -> Vec<(String, PathBuf)> {
    let mut rows = vec![("main".to_string(), root.to_path_buf())];
    if members {
        if let Ok((_, list, _)) = workspace::load(root) {
            for member in list {
                if member.path.join(".git").is_dir() {
                    rows.push((member.name, member.path));
                }
            }
        }
    }
    rows.into_iter()
        .filter(|(_, path)| path.join(".git").is_dir())
        .collect()
}

fn installed_events(repo: &Path) -> Vec<String> {
    GIT_EVENTS
        .iter()
        .filter(|event| {
            std::fs::read_to_string(hook_file(repo, event))
                .map(|text| text.contains(BEGIN))
                .unwrap_or(false)
        })
        .map(|event| event.to_string())
        .collect()
}

/// Install hook blocks for the selected events (default: events with enabled hooks).
pub fn install(root: &Path, events: &[String], members: bool) -> CoreResult<HookStatus> {
    if !root.join(".git").is_dir() {
        return Err(CoreError::new("NOT_A_REPO", "不是 git 仓库（缺少 .git）"));
    }
    let chosen: Vec<String> = if events.is_empty() {
        let mut derived: Vec<String> = load(root)
            .into_iter()
            .filter(|hook| hook.enabled)
            .map(|hook| hook.event)
            .collect();
        derived.sort();
        derived.dedup();
        if derived.is_empty() {
            return Err(CoreError::new(
                "HOOK_NOTHING_CONFIGURED",
                "没有启用的钩子；先添加命令，或显式传 --event",
            ));
        }
        derived
    } else {
        events
            .iter()
            .filter(|event| EVENTS.contains(&event.as_str()))
            .cloned()
            .collect()
    };
    for (_, path) in repos(root, members) {
        for event in &chosen {
            if !GIT_EVENTS.contains(&event.as_str()) {
                continue;
            }
            write_block(&path, event, &script_for(root, event))?;
        }
    }
    status(root)
}

pub fn uninstall(root: &Path, events: &[String], members: bool) -> CoreResult<HookStatus> {
    let chosen: Vec<String> = if events.is_empty() {
        GIT_EVENTS.iter().map(|event| event.to_string()).collect()
    } else {
        events
            .iter()
            .filter(|event| GIT_EVENTS.contains(&event.as_str()))
            .cloned()
            .collect()
    };
    for (_, path) in repos(root, members) {
        for event in &chosen {
            remove_block(&path, event)?;
        }
    }
    status(root)
}

pub fn status(root: &Path) -> CoreResult<HookStatus> {
    let mut repo_rows = Vec::new();
    let mut scripts = Vec::new();
    for (name, path) in repos(root, true) {
        repo_rows.push(RepoInstall {
            repo: name.clone(),
            path: path.to_string_lossy().to_string(),
            events: installed_events(&path),
        });
        if name == "main" {
            for event in GIT_EVENTS {
                scripts.push(ScriptPreview {
                    repo: name.clone(),
                    event: event.to_string(),
                    text: script_for(root, event),
                });
            }
        }
    }
    Ok(HookStatus {
        global_config: global_path().to_string_lossy().to_string(),
        workspace_config: workspace_path(root).to_string_lossy().to_string(),
        hooks: load(root),
        repos: repo_rows,
        scripts,
    })
}
