use std::path::{Path, PathBuf};
use std::process::Command;

use gitmove_core::revision;

fn git(dir: &Path, args: &[&str]) -> String {
    let output = Command::new("git")
        .args(args)
        .current_dir(dir)
        .output()
        .expect("git must be installed for the test suite");
    assert!(
        output.status.success(),
        "git {:?} failed: {}",
        args,
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stdout).to_string()
}

fn temp_workspace(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "gitmove-core-test-{name}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&dir).unwrap();
    git(&dir, &["init", "-q"]);
    git(&dir, &["config", "user.email", "test@example.com"]);
    git(&dir, &["config", "user.name", "test"]);
    dir
}

#[test]
fn audit_measures_are_real() {
    let dir = temp_workspace("audit");
    std::fs::write(dir.join("a.txt"), "hello").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);

    let row = gitmove_core::audit::audit_current(&dir).unwrap();
    assert_eq!(row.status, "NO_INIT");
    assert_eq!(row.tracked_files, 1);
    assert_eq!(row.tracked_bytes, 5);
}

#[test]
fn audit_counts_chinese_paths() {
    let dir = temp_workspace("chinese");
    let nested = dir.join("素材");
    std::fs::create_dir_all(&nested).unwrap();
    std::fs::write(nested.join("第一集.txt"), "x".repeat(300)).unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);

    let row = gitmove_core::audit::audit_current(&dir).unwrap();
    assert_eq!(row.tracked_bytes, 300);
    assert_eq!(row.unreadable, 0);
}

#[test]
fn commit_writes_trailer_and_log_returns_it() {
    let dir = temp_workspace("revision");
    std::fs::write(dir.join("a.txt"), "v1").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);

    let outcome = revision::commit(&dir, "first", false, false).unwrap();
    assert_eq!(outcome.revision, 1);
    assert!(outcome.trailer_written);

    let body = git(&dir, &["log", "-1", "--format=%B"]);
    assert!(body.contains("Gitmove-Revision: 1"), "trailer missing: {body}");

    let rows = revision::log(&dir, 10).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].message, "first");
}

#[test]
fn checkout_restores_recorded_state() {
    let dir = temp_workspace("checkout");
    std::fs::write(dir.join("a.txt"), "v1").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);
    revision::commit(&dir, "first", false, false).unwrap();

    std::fs::write(dir.join("a.txt"), "v2").unwrap();
    revision::commit(&dir, "second", false, false).unwrap();

    revision::checkout(&dir, 1, true).unwrap();
    let content = std::fs::read_to_string(dir.join("a.txt")).unwrap();
    assert_eq!(content, "v1");
}

#[test]
fn rebuild_index_from_trailers() {
    let dir = temp_workspace("rebuild");
    std::fs::write(dir.join("a.txt"), "v1").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);
    revision::commit(&dir, "first", false, false).unwrap();
    std::fs::write(dir.join("a.txt"), "v2").unwrap();
    revision::commit(&dir, "second", false, false).unwrap();

    std::fs::remove_file(gitmove_core::paths::index_path(&dir)).unwrap();
    let count = revision::rebuild(&dir).unwrap();
    assert_eq!(count, 2);

    let rows = revision::log(&dir, 10).unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].message.trim(), "second");
}

#[test]
fn dirty_member_gate_rejects_once_then_allows() {
    let dir = temp_workspace("gate");
    std::fs::write(dir.join("a.txt"), "v1").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-m", "init"]);

    let member = dir.join("spec");
    std::fs::create_dir_all(&member).unwrap();
    git(&member, &["init", "-q"]);
    git(&member, &["config", "user.email", "test@example.com"]);
    git(&member, &["config", "user.name", "test"]);
    std::fs::write(member.join("s.txt"), "spec").unwrap();
    git(&member, &["add", "-A"]);
    git(&member, &["commit", "-m", "spec"]);

    std::fs::write(
        dir.join("workspace.toml"),
        "version = 1\n[workspace]\nname = \"gate\"\n\n[[member]]\nname = \"spec\"\npath = \"spec\"\nrole = \"editable\"\n",
    )
    .unwrap();
    std::fs::write(member.join("s.txt"), "spec changed").unwrap();

    let first = revision::commit(&dir, "one", false, false).unwrap_err();
    assert_eq!(first.code, "DIRTY_MEMBERS");

    let second = revision::commit(&dir, "two", false, false).unwrap();
    assert!(second.trailer_written);
    assert_eq!(second.dirty_members, vec!["spec".to_string()]);
}
