# gitmove AI 集成（MCP · Skill · JSON API）

**状态**：草案（设计已写入 `docs/design/ai-integration.md`）  
**目标版本**：0.6.0（read 面） / 0.6.x（write 面）  
**依赖**：`gitmove-core` 全系、`gitmove-0.5-enhancements` 之 **F13**（错误模型 + JSON）

## 背景

AI 编码助手（Cursor Agent 等）需要代替用户执行或诊断 gitmove 操作，但当前仅有人类向 CLI/GUI：

- 无结构化机器可读输出（除 exit code）
- 无 MCP Tool 供 IDE 注册
- 无项目 Skill 指导 Agent 何时用 skip / link / vendor

竞品 repoverlay 等偏 AI 工具链，gitmove 差异化是 **per-repo 本地策略 + doctor + F13 可行动错误** — AI 面应放大这一优势。

## 目标

1. 提供 **`gitmove-mcp`** stdio 服务器（Python `mcp` SDK）
2. 提供 **MCP Resources / Prompts** 读取文档与配置上下文
3. 提供 **Cursor Skills**（`gitmove-ops`、`gitmove-mcp-setup`）
4. **CLI `--json`** 与 MCP 同构 Envelope（无 MCP 降级路径）
5. 写操作 **双门禁**：`confirm=true` + 可选 `GITMOVE_MCP_ALLOW_WRITE`

## 不交付

- 云端托管 MCP / 多用户 SaaS
- 替代 GitHub API / 远程仓管理
- MCP 暴露交互式 `sync pull` 文件级静默选择
- 任意 shell 执行工具
- Streamable HTTP（v1；留 0.7）
- AI 自动修改业务仓 `.gitignore` 或提交 gitmove 配置

## 术语

| 术语 | 含义 |
|------|------|
| **Envelope** | 统一 JSON 响应壳：`ok` / `code` / `data` / `remediation` |
| **Read tool** | 无副作用 MCP tool |
| **Write tool** | 须 `confirm=true` 的 MCP tool |
| **Resource** | MCP 只读 URI，如 `gitmove://docs/user-manual` |

## MCP Tools 契约（摘要）

完整表见 [ai-integration.md §4](../../design/ai-integration.md#4-mcp-tools-目录)。

### 只读（0.6.0）

| Tool | 必填参数 | 返回 data 要点 |
|------|----------|----------------|
| `gitmove_doctor` | — | `issues[]` 含 `code`, `remediation` |
| `gitmove_repo_summary` | — | skip/link/vendor/worktree 计数与路径 |
| `gitmove_list_projects` | — | alias, path, status |
| `gitmove_project_health` | — | 批量 doctor 行 |
| `gitmove_vendor_status` | `name?` | behind, dirty, pinned |
| `gitmove_sync_check` | — | `needs_attention[]` |
| `gitmove_explain_error` | `code` | steps, doc_anchor |
| `gitmove_capability_advise` | `scenario` | 推荐能力 + 理由 |

### 写操作（0.6.x）

| Tool | 额外门禁 |
|------|----------|
| `gitmove_apply` | `confirm=true` |
| `gitmove_skip_add` / `remove` | `confirm=true` |
| `gitmove_vendor_add` / `sync` | `confirm=true` |
| `gitmove_init` | `confirm=true` |
| `gitmove_projects_apply_all` | `confirm=true` |

## MCP Resources（0.6.0）

- `gitmove://projects/registry`
- `gitmove://repo/{path}/config`
- `gitmove://docs/user-manual`
- `gitmove://docs/workflows`
- `gitmove://errors/catalog`
- `gitmove://capability/matrix`

## Skills 交付

| Skill | 路径 | 版本 |
|-------|------|------|
| gitmove-ops | `.cursor/skills/gitmove-ops/SKILL.md` | 0.6.0（设计稿可先合入） |
| gitmove-mcp-setup | `.cursor/skills/gitmove-mcp-setup/SKILL.md` | 0.6.0 |

触发表更新：`.cursor/skills/workflow-triggers/SKILL.md`

## CLI `--json`（0.6.0 最小集）

```bash
gitmove doctor --json
gitmove projects list --json
gitmove vendor status --json
```

输出 Envelope 与 MCP 一致（`api/response.py`）。

## 验收标准

### 0.6.0

- [ ] `pip install -e ".[mcp]"` 可运行 `gitmove-mcp`
- [ ] Cursor `mcp.json` 示例可连上，至少 5 个 read tool 可调
- [ ] 失败返回 F13 结构 JSON（含 `code` + `steps`）
- [ ] Resources：`user-manual`、`errors/catalog` 可读
- [ ] `gitmove doctor --json` 与 MCP `gitmove_doctor` 同构
- [ ] Skills：`gitmove-ops`、`gitmove-mcp-setup` 合入仓库
- [ ] 单元测试：`api/response` + tool handler（mock 业务层）；覆盖率纳入门禁
- [ ] README「AI / MCP 集成」章节

### 0.6.x

- [ ] Write tools + `GITMOVE_MCP_ALLOW_WRITE` 文档化
- [ ] MCP Prompts ≥ 3 个
- [ ] 写工具无 `confirm` 时返回 `CONFIRM_REQUIRED` 错误码

## 开放问题

| ID | 问题 | 建议 |
|----|------|------|
| Q-A1 | 0.6.0 是否包含 write tools？ | **否**，先 read + `--json` |
| Q-A2 | 默认是否设 `GITMOVE_MCP_ALLOW_WRITE=0`？ | **是** |
| Q-A3 | Skill 放仓库还是仅文档？ | **仓库 `.cursor/skills/` vendoring** |

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-29 | 草案：MCP/Skill/JSON API 需求 + 设计文档 |
