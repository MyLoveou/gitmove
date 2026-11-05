use std::path::Path;

use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::paths;

#[derive(Debug, Clone, Serialize)]
pub struct SyncCheck {
    pub dirty: Vec<String>,
    pub ahead: u32,
    pub behind: u32,
    pub upstream: Option<String>,
}

pub fn check(root: &Path) -> CoreResult<SyncCheck> {
    let dirty = git::dirty_paths(root);
    let upstream = git::run_allow_fail(root, &["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    let ahead = git::run_allow_fail(root, &["rev-list", "--count", "@{u}..HEAD"])
        .and_then(|value| value.trim().parse::<u32>().ok())
        .unwrap_or(0);
    let behind = git::run_allow_fail(root, &["rev-list", "--count", "HEAD..@{u}"])
        .and_then(|value| value.trim().parse::<u32>().ok())
        .unwrap_or(0);
    Ok(SyncCheck { dirty, ahead, behind, upstream })
}

/// Fast-forward pull; refuses when skip-worktree files are locally modified
/// (pulling would overwrite work the user explicitly froze).
pub fn pull(root: &Path, fetch: bool) -> CoreResult<serde_json::Value> {
    if fetch {
        let _ = git::run_allow_fail(root, &["fetch", "--all", "--prune"]);
    }
    let status = check(root)?;
    if status.upstream.is_none() {
        return Err(CoreError::new("SYNC_NO_UPSTREAM", "当前分支没有上游").with_steps(vec![
            "设置上游: git branch --set-upstream-to=origin/<branch>".to_string(),
        ]));
    }
    let skip = crate::policy::load(root).skip_paths;
    let frozen_dirty: Vec<String> = status
        .dirty
        .iter()
        .filter(|path| skip.iter().any(|item| item == *path))
        .cloned()
        .collect();
    if !frozen_dirty.is_empty() {
        return Err(CoreError::new(
            "SYNC_FROZEN_DIRTY",
            format!("冻结文件本地有改动，拒绝 pull: {}", frozen_dirty.join(", ")),
        )
        .with_steps(vec!["先提交或暂存这些文件，或 gitmove skip remove 取消冻结".to_string()]));
    }
    let output = git::run(root, &["pull", "--ff-only"])?;
    let after = check(root)?;
    Ok(serde_json::json!({
        "pulled": true,
        "output": output.trim().chars().take(500).collect::<String>(),
        "ahead": after.ahead,
        "behind": after.behind,
        "upstream": after.upstream,
    }))
}

#[derive(Debug, Clone, Serialize)]
pub struct Preset {
    pub name: String,
    pub description: String,
    pub patterns: Vec<String>,
}

pub fn presets() -> Vec<Preset> {
    vec![
        Preset {
            name: "ai-runtime".to_string(),
            description: "AI 运行时目录（.cursor/.claude 等）".to_string(),
            patterns: vec![
                ".cursor".into(),
                ".claude".into(),
                ".agents".into(),
                ".opencode".into(),
                ".hermes".into(),
                "local/private".into(),
            ],
        },
        Preset {
            name: "video-media".to_string(),
            description: "视频素材/虚拟环境/构建产物".to_string(),
            patterns: vec![
                "*-venv".into(),
                "node_modules".into(),
                "out".into(),
                "**/__pycache__".into(),
                "模型".into(),
            ],
        },
    ]
}

fn config_value(root: &Path) -> toml::Value {
    let path = paths::config_path(root);
    std::fs::read_to_string(path)
        .ok()
        .and_then(|raw| toml::from_str::<toml::Value>(&raw).ok())
        .unwrap_or_else(|| toml::Value::Table(toml::map::Map::new()))
}

fn save_config(root: &Path, value: &toml::Value) -> CoreResult<()> {
    let path = root.join(".gitmove").join("config.toml");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, toml::to_string_pretty(value).unwrap_or_default())?;
    Ok(())
}

fn depot_excludes_mut(value: &mut toml::Value) -> &mut Vec<toml::Value> {
    let table = value.as_table_mut().expect("config root must be a table");
    let depot = table
        .entry("depot".to_string())
        .or_insert_with(|| toml::Value::Table(toml::map::Map::new()));
    let depot_table = depot.as_table_mut().expect("depot must be a table");
    depot_table
        .entry("excludes".to_string())
        .or_insert_with(|| toml::Value::Array(Vec::new()))
        .as_array_mut()
        .expect("excludes must be an array")
}

pub fn preset_enable(root: &Path, name: &str) -> CoreResult<Vec<String>> {
    let preset = presets()
        .into_iter()
        .find(|item| item.name == name)
        .ok_or_else(|| CoreError::new("PRESET_UNKNOWN", format!("未知预设: {name}")))?;
    let mut value = config_value(root);
    let excludes = depot_excludes_mut(&mut value);
    for pattern in &preset.patterns {
        let item = toml::Value::String(pattern.clone());
        if !excludes.contains(&item) {
            excludes.push(item);
        }
    }
    save_config(root, &value)?;
    Ok(preset.patterns)
}

pub fn preset_disable(root: &Path, name: &str) -> CoreResult<Vec<String>> {
    let preset = presets()
        .into_iter()
        .find(|item| item.name == name)
        .ok_or_else(|| CoreError::new("PRESET_UNKNOWN", format!("未知预设: {name}")))?;
    let mut value = config_value(root);
    let excludes = depot_excludes_mut(&mut value);
    excludes.retain(|item| {
        item.as_str()
            .map(|text| !preset.patterns.iter().any(|pattern| pattern == text))
            .unwrap_or(true)
    });
    save_config(root, &value)?;
    Ok(preset.patterns)
}

pub fn preset_active(root: &Path) -> Vec<String> {
    let value = config_value(root);
    let configured: Vec<String> = value
        .get("depot")
        .and_then(|depot| depot.get("excludes"))
        .and_then(|item| item.as_array())
        .map(|items| items.iter().filter_map(|item| item.as_str().map(str::to_string)).collect())
        .unwrap_or_default();
    presets()
        .into_iter()
        .filter(|preset| preset.patterns.iter().all(|pattern| configured.contains(pattern)))
        .map(|preset| preset.name)
        .collect()
}

#[derive(Debug, Clone, Serialize)]
pub struct VendorTemplate {
    pub name: String,
    pub description: String,
    pub deprecated: bool,
}

pub fn vendor_templates() -> Vec<VendorTemplate> {
    vec![
        VendorTemplate {
            name: "cursor-rules".into(),
            description: "文本规则目录（无渲染）".into(),
            deprecated: false,
        },
        VendorTemplate {
            name: "ai-spec".into(),
            description: "规范库：.spec-src vendored + 本地 render".into(),
            deprecated: false,
        },
        VendorTemplate {
            name: "cursor-spec".into(),
            description: "旧模板：由 spec 库渲染取代，勿用于新项目".into(),
            deprecated: true,
        },
    ]
}
