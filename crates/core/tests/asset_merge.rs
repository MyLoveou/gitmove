
use std::path::{Path, PathBuf};
use std::process::Command;

use gitmove_core::{asset, merge};

fn run(dir: &Path, args: &[&str]) {
    let status = Command::new("git")
        .current_dir(dir)
        .args(args)
        .status()
        .expect("git");
    assert!(status.success(), "git {args:?} failed");
}

fn write(root: &Path, name: &str, text: &str) {
    std::fs::write(root.join(name), text).unwrap();
}

fn read(root: &Path, name: &str) -> String {
    std::fs::read_to_string(root.join(name)).unwrap().trim().to_string()
}

#[test]
fn three_way_merge_resolves_per_file() {
    let has_restic = Command::new("restic")
        .arg("version")
        .output()
        .map(|out| out.status.success())
        .unwrap_or(false);
    if !has_restic {
        eprintln!("SKIP: restic not on PATH");
        return;
    }
    std::env::set_var("RESTIC_PASSWORD", "gitmove-test-pass");

    let tmp = std::env::temp_dir().join(format!("gitmove-asset-merge-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    let backup_dir = tmp.join("depot-a");

    run(&tmp, &["init", "-q"]);
    run(&tmp, &["config", "user.email", "test@example.com"]);
    run(&tmp, &["config", "user.name", "test"]);
    write(&tmp, "a.txt", "a");
    write(&tmp, "b.txt", "b");
    write(&tmp, "c.txt", "c");
    run(&tmp, &["add", "-A"]);
    run(&tmp, &["commit", "-qm", "base"]);

    let manifest = format!(
        "version = 1\n[workspace]\nname = \"t\"\n\n[[backup.target]]\nname = \"a\"\nrepo = \"{}\"\n",
        backup_dir.to_string_lossy().replace('\\', "/")
    );
    std::fs::write(tmp.join("workspace.toml"), manifest).unwrap();

    asset::init(&tmp, Some("a")).expect("init");
    asset::backup(&tmp, Some("a"), None).expect("backup base");
    let base = asset::snapshots(&tmp, 10).unwrap()[0].snapshot_id.clone();

    write(&tmp, "a.txt", "a2");
    write(&tmp, "c.txt", "c2");
    run(&tmp, &["add", "-A"]);
    run(&tmp, &["commit", "-qm", "ours"]);
    asset::backup(&tmp, Some("a"), None).expect("backup ours");
    let ours = asset::snapshots(&tmp, 10).unwrap()[0].snapshot_id.clone();

    write(&tmp, "a.txt", "a3");
    write(&tmp, "c.txt", "c");
    run(&tmp, &["add", "-A"]);
    run(&tmp, &["commit", "-qm", "theirs"]);
    asset::backup(&tmp, Some("a"), None).expect("backup theirs");
    let theirs = asset::snapshots(&tmp, 10).unwrap()[0].snapshot_id.clone();

    let plan = merge::plan(&tmp, "a", &base, &ours, &theirs).expect("plan");
    assert!(
        plan.conflicts.iter().any(|item| item.path == "a.txt"),
        "a.txt should conflict"
    );
    assert!(
        plan.merged.iter().any(|item| item.path == "c.txt" && item.action == "keep_ours"),
        "c.txt should keep ours"
    );
    assert_eq!(plan.conflicts.len(), 1, "only a.txt conflicts");

    merge::apply(&tmp, "a", &plan, true).expect("apply");
    assert_eq!(read(&tmp, "c.txt"), "c2", "c.txt restored from ours");

    let state = merge::read_state(&tmp).expect("merge state written");
    assert!(state.pending.contains(&"a.txt".to_string()));

    let state = merge::resolve(&tmp, "a.txt", "theirs").expect("resolve theirs");
    assert!(state.pending.is_empty());
    assert_eq!(read(&tmp, "a.txt"), "a3", "a.txt taken from theirs");
    assert!(merge::read_state(&tmp).is_none(), "state cleared");
    let _ = std::fs::remove_dir_all(&tmp);
}

