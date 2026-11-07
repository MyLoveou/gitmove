use std::path::{Path, PathBuf};
use std::process::Command;

use gitmove_core::workspace;

fn git(dir: &Path, args: &[&str]) -> String {
    let output = Command::new("git")
        .args(args)
        .current_dir(dir)
        .output()
        .expect("git must be installed");
    assert!(
        output.status.success(),
        "git {:?} failed: {}",
        args,
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stdout).to_string()
}

fn init_repo(dir: &Path) {
    std::fs::create_dir_all(dir).unwrap();
    git(dir, &["init", "-q"]);
    git(dir, &["config", "user.email", "test@example.com"]);
    git(dir, &["config", "user.name", "test"]);
    std::fs::write(dir.join("readme.txt"), "v1").unwrap();
    git(dir, &["add", "-A"]);
    git(dir, &["commit", "-q", "-m", "init"]);
}

fn workspace() -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "gitmove-member-branch-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    init_repo(&dir);
    init_repo(&dir.join("spec"));
    init_repo(&dir.join("lib"));
    std::fs::write(
        dir.join("workspace.toml"),
        r#"version = 1
[workspace]
name = "t"

[[member]]
name = "main"
path = "."
role = "main"

[[member]]
name = "spec"
path = "spec"
role = "editable"

[[member]]
name = "lib"
path = "lib"
role = "readonly"
"#,
    )
    .unwrap();
    dir
}

fn branch_of(dir: &Path) -> String {
    git(dir, &["rev-parse", "--abbrev-ref", "HEAD"]).trim().to_string()
}

#[test]
fn create_and_switch_one_member_leaves_the_others() {
    let root = workspace();
    let main_before = branch_of(&root);
    let lib_before = branch_of(&root.join("lib"));

    workspace::branch_create(&root, "feature/ui", Some("spec")).unwrap();
    assert_eq!(branch_of(&root.join("spec")), "feature/ui");
    assert_eq!(branch_of(&root), main_before);
    assert_eq!(branch_of(&root.join("lib")), lib_before);

    let err = workspace::branch_create(&root, "feature/ui", Some("spec")).unwrap_err();
    assert_eq!(err.code, "BRANCH_EXISTS");

    workspace::branch_switch(&root, &main_before, Some("spec")).unwrap();
    assert_eq!(branch_of(&root.join("spec")), main_before);

    std::fs::write(root.join("spec").join("dirty.txt"), "x").unwrap();
    let dirty = workspace::branch_switch(&root, "feature/ui", Some("spec")).unwrap_err();
    assert_eq!(dirty.code, "WORKSPACE_DIRTY");
    assert_eq!(branch_of(&root.join("spec")), main_before);

    let readonly = workspace::branch_create(&root, "feature/lib", Some("lib")).unwrap_err();
    assert_eq!(readonly.code, "MEMBER_READONLY");
}

#[test]
fn member_commit_does_not_move_the_main_repository() {
    let root = workspace();
    let main_head = git(&root, &["rev-parse", "HEAD"]);
    std::fs::write(root.join("spec").join("note.txt"), "change").unwrap();

    let outcome = workspace::member_commit(&root, "spec", "only spec").unwrap();
    assert_eq!(outcome.member, "spec");
    let spec_log = git(&root.join("spec"), &["log", "-1", "--format=%s"]);
    assert_eq!(spec_log.trim(), "only spec");
    assert_eq!(git(&root, &["rev-parse", "HEAD"]), main_head);

    let empty = workspace::member_commit(&root, "spec", "   ").unwrap_err();
    assert_eq!(empty.code, "MEMBER_MESSAGE_REQUIRED");
    let readonly = workspace::member_commit(&root, "lib", "nope").unwrap_err();
    assert_eq!(readonly.code, "MEMBER_READONLY");
}
