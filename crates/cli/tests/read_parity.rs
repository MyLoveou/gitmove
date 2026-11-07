//! CLI `--json` 和 MCP `tools/call` 读的是同一个 core。
//! 界面走 sidecar 调同一条 CLI，所以读路径三端只有这一份数据。

use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

fn git(dir: &Path, args: &[&str]) {
    let output = Command::new("git").args(args).current_dir(dir).output().expect("git");
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
}

fn workspace() -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "gitmove-parity-{}-{}",
        std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
    ));
    std::fs::create_dir_all(&dir).unwrap();
    git(&dir, &["init", "-q"]);
    git(&dir, &["config", "user.email", "test@example.com"]);
    git(&dir, &["config", "user.name", "test"]);
    std::fs::write(dir.join("readme.txt"), "v1").unwrap();
    git(&dir, &["add", "-A"]);
    git(&dir, &["commit", "-q", "-m", "init"]);
    dir
}

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_gitmove-core")
}

#[test]
fn cli_and_mcp_see_the_same_workspace() {
    let dir = workspace();
    let cli = Command::new(bin())
        .args(["--json", "-C", &dir.to_string_lossy(), "ws", "status"])
        .output()
        .expect("cli");
    assert!(cli.status.success(), "{}", String::from_utf8_lossy(&cli.stderr));
    let envelope: serde_json::Value = serde_json::from_slice(&cli.stdout).expect("cli json");
    assert_eq!(envelope["ok"], true);
    assert_eq!(envelope["schema_version"], 1);
    let cli_members = envelope["data"]["members"].as_array().expect("members");

    let mut child = Command::new(bin())
        .args(["-C", &dir.to_string_lossy(), "mcp"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("mcp");
    let mut stdin = child.stdin.take().unwrap();
    let call = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": { "name": "gitmove_ws_status", "arguments": {} }
    });
    writeln!(stdin, "{call}").unwrap();
    drop(stdin);

    let stdout = child.stdout.take().unwrap();
    let line = BufReader::new(stdout).lines().next().unwrap().unwrap();
    let rpc: serde_json::Value = serde_json::from_str(&line).unwrap();
    let text = rpc["result"]["content"][0]["text"].as_str().expect("mcp text");
    let mcp_status: serde_json::Value = serde_json::from_str(text).unwrap();
    let mcp_members = mcp_status["members"].as_array().expect("mcp members");

    assert_eq!(cli_members.len(), mcp_members.len());
    assert_eq!(cli_members[0]["name"], mcp_members[0]["name"]);
    assert_eq!(cli_members[0]["head"], mcp_members[0]["head"]);
    let _ = std::fs::remove_dir_all(&dir);
}

fn cli_json(dir: &Path, args: &[&str]) -> serde_json::Value {
    let cwd = dir.to_string_lossy().to_string();
    let mut argv = vec!["--json".to_string(), "-C".to_string(), cwd];
    argv.extend(args.iter().map(|item| (*item).to_string()));
    let cli = Command::new(bin()).args(&argv).output().expect("cli");
    serde_json::from_slice(&cli.stdout).unwrap_or_else(|_| {
        panic!(
            "cli json failed: {}\n{}",
            String::from_utf8_lossy(&cli.stdout),
            String::from_utf8_lossy(&cli.stderr)
        )
    })
}

fn mcp_call(dir: &Path, name: &str, arguments: serde_json::Value, allow_write: bool) -> serde_json::Value {
    let mut command = Command::new(bin());
    command.args(["-C", &dir.to_string_lossy(), "mcp"]).stdin(Stdio::piped()).stdout(Stdio::piped());
    if allow_write {
        command.env("GITMOVE_MCP_ALLOW_WRITE", "1");
    }
    let mut child = command.spawn().expect("mcp");
    let mut stdin = child.stdin.take().unwrap();
    let call = serde_json::json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": { "name": name, "arguments": arguments }
    });
    writeln!(stdin, "{call}").unwrap();
    drop(stdin);
    let line = BufReader::new(child.stdout.take().unwrap()).lines().next().unwrap().unwrap();
    serde_json::from_str(&line).unwrap()
}

/// 界面 `rev.commit` / `rev.show` 走的就是这两条命令。提交结果必须同一份。
#[test]
fn cli_and_mcp_commit_then_show() {
    let dir = workspace();
    std::fs::write(dir.join("note.txt"), "changed").unwrap();
    let envelope = cli_json(&dir, &["commit", "-m", "第一集"]);
    assert_eq!(envelope["ok"], true, "{envelope}");
    let id = envelope["data"]["revision"].as_i64().unwrap();
    let head = envelope["data"]["git_commit"].as_str().unwrap().to_string();

    let rpc = mcp_call(&dir, "gitmove_rev_show", serde_json::json!({ "id": id }), false);
    let text = rpc["result"]["content"][0]["text"].as_str().unwrap();
    let shown: serde_json::Value = serde_json::from_str(text).unwrap();
    assert_eq!(shown["id"], id);
    assert_eq!(shown["git_commit"], head);
    let _ = std::fs::remove_dir_all(&dir);
}

/// 脏工作区回滚：命令行和 MCP 都拒绝，文案一致。界面对应 `rev.checkout`。
#[test]
fn cli_and_mcp_refuse_dirty_checkout() {
    let dir = workspace();
    std::fs::write(dir.join("note.txt"), "changed").unwrap();
    let committed = cli_json(&dir, &["commit", "-m", "base"]);
    assert_eq!(committed["ok"], true, "{committed}");
    let id = committed["data"]["revision"].as_i64().unwrap();
    std::fs::write(dir.join("note.txt"), "dirty").unwrap();

    let cli = cli_json(&dir, &["checkout", &id.to_string()]);
    assert_eq!(cli["ok"], false, "{cli}");
    let cli_message = cli["error"]["message"].as_str().unwrap().to_string();

    let rpc = mcp_call(
        &dir,
        "gitmove_checkout",
        serde_json::json!({ "id": id, "confirm": true, "force": false }),
        true,
    );
    let mcp_message = rpc["error"]["message"].as_str().unwrap();
    assert_eq!(cli_message, mcp_message);
    let _ = std::fs::remove_dir_all(&dir);
}

/// 没有备份目标时，界面 `asset.backup`、命令行、MCP 报同一句。
#[test]
fn cli_and_mcp_backup_without_target() {
    let dir = workspace();
    let cli = cli_json(&dir, &["asset", "backup"]);
    assert_eq!(cli["ok"], false, "{cli}");
    let cli_message = cli["error"]["message"].as_str().unwrap().to_string();
    let rpc = mcp_call(&dir, "gitmove_asset_backup", serde_json::json!({ "confirm": true }), true);
    assert_eq!(rpc["error"]["message"].as_str().unwrap(), cli_message);
    let _ = std::fs::remove_dir_all(&dir);
}

/// 主仓角色不能回推。界面 `ws.contribute` 与 MCP 报同一句。
#[test]
fn cli_and_mcp_contribute_rejects_main() {
    let dir = workspace();
    let cli = cli_json(&dir, &["ws", "contribute", "main"]);
    assert_eq!(cli["ok"], false, "{cli}");
    let cli_message = cli["error"]["message"].as_str().unwrap().to_string();
    let rpc = mcp_call(
        &dir,
        "gitmove_ws_contribute",
        serde_json::json!({ "member": "main", "confirm": true }),
        true,
    );
    assert_eq!(rpc["error"]["message"].as_str().unwrap(), cli_message);
    let _ = std::fs::remove_dir_all(&dir);
}
