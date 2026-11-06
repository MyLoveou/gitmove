
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

use crate::error::{CoreError, CoreResult};

pub const EVENTS: [&str; 3] = ["pre-commit", "post-commit", "pre-push"];
const BEGIN: &str = "# >>> gitmove hooks >>>";
const END: &str = "# <<< gitmove hooks <<<";

#[derive(Debug, Clone, Serialize)]
pub struct HookDef {
    pub event: String,
    pub command: String,
    pub blocking: bool,
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
pub struct HookStatus {
    pub config: String,
    pub hooks: Vec<HookDef>,
    pub installed: Vec<String>,
    pub missing_command: bool,
}

pub fn config_path(root: &Path) -> PathBuf {
    root.join(".gitmove").join("hooks.toml")
}

pub fn load(root: &Path) -> Vec<HookDef> {
    let Ok(raw) = std::fs::read_to_string(config_path(root)) else {
        return Vec::new();
    };
    let Ok(parsed) = toml::from_str::<toml::Value>(&raw) else {
        return Vec::new();
    };
    let mut hooks = Vec::new();
    if let Some(items) = parsed.get("hook").and_then(|value| value.as_array()) {
        for item in items {
            let event = item.get("event").and_then(|value| value.as_str()).unwrap_or("pre-commit");
            let command = item.get("command").and_then(|value| value.as_str()).unwrap_or("");
            if command.trim().is_empty() {
                continue;
            }
            hooks.push(HookDef {
                event: event.to_string(),
                command: command.to_string(),
                blocking: item.get("blocking").and_then(|value| value.as_bool()).unwrap_or(true),
            });
        }
    }
    hooks
}

pub fn add(root: &Path, event: &str, command: &str, blocking: bool) -> CoreResult<()> {
    if !EVENTS.contains(&event) {
        return Err(CoreError::new("HOOK_EVENT_UNKNOWN", format!("未知事件: {event}")));
    }
    if command.trim().is_empty() {
        return Err(CoreError::new("HOOK_COMMAND_EMPTY", "命令不能为空"));
    }
    let path = config_path(root);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut text = std::fs::read_to_string(&path).unwrap_or_default();
    if !text.ends_with('\n') && !text.is_empty() {
        text.push('\n');
    }
    text.push_str(&format!(
        "\n[[hook]]\nevent = \"{event}\"\ncommand = \"{}\"\nblocking = {blocking}\n",
        command.replace('"', "\\\"")
    ));
    std::fs::write(path, text)?;
    Ok(())
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

/// Run every hook registered for `event`; blocking failures abort with HOOK_FAILED.
pub fn run(root: &Path, event: &str) -> CoreResult<Vec<HookRun>> {
    let mut results = Vec::new();
    for hook in load(root).into_iter().filter(|hook| hook.event == event) {
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
                "如需跳过：gitmove hook run <event> --no-block 或移除 .gitmove/hooks.toml 中的该项".to_string(),
            ]));
        }
    }
    Ok(results)
}

/// Run every hook for `event` but never abort on failure (advisory mode).
pub fn run_advisory(root: &Path, event: &str) -> CoreResult<Vec<HookRun>> {
    let mut results = Vec::new();
    for hook in load(root).into_iter().filter(|hook| hook.event == event) {
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

fn marked_block(root: &Path) -> String {
    let exe = std::env::current_exe()
        .map(|value| value.to_string_lossy().to_string())
        .unwrap_or_else(|_| "gitmove-core".to_string());
    format!(
        "{BEGIN}\n\"{exe}\" -C \"{}\" hook run pre-commit || exit 1\n{END}\n",
        root.to_string_lossy()
    )
}

fn hook_file(root: &Path, name: &str) -> PathBuf {
    root.join(".git").join("hooks").join(name)
}

fn write_block(root: &Path, name: &str, block: &str) -> CoreResult<()> {
    let path = hook_file(root, name);
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

fn remove_block(root: &Path, name: &str) -> CoreResult<()> {
    let path = hook_file(root, name);
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

/// Install git hooks that call back into `gitmove hook run <event>`.
pub fn install(root: &Path) -> CoreResult<HookStatus> {
    if !root.join(".git").is_dir() {
        return Err(CoreError::new("NOT_A_REPO", "不是 git 仓库（缺少 .git）"));
    }
    for name in ["pre-commit", "pre-push"] {
        let exe = std::env::current_exe()
            .map(|value| value.to_string_lossy().to_string())
            .unwrap_or_else(|_| "gitmove-core".to_string());
        let block = format!(
            "{BEGIN}\n\"{exe}\" -C \"{}\" hook run {name} || exit 1\n{END}\n",
            root.to_string_lossy()
        );
        write_block(root, name, &block)?;
    }
    status(root)
}

pub fn uninstall(root: &Path) -> CoreResult<HookStatus> {
    for name in ["pre-commit", "pre-push"] {
        remove_block(root, name)?;
    }
    status(root)
}

pub fn status(root: &Path) -> CoreResult<HookStatus> {
    let mut installed = Vec::new();
    for name in ["pre-commit", "pre-push"] {
        let path = hook_file(root, name);
        if let Ok(text) = std::fs::read_to_string(&path) {
            if text.contains(BEGIN) {
                installed.push(name.to_string());
            }
        }
    }
    Ok(HookStatus {
        config: config_path(root).to_string_lossy().to_string(),
        hooks: load(root),
        installed,
        missing_command: false,
    })
}
