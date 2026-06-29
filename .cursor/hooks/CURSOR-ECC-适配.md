# Cursor × ECC Hooks 适配说明

> ECC 全局 hooks：`%USERPROFILE%\.cursor\hooks\`  
> 项目 hooks：`<项目>/.cursor/hooks/`（协议与加载路径不同，勿混用）

## Cursor 强制协议

以下事件 **stdout 必须是 JSON**，不能透传 stdin：

| 事件 | 允许 | 拒绝 |
|------|------|------|
| `beforeReadFile` | `{ "permission": "allow" }` | `{ "permission": "deny", ... }` |
| `beforeShellExecution` | 同上 | 同上 |
| `beforeTabFileRead` | 同上 | 同上 |
| `preToolUse` | 同上 | 同上 |

日志、警告请写 **stderr**，不要污染 stdout。

## ECC 常见错误

```javascript
// ❌ Claude Code 风格 — Cursor 会报 invalid JSON
process.stdout.write(raw);

// ✅ Cursor
process.stdout.write(JSON.stringify({ permission: 'allow' }));
```

## 用户级 ECC hooks 修复

若 Settings → Hooks 报 `invalid JSON` 或错误路径 `~\.cursor\.cursor\hooks\`：

1. 打开 `%USERPROFILE%\.cursor\hooks.json`
2. 脚本路径应为相对 `~/.cursor/` 的 `hooks/*.mjs`，勿多写一层 `.cursor`
3. 禁用分支须输出 `{ "permission": "allow" }`，勿 `process.stdout.write(raw)`
4. 修改后重启 Cursor

## 项目级 hooks

本库默认提供轻量 `hooks.json`（stop DoD 提醒）。若项目需要 `preToolUse` 硬约束：

- 脚本须返回 `{ permission: 'allow'|'deny' }`
- 与 `~/.cursor/hooks` 勿共用 passthrough 脚本
- 在项目 `ecc-manifest.md` 记录选型

## 验证

修复后重启 Cursor，并在 Settings → Hooks 确认无红字。
