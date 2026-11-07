
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
fn hooks_scope_install_and_toggle() {
    let root = scratch();

    assert!(hooks::load(&root).is_empty());
    hooks::add(&root, "pre-commit", "echo ok", true, false).unwrap();
    let defs = hooks::load(&root);
    assert_eq!(defs.len(), 1);
    assert_eq!(defs[0].event, "pre-commit");
    assert!(defs[0].enabled);
    assert_eq!(defs[0].source, "workspace");

    hooks::set_enabled(&root, "pre-commit", "echo ok", false, false).unwrap();
    assert!(!hooks::load(&root)[0].enabled);
    let results = hooks::run(&root, "pre-commit").unwrap();
    assert!(results.is_empty(), "disabled hook must not run");
    hooks::set_enabled(&root, "pre-commit", "echo ok", true, false).unwrap();

    let results = hooks::run(&root, "pre-commit").unwrap();
    assert_eq!(results.len(), 1);
    assert!(results[0].ok);

    hooks::add(&root, "pre-commit", "exit 3", true, false).unwrap();
    assert!(hooks::run(&root, "pre-commit").is_err(), "blocking failure aborts");
    assert_eq!(hooks::run(&root, "pre-commit").err().unwrap().code, "HOOK_FAILED");

    let status = hooks::install(&root, &[], false).unwrap();
    let main = status.repos.iter().find(|repo| repo.repo == "main").unwrap();
    assert!(main.events.contains(&"pre-commit".to_string()));
    let hook = std::fs::read_to_string(root.join(".git/hooks/pre-commit")).unwrap();
    assert!(hook.contains("# >>> gitmove hooks >>>"));

    let status = hooks::uninstall(&root, &[], false).unwrap();
    let main = status.repos.iter().find(|repo| repo.repo == "main").unwrap();
    assert!(main.events.is_empty());

    hooks::remove(&root, "pre-commit", "exit 3", false).unwrap();
    assert_eq!(hooks::load(&root).len(), 1);

    hooks::add(&root, "post-pull", "echo post-pull", false, false).unwrap();
    hooks::install(&root, &["post-pull".to_string()], false).unwrap();
    assert!(
        !root.join(".git/hooks/post-pull").exists(),
        "post-pull 由 sync pull 调用，不写 git 钩子文件"
    );

    let _ = std::fs::remove_dir_all(&root);
}
