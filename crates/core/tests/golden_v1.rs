//! 从 Python 1.x 金样里留下、和核心行为有关的三条。
//! Tk 界面那一批不迁：v2 的界面是 Electron，不再跑 customtkinter。

use std::path::{Path, PathBuf};
use std::process::Command;

use gitmove_core::asset;
use gitmove_core::policy;
use gitmove_core::scan;

fn git(dir: &Path, args: &[&str]) {
    let output = Command::new("git")
        .args(args)
        .current_dir(dir)
        .output()
        .expect("git must be installed");
    assert!(output.status.success(), "git {args:?} failed: {}", String::from_utf8_lossy(&output.stderr));
}

fn scratch(label: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "gitmove-golden-{label}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
    ));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn init_repo(dir: &Path) {
    git(dir, &["init", "-q"]);
    git(dir, &["config", "user.email", "test@example.com"]);
    git(dir, &["config", "user.name", "test"]);
}

/// quotePath 打开时 `git status` 会把中文显示成八进制。扫描必须走 `-z`，路径保持原文。
#[test]
fn chinese_path_stays_literal() {
    let dir = scratch("path");
    init_repo(&dir);
    let name = "素材/说明.txt";
    std::fs::create_dir_all(dir.join("素材")).unwrap();
    std::fs::write(dir.join(name), "内容").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-q", "-m", "add chinese"]);

    let paths = scan::tracked_paths(&dir).unwrap();
    assert!(paths.iter().any(|path| path == name), "paths were {paths:?}");
    assert!(paths.iter().all(|path| !path.contains('\\') && !path.starts_with('"')));
    let _ = std::fs::remove_dir_all(&dir);
}

/// 没有备份目标时，资产状态是空列表，而不是缺 restic 就崩溃。
#[test]
fn missing_depot_does_not_crash() {
    let dir = scratch("depot");
    init_repo(&dir);
    let status = asset::status(&dir);
    assert!(status.targets.is_empty());
    let _ = std::fs::remove_dir_all(&dir);
}

/// Windows 上成员落盘用 junction，不复制目录。
#[test]
fn junction_points_at_external_dir() {
    let dir = scratch("link");
    let external = dir.join("external");
    let link = dir.join("link");
    std::fs::create_dir_all(&external).unwrap();
    std::fs::write(external.join("marker.txt"), "from-external").unwrap();

    policy::create_link(&link, &external, "junction").unwrap();
    let text = std::fs::read_to_string(link.join("marker.txt")).unwrap();
    assert_eq!(text, "from-external");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 1.x depot：密码文件放在 Git 仓库里必须拒绝，不能拿去调 restic。
#[test]
fn password_file_inside_repo_is_rejected() {
    let dir = scratch("pass");
    init_repo(&dir);
    let secret = dir.join("restic-pass.txt");
    std::fs::write(&secret, "secret").unwrap();
    let manifest = format!(
        "version = 1\n[[backup.target]]\nname = \"disk\"\nkind = \"local\"\nrepo = \"{repo}\"\npassword_file = \"{file}\"\n",
        repo = dir.join("restic-repo").display().to_string().replace('\\', "/"),
        file = secret.display().to_string().replace('\\', "/")
    );
    std::fs::write(dir.join("workspace.toml"), manifest).unwrap();
    let outcome = asset::backup(&dir, None, None).unwrap();
    assert!(!outcome.results[0].ok);
    let message = &outcome.results[0].message;
    assert!(message.contains("密码文件不得位于 Git 仓库内"), "{message}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 1.x skip-worktree：登记之后 `ls-files -v` 以 S 标记，路径仍是原文。
#[test]
fn skip_worktree_roundtrip() {
    let dir = scratch("skip");
    init_repo(&dir);
    std::fs::write(dir.join("说明.txt"), "keep").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-q", "-m", "add"]);
    let listed = policy::skip_add(&dir, &["说明.txt".to_string()]).unwrap();
    assert!(listed.iter().any(|path| path == "说明.txt"));
    let marked = policy::skip_list(&dir).unwrap();
    assert!(marked.iter().any(|path| path == "说明.txt"), "marked {marked:?}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// 1.x guard：暂存区里超过 5MB 的文件必须被点名。
#[test]
fn guard_flags_staged_oversize() {
    let dir = scratch("guard");
    init_repo(&dir);
    let big = vec![0_u8; 6 * 1024 * 1024];
    std::fs::write(dir.join("blob.bin"), big).unwrap();
    git(&dir, &["add", "blob.bin"]);
    let rows = asset::guard(&dir).unwrap();
    assert!(rows.iter().any(|row| row.path.replace('\\', "/") == "blob.bin"), "rows {rows:?}");
    let _ = std::fs::remove_dir_all(&dir);
}
