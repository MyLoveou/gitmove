---
name: gitmove-ops
description: >-
  gitmove 本地 Git 策略：skip-worktree、link、vendor、多项目 doctor/apply。
  触发：gitmove、skip-worktree、vendor sync、.git/gitmove.toml、本地配置不提交、
  .cursor 外仓、doctor 报错修复。
---

# gitmove 操作（Agent）

> 设计文档：`docs/design/ai-integration.md`  
> 人类手册：`docs/guides/user-manual.md`

## 何时使用

- 用户要在**不改 `.gitignore`** 前提下管理本地 Git 策略
- 已追踪文件本地改不提交 → **skip-worktree**
- 目录放盘外 → **link**
- 目录内容来自另一 Git 仓 → **vendor**
- 多仓批量巡检 → **projects**

## 能力选型（先读再动）

| 需求 | 用 | 勿用 |
|------|-----|------|
| 已追踪小文件本地改 | skip | 改 gitignore |
| 整目录放盘外 | link | vendor |
| 外仓整仓挂到 `.cursor` | vendor | submodule 提交 |
| 业务仓 pull + skip 冲突 | sync pull（CLI/GUI） | 裸 `git pull` |

详细场景：`docs/guides/workflows.md`

## MCP 优先（若已配置 gitmove-mcp）

1. **只读诊断**：`gitmove_doctor` → `gitmove_repo_summary` → `gitmove_sync_check`
2. **多项目**：`gitmove_list_projects` → `gitmove_project_health`
3. **失败**：读返回 JSON 的 `code` / `steps`，或 `gitmove_explain_error`
4. **文档**：Resource `gitmove://docs/user-manual` 或 `gitmove://docs/workflows`

### 写操作规则（强制）

- **必须**向用户说明将做什么，取得同意
- MCP write tool **必须**传 `confirm: true`
- 宿主需设 `GITMOVE_MCP_ALLOW_WRITE=1` 才允许写
- **禁止**静默 `vendor remove --purge-cache` 或等价破坏性操作

## 无 MCP 时（CLI）

```bash
gitmove doctor                    # 健康检查
gitmove apply                     # 恢复 skip/link/vendor
gitmove -C <alias> doctor         # 多项目
gitmove vendor status <name>
gitmove sync check
```

实现 0.6 后优先：

```bash
gitmove doctor --json
gitmove projects list --json
```

解析 JSON 的 `steps` 字段向用户给出修复建议（与 F13 一致）。

## 硬约束

- 不修改业务仓 `.gitignore`
- 配置在 `.git/gitmove.toml`，**不提交**
- vendor 必须挂用户指定 `repo_path`（含已追踪 `.cursor`），禁止改挂替代路径
- `vendor sync` 仅 FF；失败时按 remediation 步骤处理 cache，不自动 merge

## 常见错误码（速查）

| code | 含义 | 首选修复 |
|------|------|----------|
| `SKIP_NOT_ACTIVE` | skip 未生效 | `gitmove apply` |
| `VENDOR_FF_BLOCKED` | 上游非 FF | 处理 cache 后重试 sync |
| `VENDOR_PATH_EXISTS` | 目录存在 | `vendor add --migrate` |
| `PROJECT_PATH_MISSING` | 注册路径失效 | `projects repair` |
| `REPO_NOT_INIT` | 未 init | `gitmove init` |

完整 catalog：Resource `gitmove://errors/catalog`（MCP）或 `docs/guides/user-manual.md` §10。

## 安装 MCP

见 Skill：`gitmove-mcp-setup` 或 `examples/mcp/cursor-mcp.json`
