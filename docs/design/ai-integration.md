# gitmove AI 集成设计

> 版本：0.6.0（规划） · 状态：设计稿  
> 需求文档：[gitmove-ai-integration.md](../requirements/features/gitmove-ai-integration.md)

## 1. 目标

让 **Cursor / Claude Desktop / 其他 MCP 客户端** 中的 AI Agent 能够：

1. **读懂** gitmove 状态（doctor、配置、多项目注册表）
2. **安全执行** 常用操作（apply、skip、vendor sync 等）
3. **获得可行动错误**（与 F13 `GitMoveError` 同构 JSON，含 remediation）
4. **遵循项目 Skill** 选型 skip / link / vendor / projects

**原则**：MCP / Skill **不重复** Git 或业务逻辑；只包装已有 `src/gitmove/` 模块。

---

## 2. 能力面选型

| 能力面 | 用途 | 交付物 |
|--------|------|--------|
| **MCP Server** | 工具化调用、结构化 I/O、IDE 集成 | `gitmove-mcp`（stdio） |
| **MCP Resources** | 只读上下文（配置、文档、错误码） | `gitmove://` URI |
| **MCP Prompts** | 可复用任务模板 | 诊断 / 换机 / vendor _setup |
| **Cursor Skill** | 路由、边界、何时用何能力 | `.cursor/skills/gitmove-ops/` |
| **Agent 规则（可选）** | 仓库内短约束 | `.cursor/rules/gitmove-ai.mdc` |
| **CLI `--json`** | 无 MCP 时的机器可读输出 | 与 MCP 共用 serializer |

```
                    ┌─────────────────────────────────┐
                    │  AI Client (Cursor / Claude)     │
                    └────────────┬────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │ MCP Tools   │      │ MCP Resources│      │ Skill       │
    │ gitmove-mcp │      │ gitmove://   │      │ gitmove-ops │
    └──────┬──────┘      └──────┬──────┘      └─────────────┘
           │                     │
           └──────────┬──────────┘
                      ▼
           ┌─────────────────────┐
           │  api/ 序列化层       │  ← 新建：JSON DTO、错误包装
           └──────────┬──────────┘
                      ▼
           ┌─────────────────────┐
           │  既有业务模块        │
           │ doctor skip vendor  │
           │ projects sync …     │
           └─────────────────────┘
```

---

## 3. MCP Server 架构

### 3.1 进程与入口

| 项 | 规格 |
|----|------|
| 包路径 | `src/gitmove/mcp/` |
| 入口命令 | `gitmove-mcp`（`project.scripts`） |
| 传输 | **stdio**（v1）；Streamable HTTP 留 v2 |
| SDK | Python 官方 `mcp`（`FastMCP` 或等效 Server API） |
| 依赖 | `[project.optional-dependencies] mcp = ["mcp>=1.0"]` |

```bash
# Cursor ~/.cursor/mcp.json 示例见 examples/mcp/cursor-mcp.json
gitmove-mcp
```

### 3.2 环境变量

| 变量 | 作用 |
|------|------|
| `GITMOVE_REPO` | 默认操作仓库（路径或 alias） |
| `GITMOVE_HOME` | 注册表目录 |
| `GITMOVE_VENDOR_HOME` | Vendor 缓存根 |
| `GITMOVE_MCP_ALLOW_WRITE` | `1` 时允许写工具（否则只读）；写工具仍须 `confirm=true` |

### 3.3 响应格式（统一 Envelope）

所有 Tool 返回 **JSON 字符串**（`application/json` text content）：

```json
{
  "ok": true,
  "tool": "gitmove_doctor",
  "repo": "E:/项目/my-app",
  "data": { "error_count": 0, "issues": [] },
  "remediation": null
}
```

失败时（与 F13 对齐）：

```json
{
  "ok": false,
  "tool": "gitmove_vendor_sync",
  "code": "VENDOR_FF_BLOCKED",
  "message": "vendor sync 无法 fast-forward",
  "cause": "cache 存在非 FF 历史或本地提交",
  "steps": [
    { "title": "检查 cache 状态", "command": "cd ~/gitmove-vendor/foo && git status" },
    { "title": "重置后重试", "command": "gitmove vendor sync foo" }
  ],
  "doc_anchor": "vendor-sync-失败"
}
```

实现：`src/gitmove/api/response.py` 提供 `success()` / `failure()`，MCP 与 CLI `--json` 共用。

---

## 4. MCP Tools 目录

### 4.1 只读工具（默认允许）

| Tool | 参数 | 映射模块 | 说明 |
|------|------|----------|------|
| `gitmove_doctor` | `repo?`, `alias?` | `doctor.run_doctor` | 健康检查 + issue remediation |
| `gitmove_repo_summary` | `repo?` | config + skip/link/vendor list | 配置摘要 |
| `gitmove_list_projects` | `group?` | `registry.list_projects` | 注册表 |
| `gitmove_project_health` | `group?`, `all?` | `projects.batch_doctor` | 多项目巡检 |
| `gitmove_vendor_status` | `repo?`, `name?` | `vendor.status` | 上游落后、cache 状态 |
| `gitmove_sync_check` | `repo?`, `fetch?` | `sync.check_sync` | skip 路径远程差异 |
| `gitmove_explain_error` | `code` | `errors.catalog` | 查错误码修复步骤 |
| `gitmove_capability_advise` | `scenario` | 静态表 + 文档链接 | skip/link/vendor 选型 |

### 4.2 写操作工具（须 `confirm: true` + 可选 `GITMOVE_MCP_ALLOW_WRITE`）

| Tool | 参数 | 映射 | 风险 |
|------|------|------|------|
| `gitmove_init` | `repo`, `confirm` | `init_repo` | 低 |
| `gitmove_apply` | `repo?`, `confirm` | `apply_all` | 中（重建 link/skip） |
| `gitmove_skip_add` | `repo?`, `path`, `confirm` | `skip.add` | 中 |
| `gitmove_skip_remove` | `repo?`, `path`, `confirm` | `skip.remove` | 中 |
| `gitmove_vendor_add` | `repo?`, `repo_path`, `from`, `template?`, `migrate?`, `confirm` | `vendor.add` | 高 |
| `gitmove_vendor_sync` | `repo?`, `name?`, `confirm` | `vendor.sync` | 中 |
| `gitmove_projects_apply_all` | `group?`, `confirm` | `projects.batch_apply` | 高 |

**禁止通过 MCP 暴露**（v1）：

- `vendor remove --purge-cache`
- 任意 `git reset --hard` 代理
- 交互式 `sync pull` 文件级选择（改为 `sync_check` + 建议用户 CLI/GUI）

写工具 schema 示例：

```json
{
  "repo": { "type": "string", "description": "仓库路径或 projects 别名" },
  "confirm": {
    "type": "boolean",
    "description": "必须为 true 才执行写操作"
  }
}
```

---

## 5. MCP Resources

| URI 模板 | 内容 | MIME |
|----------|------|------|
| `gitmove://projects/registry` | `projects.toml` 解析结果 JSON | application/json |
| `gitmove://repo/{path}/config` | 脱敏后的 gitmove.toml 摘要（无密钥） | application/json |
| `gitmove://repo/{path}/doctor` | 最近一次 doctor 快照（可选缓存） | application/json |
| `gitmove://docs/user-manual` | `docs/guides/user-manual.md` 全文 | text/markdown |
| `gitmove://docs/workflows` | `docs/guides/workflows.md` | text/markdown |
| `gitmove://errors/catalog` | 全部 error code + remediation | application/json |
| `gitmove://capability/matrix` | skip/link/vendor/projects 选型表 | application/json |

`{path}` 须 URL 编码；服务器端 `resolve_repo_root` 校验。

---

## 6. MCP Prompts

| Prompt ID | 用途 | 注入上下文 |
|-----------|------|------------|
| `diagnose_repository` | 单仓 doctor + 修复建议 | repo + doctor resource |
| `setup_cursor_vendor` | `.cursor` vendor 分步 | workflows §6 + template |
| `multi_project_health` | 批量巡检解读 | projects registry |
| `after_git_pull` | pull 后 skip 检查 | sync_check 结果 |
| `onboard_new_clone` | init → import → apply | user-manual §4 |

Prompt 仅组装说明与建议调用的 Tool 名，**不**自动执行写操作。

---

## 7. Cursor Skill 设计

### 7.1 `gitmove-ops`（主 Skill）

路径：`.cursor/skills/gitmove-ops/SKILL.md`

**触发**：

- 用户提到 gitmove、skip-worktree、vendor、`.git/gitmove.toml`
- 本地 Git 策略、不改 gitignore、`.cursor` 外仓
- Agent 需诊断/修复 gitmove doctor 问题

**内容要点**：

1. 先 `gitmove_doctor` 或 CLI `gitmove doctor --json`（实现后）
2. 读 `gitmove://docs/workflows` 选型
3. 写操作必须向用户确认后再 `confirm=true`
4. 错误时读 `gitmove_explain_error` 或 response.steps

### 7.2 `gitmove-mcp-setup`（安装 Skill）

路径：`.cursor/skills/gitmove-mcp-setup/SKILL.md`

**触发**：配置 MCP、Cursor mcp.json、gitmove-mcp 连不上

**内容**：安装 `pip install -e ".[mcp]"`、mcp.json 片段、环境变量、stdio 调试

### 7.3 工作流触发表增量

在 `workflow-triggers/SKILL.md` 增加：

| 触发 | Skill |
|------|-------|
| gitmove、skip-worktree、vendor sync、gitmove.toml | `gitmove-ops` |
| 配置 gitmove MCP、mcp.json | `gitmove-mcp-setup` |

---

## 8. CLI `--json` 对齐（无 MCP 降级）

为脚本与 Agent 提供与 MCP 同构输出：

```bash
gitmove doctor --json
gitmove projects list --json
gitmove vendor status cursor-spec --json
```

字段与 MCP Envelope 一致，便于 Skill 写「无 MCP 时用 CLI」。

---

## 9. 模块划分

```
src/gitmove/
  api/
    __init__.py
    response.py      # Envelope、serialize DoctorReport
    repo_resolver.py # repo/alias 参数解析（复用 repo_context）
  mcp/
    __init__.py
    server.py        # FastMCP 注册 tools/resources/prompts
    tools_read.py
    tools_write.py
  errors.py          # F13 catalog（MCP 依赖）
```

| 层 | 职责 |
|----|------|
| `api/` | 无 MCP 依赖；CLI `--json` 与 MCP 共用 |
| `mcp/` | 仅协议适配；薄 wrapper |
| 业务层 | 不变 |

---

## 10. 安全与权限

| 规则 | 说明 |
|------|------|
| 本地等同用户 | MCP 以当前 OS 用户运行，能读写的与 CLI 相同 |
| 写操作双门禁 | `confirm=true` + 可选 `GITMOVE_MCP_ALLOW_WRITE=1` |
| 路径校验 | 所有 `repo_path` 走 `resolve_repo_path` |
| 无任意 shell | Tools 不得接受自由 form 命令 |
| 日志 | stderr 可 debug；不记录 git 凭据 |
| 交互式 sync | v1 不暴露 MCP；避免 Agent 静默选 l/r/m/s |

---

## 11. 与 F13 / 0.5 的关系

| 依赖 | 说明 |
|------|------|
| **F13 错误模型** | MCP 失败响应 MUST 使用 `GitMoveError` + `RemediationStep` |
| **实现顺序** | F13-a（errors + JSON）→ **AI api 层** → MCP server |
| **0.6.0** | 建议在 0.5.0 Phase 1 完成后启动 |

---

## 12. 客户端配置示例

见 [examples/mcp/cursor-mcp.json](../../examples/mcp/cursor-mcp.json)。

Claude Desktop `claude_desktop_config.json` 同构，command 指向 venv 内 `gitmove-mcp`。

---

## 13. 测试策略

| 类型 | 内容 |
|------|------|
| 单元 | `api/response.py` 序列化；tool handler mock 业务层 |
| 集成 | in-process MCP Client 调用各 read tool |
| 契约 | JSON schema snapshot（doctor、error envelope） |
| 不写 E2E | 不依赖真实 Cursor UI |

---

## 14. 版本路线

| 版本 | 内容 |
|------|------|
| **0.6.0** | MCP stdio、read tools、resources、gitmove-ops skill、CLI `--json`（doctor/list/status） |
| **0.6.x** | write tools、prompts、mcp-setup skill |
| **0.7** | Streamable HTTP、可选 `GITMOVE_MCP_TOKEN` |

---

## 相关文档

- [需求规格](../requirements/features/gitmove-ai-integration.md)
- [架构概览](overview.md)
- [0.5 增强（F13 错误模型）](../requirements/features/gitmove-0.5-enhancements.md)
- [使用说明书](../guides/user-manual.md)
