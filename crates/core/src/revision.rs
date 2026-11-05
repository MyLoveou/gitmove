use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};

use chrono::Utc;
use rusqlite::{Connection, OptionalExtension, params};
use serde::Serialize;

use crate::error::{CoreError, CoreResult};
use crate::git;
use crate::paths;

#[derive(Debug, Clone, Serialize)]
pub struct RevisionMember {
    pub member: String,
    pub commit: String,
    pub dirty: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Revision {
    pub id: i64,
    pub status: String,
    pub git_commit: Option<String>,
    pub snapshot: Option<String>,
    pub message: String,
    pub created_at: String,
    pub branch: Option<String>,
    pub parents: Vec<i64>,
    pub members: Vec<RevisionMember>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CommitOutcome {
    pub revision: i64,
    pub git_commit: Option<String>,
    pub members_committed: Vec<String>,
    pub dirty_members: Vec<String>,
    pub trailer_written: bool,
    pub assets: Vec<crate::asset::TargetResult>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CheckoutOutcome {
    pub revision: i64,
    pub main_commit: Option<String>,
    pub members: Vec<String>,
}

pub(crate) fn connect(workspace: &Path) -> CoreResult<Connection> {
    let index = paths::index_path(workspace);
    if let Some(parent) = index.parent() {
        std::fs::create_dir_all(parent)?;
    }
    if let Some(parent) = index.parent() {
        let ignore = parent.join(".gitignore");
        if !ignore.is_file() {
            std::fs::write(&ignore, "index.sqlite\ncommit-gate.json\n")?;
        }
    }
    let conn = Connection::open(index)?;
    ensure_schema(&conn)?;
    Ok(conn)
}

fn ensure_schema(conn: &Connection) -> CoreResult<()> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS revision(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'pending',
            git_commit TEXT,
            snapshot TEXT,
            env_hash TEXT,
            deps_json TEXT,
            message TEXT,
            created_at TEXT,
            branch TEXT
        );
        CREATE TABLE IF NOT EXISTS revision_member(
            revision_id INTEGER NOT NULL,
            member TEXT NOT NULL,
            commit_sha TEXT,
            dirty INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(revision_id, member)
        );
        CREATE TABLE IF NOT EXISTS asset_snapshot(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            files INTEGER NOT NULL DEFAULT 0,
            bytes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            revision_id INTEGER,
            UNIQUE(target, snapshot_id)
        );
        CREATE TABLE IF NOT EXISTS revision_parent(
            revision_id INTEGER NOT NULL,
            parent_id INTEGER NOT NULL,
            PRIMARY KEY(revision_id, parent_id)
        );
        "#,
    )?;
    Ok(())
}

/// Reserve an id before creating the commit, so the trailer can reference it.
fn reserve(conn: &Connection) -> CoreResult<i64> {
    conn.execute(
        "INSERT INTO revision(status, created_at) VALUES ('pending', ?1)",
        params![Utc::now().to_rfc3339()],
    )?;
    Ok(conn.last_insert_rowid())
}

fn discard(conn: &Connection, id: i64) {
    let _ = conn.execute("DELETE FROM revision WHERE id = ?1", params![id]);
}

fn record_members(conn: &Connection, id: i64, members: &[(String, String, bool)]) -> CoreResult<()> {
    for (name, commit, dirty) in members {
        conn.execute(
            "INSERT OR REPLACE INTO revision_member(revision_id, member, commit_sha, dirty)
             VALUES (?1, ?2, ?3, ?4)",
            params![id, name, commit, if *dirty { 1 } else { 0 }],
        )?;
    }
    Ok(())
}

fn fingerprint(root: &Path, dirty: &[String]) -> String {
    let mut hasher = DefaultHasher::new();
    for name in dirty {
        name.hash(&mut hasher);
    }
    if let Ok((_, members, _)) = crate::workspace::load(root) {
        for member in members {
            git::head(&member.path).unwrap_or_default().hash(&mut hasher);
        }
    }
    format!("{:x}", hasher.finish())
}

fn gate_path(workspace: &Path) -> PathBuf {
    workspace.join(".gitmove").join("commit-gate.json")
}

#[derive(Serialize, serde::Deserialize, Default)]
struct CommitGate {
    fingerprint: String,
    members: Vec<String>,
}

fn read_gate(workspace: &Path) -> Option<CommitGate> {
    let raw = std::fs::read_to_string(gate_path(workspace)).ok()?;
    serde_json::from_str(&raw).ok()
}

fn write_gate(workspace: &Path, gate: &CommitGate) -> CoreResult<()> {
    let path = gate_path(workspace);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(gate).unwrap())?;
    Ok(())
}

fn clear_gate(workspace: &Path) {
    let _ = std::fs::remove_file(gate_path(workspace));
}

fn commit_one(workspace: &Path, message: &str) -> CoreResult<String> {
    git::run(workspace, &["add", "-A"])?;
    let status = git::run_allow_fail(workspace, &["status", "--porcelain"]).unwrap_or_default();
    if status.trim().is_empty() {
        return Err(CoreError::new("NOTHING_TO_COMMIT", "没有可提交的改动"));
    }
    git::run(workspace, &["commit", "-m", message])?;
    git::head(workspace).ok_or_else(|| CoreError::new("GIT_FAILED", "提交后无法读取 HEAD"))
}

/// Commit the main repo (ADR-0014: first attempt rejects dirty members, second allows).
pub fn commit(
    workspace: &Path,
    message: &str,
    include_members: bool,
    strict: bool,
    with_assets: bool,
) -> CoreResult<CommitOutcome> {
    let conn = connect(workspace)?;
    let dirty = crate::workspace::dirty_members(workspace)?;
    let mut gate_armed = false;

    if !dirty.is_empty() && !include_members {
        let fp = fingerprint(workspace, &dirty);
        if strict {
            return Err(CoreError::new(
                "DIRTY_MEMBERS",
                format!("成员有未提交改动（--strict）: {}", dirty.join(", ")),
            )
            .with_steps(vec![
                "gitmove commit --members".to_string(),
                "或 gitmove member commit <name>".to_string(),
            ]));
        }
        match read_gate(workspace) {
            Some(gate) if gate.fingerprint == fp => gate_armed = true,
            _ => {
                write_gate(workspace, &CommitGate { fingerprint: fp, members: dirty.clone() })?;
                return Err(CoreError::new(
                    "DIRTY_MEMBERS",
                    format!("成员有未提交改动: {}", dirty.join(", ")),
                )
                .with_steps(vec![
                    "一并提交成员：gitmove commit --members".to_string(),
                    "只提交某个成员：gitmove member commit <name>".to_string(),
                    "确认只提交主仓：再执行一次同样的 commit".to_string(),
                ]));
            }
        }
    }

    let id = reserve(&conn)?;
    let mut members_committed = Vec::new();

    if include_members {
        for name in &dirty {
            let (_, members, _) = crate::workspace::load(workspace)?;
            if let Some(member) = members.iter().find(|item| &item.name == name) {
                if member.path.exists() && git::is_repo(&member.path) {
                    let member_message = format!("{message} [rev {id}]");
                    if commit_one(&member.path, &member_message).is_ok() {
                        members_committed.push(name.clone());
                    }
                }
            }
        }
    }

    let trailer_message = format!("{message}\n\nGitmove-Revision: {id}");
    let main_commit = match commit_one(workspace, &trailer_message) {
        Ok(commit) => commit,
        Err(err) => {
            discard(&conn, id);
            return Err(err);
        }
    };

    let (_, members, _) = crate::workspace::load(workspace)?;
    let mut recorded = Vec::new();
    for member in &members {
        if let Some(sha) = git::head(&member.path) {
            let is_dirty = git::is_dirty(&member.path);
            recorded.push((member.name.clone(), sha, is_dirty));
        }
    }
    record_members(&conn, id, &recorded)?;

    let branch = git::run_allow_fail(workspace, &["rev-parse", "--abbrev-ref", "HEAD"])
        .map(|value| value.trim().to_string())
        .filter(|value| value != "HEAD");

    conn.execute(
        "UPDATE revision SET status='ok', git_commit=?2, message=?3, created_at=?4, branch=?5 WHERE id=?1",
        params![id, main_commit, message, Utc::now().to_rfc3339(), branch],
    )?;
    clear_gate(workspace);

    let mut asset_results = Vec::new();
    if with_assets {
        if let Ok(outcome) = crate::asset::backup(workspace, None, Some(id)) {
            if let Some(first) = outcome.results.iter().find(|item| item.ok && item.snapshot_id.is_some()) {
                let _ = conn.execute(
                    "UPDATE revision SET snapshot = ?2 WHERE id = ?1",
                    params![id, first.snapshot_id.clone()],
                );
            }
            asset_results = outcome.results;
        }
    }

    Ok(CommitOutcome {
        revision: id,
        git_commit: Some(main_commit),
        members_committed,
        dirty_members: if gate_armed { dirty } else { Vec::new() },
        trailer_written: true,
        assets: asset_results,
    })
}

fn load_members(conn: &Connection, id: i64) -> CoreResult<Vec<RevisionMember>> {
    let mut stmt = conn
        .prepare("SELECT member, commit_sha, dirty FROM revision_member WHERE revision_id = ?1 ORDER BY member")?;
    let rows = stmt.query_map(params![id], |row| {
        Ok(RevisionMember {
            member: row.get(0)?,
            commit: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
            dirty: row.get::<_, i64>(2)? != 0,
        })
    })?;
    Ok(rows.filter_map(Result::ok).collect())
}

fn load_revision(conn: &Connection, id: i64) -> CoreResult<Revision> {
    let revision = conn
        .query_row(
            "SELECT id, status, git_commit, snapshot, message, created_at, branch FROM revision WHERE id = ?1",
            params![id],
            |row| {
                Ok(Revision {
                    id: row.get(0)?,
                    status: row.get(1)?,
                    git_commit: row.get(2)?,
                    snapshot: row.get(3)?,
                    message: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    created_at: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
                    branch: row.get(6)?,
                    parents: Vec::new(),
                    members: Vec::new(),
                })
            },
        )
        .optional()?;
    let Some(mut revision) = revision else {
        return Err(CoreError::new("REVISION_NOT_FOUND", format!("修订不存在: {id}")));
    };
    let mut parents_stmt = conn.prepare("SELECT parent_id FROM revision_parent WHERE revision_id = ?1")?;
    revision.parents = parents_stmt
        .query_map(params![id], |row| row.get::<_, i64>(0))?
        .filter_map(Result::ok)
        .collect();
    revision.members = load_members(conn, id)?;
    Ok(revision)
}

pub fn log(workspace: &Path, limit: u32) -> CoreResult<Vec<Revision>> {
    let conn = connect(workspace)?;
    let mut stmt = conn.prepare(
        "SELECT id FROM revision WHERE status='ok' ORDER BY id DESC LIMIT ?1",
    )?;
    let ids: Vec<i64> = stmt
        .query_map(params![limit], |row| row.get::<_, i64>(0))?
        .filter_map(Result::ok)
        .collect();
    ids.into_iter().map(|id| load_revision(&conn, id)).collect()
}

pub fn show(workspace: &Path, id: i64) -> CoreResult<Revision> {
    let conn = connect(workspace)?;
    load_revision(&conn, id)
}

/// Restore every member (and the main repo) to the recorded commits.
pub fn checkout(workspace: &Path, id: i64, force: bool) -> CoreResult<CheckoutOutcome> {
    let conn = connect(workspace)?;
    let revision = load_revision(&conn, id)?;

    let mut dirty = Vec::new();
    if git::is_repo(workspace) && git::is_dirty(workspace) {
        dirty.push(workspace.display().to_string());
    }
    let (_, members, _) = crate::workspace::load(workspace)?;
    for member in &members {
        if member.path.exists() && git::is_repo(&member.path) && git::is_dirty(&member.path) {
            dirty.push(member.name.clone());
        }
    }
    if !dirty.is_empty() && !force {
        return Err(CoreError::new(
            "WORKSPACE_DIRTY",
            format!("工作区有未提交改动: {}", dirty.join(", ")),
        )
        .with_steps(vec!["确认丢弃后重试: gitmove checkout <rev> --force".to_string()]));
    }

    let mut restored = Vec::new();
    if let Some(commit) = &revision.git_commit {
        if git::is_repo(workspace) {
            git::run(workspace, &["checkout", "--detach", commit])?;
        }
    }
    for member in &revision.members {
        if let Some(item) = members.iter().find(|candidate| candidate.name == member.member) {
            if item.path.exists() && git::is_repo(&item.path) && !member.commit.is_empty() {
                git::run(&item.path, &["checkout", "--detach", &member.commit])?;
                restored.push(member.member.clone());
            }
        }
    }

    Ok(CheckoutOutcome { revision: id, main_commit: revision.git_commit.clone(), members: restored })
}

/// Rebuild the index from `Gitmove-Revision:` trailers in the main repo.
pub fn rebuild(workspace: &Path) -> CoreResult<usize> {
    let conn = connect(workspace)?;
    // 0x1f separates sha/body, 0x1e separates records: robust against multi-line bodies.
    let log = git::run(workspace, &["log", "--format=%H%x1f%B%x1e"])?;
    let mut count = 0;
    for record in log.split('\u{1e}') {
        let record = record.trim_matches(|ch| ch == '\n' || ch == '\r' || ch == ' ' || ch == '\t');
        if record.is_empty() {
            continue;
        }
        let mut parts = record.splitn(2, '\u{1f}');
        let sha = parts.next().unwrap_or_default().trim();
        let body = parts.next().unwrap_or_default();
        if sha.len() != 40 || !sha.chars().all(|ch| ch.is_ascii_hexdigit()) {
            continue;
        }
        let Some(raw_id) = body
            .lines()
            .find_map(|line| line.strip_prefix("Gitmove-Revision: "))
            .map(|value| value.trim().to_string())
        else {
            continue;
        };
        let Ok(id) = raw_id.parse::<i64>() else {
            continue;
        };
        let message = body
            .lines()
            .filter(|line| !line.starts_with("Gitmove-Revision:"))
            .collect::<Vec<_>>()
            .join("\n")
            .trim()
            .to_string();
        conn.execute(
            "INSERT OR REPLACE INTO revision(id, status, git_commit, message, created_at)
             VALUES (?1, 'ok', ?2, ?3, ?4)",
            params![id, sha, message, Utc::now().to_rfc3339()],
        )?;
        count += 1;
    }
    Ok(count)
}
