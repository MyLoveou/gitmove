
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::error::{CoreError, CoreResult};

#[derive(Debug, Clone, Serialize)]
pub struct RenderItem {
    pub source: String,
    pub target: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct RenderReport {
    pub project: String,
    pub target: String,
    pub dry_run: bool,
    pub platforms: Vec<String>,
    pub copied: usize,
    pub skipped: usize,
    pub missing: usize,
    pub items: Vec<RenderItem>,
}

fn matches(pattern: &str, stem: &str) -> bool {
    match pattern.strip_suffix('*') {
        Some(prefix) => stem.starts_with(prefix),
        None => pattern == stem,
    }
}

fn wanted(stem: &str, include: &[String], exclude: &[String]) -> bool {
    let included = include.is_empty() || include.iter().any(|pattern| matches(pattern, stem));
    let excluded = exclude.iter().any(|pattern| matches(pattern, stem));
    included && !excluded
}

fn copy_file(source: &Path, target: &Path, force: bool, dry_run: bool, report: &mut RenderReport) {
    let relative = source.to_string_lossy().to_string();
    let destination = target.to_string_lossy().to_string();
    if target.exists() {
        if !force {
            report.skipped += 1;
            report.items.push(RenderItem {
                source: relative,
                target: destination,
                status: "skipped".to_string(),
            });
            return;
        }
    } else if dry_run {
        report.copied += 1;
        report.items.push(RenderItem {
            source: relative,
            target: destination,
            status: "would-copy".to_string(),
        });
        return;
    }
    if !dry_run {
        if let Some(parent) = target.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Err(err) = std::fs::copy(source, target) {
            report.items.push(RenderItem {
                source: relative,
                target: destination,
                status: format!("error: {err}"),
            });
            return;
        }
    }
    report.copied += 1;
    report.items.push(RenderItem {
        source: relative,
        target: destination,
        status: if dry_run { "would-copy" } else { "copied" }.to_string(),
    });
}

fn copy_dir(source: &Path, target: &Path, force: bool, dry_run: bool, report: &mut RenderReport) -> CoreResult<()> {
    if !source.is_dir() {
        report.missing += 1;
        return Ok(());
    }
    let mut entries: Vec<PathBuf> = std::fs::read_dir(source)?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .collect();
    entries.sort();
    for entry in entries {
        let name = entry.file_name().map(|value| value.to_string_lossy().to_string()).unwrap_or_default();
        let destination = target.join(&name);
        if entry.is_dir() {
            copy_dir(&entry, &destination, force, dry_run, report)?;
        } else {
            copy_file(&entry, &destination, force, dry_run, report);
        }
    }
    Ok(())
}

fn platform_dirs(platform: &str) -> (&'static str, &'static str) {
    match platform {
        "opencode" => (".opencode", "agent"),
        "dsh" => (".dsh", ""),
        _ => (".cursor", "agents"),
    }
}

pub fn render(
    spec_root: &Path,
    project: &str,
    target: &Path,
    force: bool,
    dry_run: bool,
) -> CoreResult<RenderReport> {
    let manifest = spec_root.join("projects").join(project).join("assembly.json");
    if !manifest.is_file() {
        return Err(CoreError::new(
            "ASSEMBLY_MISSING",
            format!("找不到装配单: {}", manifest.display()),
        )
        .with_steps(vec![
            "确认 --spec-root 指向规范库根目录".to_string(),
            format!("确认 projects/{project}/assembly.json 存在"),
        ]));
    }
    let raw = std::fs::read_to_string(&manifest)?;
    let parsed: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|err| CoreError::new("ASSEMBLY_INVALID", err.to_string()))?;

    let strings = |value: Option<&serde_json::Value>| -> Vec<String> {
        value
            .and_then(|item| item.as_array())
            .map(|items| items.iter().filter_map(|item| item.as_str().map(str::to_string)).collect())
            .unwrap_or_default()
    };

    let platforms = strings(parsed.get("platforms"));
    let include = strings(parsed.get("rules").and_then(|rules| rules.get("include")));
    let exclude = strings(parsed.get("rules").and_then(|rules| rules.get("exclude")));
    let skills = strings(parsed.get("skills"));
    let agents = strings(parsed.get("agents"));
    let entry = strings(parsed.get("entry"));

    let mut report = RenderReport {
        project: project.to_string(),
        target: target.to_string_lossy().to_string(),
        dry_run,
        platforms: platforms.clone(),
        ..RenderReport::default()
    };

    for platform in &platforms {
        let (dir, agent_dir) = platform_dirs(platform);
        let base = spec_root.join(dir);

        if platform != "dsh" {
            let rules = base.join("rules");
            if rules.is_dir() {
                for entry in std::fs::read_dir(&rules)?.filter_map(|item| item.ok()) {
                    let path = entry.path();
                    if !path.is_file() {
                        continue;
                    }
                    let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
                    let stem = name.split('.').next().unwrap_or_default().to_string();
                    if !wanted(&stem, &include, &exclude) {
                        continue;
                    }
                    let destination = target.join(dir).join("rules").join(&name);
                    copy_file(&path, &destination, force, dry_run, &mut report);
                }
            }
        }

        if !agent_dir.is_empty() {
            for agent in &agents {
                let path = base.join(agent_dir).join(format!("{agent}.md"));
                let destination = target.join(dir).join(agent_dir).join(format!("{agent}.md"));
                if path.is_file() {
                    copy_file(&path, &destination, force, dry_run, &mut report);
                } else {
                    report.missing += 1;
                }
            }
        }

        for skill in &skills {
            let source = base.join("skills").join(skill);
            let destination = target.join(dir).join("skills").join(skill);
            copy_dir(&source, &destination, force, dry_run, &mut report)?;
        }
    }

    for item in &entry {
        let source = spec_root.join(item);
        let destination = target.join(item);
        if source.is_dir() {
            copy_dir(&source, &destination, force, dry_run, &mut report)?;
        } else if source.is_file() {
            copy_file(&source, &destination, force, dry_run, &mut report);
        } else {
            report.missing += 1;
        }
    }

    Ok(report)
}
