
use std::path::PathBuf;
use std::process::Command;

use gitmove_core::hooks;

fn scratch() -> PathBuf {
    let dir = std::env::temp_dir().join(format!("gitmove-hooks-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    Command::new("git").current_dir(&dir).args(["init", "-q"]).status().unwrap();
    dir
}

#[test]
fn hooks_run_install_and_uninstall() {
    let root = scratch();

    assert!(hooks::load(&root).is_empty());
    hooks::add(&root, "pre-commit", "echo ok", true).unwrap();
    let defs = hooks::load(&root);
    assert_eq!(defs.len(), 1);
    assert_eq!(defs[0].event, "pre-commit");

    let results = hooks::run(&root, "pre-commit").unwrap();
    assert_eq!(results.len(), 1);
    assert!(results[0].ok);

    hooks::add(&root, "pre-commit", "exit 3", true).unwrap();
    let failed = hooks::run(&root, "pre-commit");
    assert!(failed.is_err(), "blocking failure must abort");
    assert_eq!(failed.err().unwrap().code, "HOOK_FAILED");

    let status = hooks::install(&root).unwrap();
    assert!(status.installed.contains(&"pre-commit".to_string()));
    assert!(status.installed.contains(&"pre-push".to_string()));
    let hook = std::fs::read_to_string(root.join(".git/hooks/pre-commit")).unwrap();
    assert!(hook.contains("# >>> gitmove hooks >>>"));

    let status = hooks::uninstall(&root).unwrap();
    assert!(status.installed.is_empty());
    let _ = std::fs::remove_dir_all(&root);
}
