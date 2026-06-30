# gitmove 产品路线图

## 版本总览

| 版本 | 主题 | 状态 | 需求文档 |
|------|------|------|----------|
| **0.2.0** | 核心 + GUI + 打包 | 已发布 | [gitmove-core](../requirements/features/gitmove-core.md) |
| **0.2.x** | 配置迁移 + 远程 sync | 已实现 | [gitmove-config-sync](../requirements/features/gitmove-config-sync.md) |
| **0.3.0** | 多项目 CLI | 已实现 | [gitmove-multi-project](../requirements/features/gitmove-multi-project.md) |
| **0.3.1** | 多项目 GUI 侧栏 | 已实现 | 同上 |
| **0.4.0** | 上游 Vendor | 已实现 | [gitmove-vendor](../requirements/features/gitmove-vendor.md) |
| **0.5.0** | Vendor 增强 + 多项目增强 + 错误引导 | **已实现** | [gitmove-0.5-enhancements](../requirements/features/gitmove-0.5-enhancements.md) |
| **0.6.0** | AI 集成（MCP + Skill + JSON） | 草案 · 待实现 | [gitmove-ai-integration](../requirements/features/gitmove-ai-integration.md) |

## 0.2.0 — 核心能力（已完成）

- skip-worktree / link / worktree
- `init` · `apply` · `doctor`
- CustomTkinter GUI
- PyInstaller 三平台 CI
- 路径穿越防护、测试覆盖率 ≥ 80%

## 0.2.x — 配置与同步（已完成）

- `gitmove config export` / `import`（含 `--from-repo`）
- `gitmove sync check` / `sync pull`（skip 文件交互式 reconcile）
- Windows 子进程无 CMD 闪烁
- 刷新性能优化（合并 `ls-files`、doctor 复用数据）

## 0.3.0 — 多项目管理 · CLI

**目标**：同时管理多个业务仓库。

交付：

- `~/.gitmove/projects.toml` 注册表
- `gitmove projects list|add|remove|set-default`
- 全局 `-C` / `GITMOVE_REPO`
- `projects doctor|apply|sync --all`
- 批量 sync：**项目级** + **文件级** 两级交互

不交付：云端同步注册表、自动扫描全盘 Git 仓。

## 0.3.1 — 多项目管理 · GUI

- 左侧项目列表与切换
- 「全部 doctor」「全部 apply」（后台队列）
- 批量 sync 向导（可选，可延后）

## 0.4.0 — 上游 Vendor

**目标**：从任意上游 Git 仓整仓取用内容到指定 `repo_path`。

交付：

- `vendor add|sync|list|status|remove`
- 整仓 link 到 `~/gitmove-vendor/<name>/`
- **已追踪 `repo_path`**：批量 skip-worktree（禁止改挂替代路径）
- `vendor sync` 仅 FF，冲突**中止不 merge**
- `apply` / `doctor` 集成

典型场景：AI 规范 `.cursor`、公司 tools 仓、文档模板等（见 vendor 需求文档场景表）。

## 0.5.0 — Vendor 增强 + 错误引导（已定稿）

**目标**：竞品高契合能力 Phase 1 + 全命令可行动错误提示。

交付：

- **F13** 错误模型、CLI Rich 引导、GUI `ErrorDialog`、doctor 修复按钮
- **F1** Vendor 模板（`cursor-spec` + `templates.toml`）
- **F2** `include_paths` 子目录 link（v1 单路径）
- **F3** shallow clone（默认 depth=1）
- **F4** `projects repair`
- **F5** `config import --register`
- **F6** GUI 批量 sync 向导

## 0.5.x — Phase 2（已定稿 · 后续版本）

- F7 Vendor pin（tag/SHA）
- F8 Git hooks install/uninstall
- F9 Profile 切换
- F10 `projects scan`（opt-in）
- F11 `projects update`（批量 ff-only pull）
- F12 Vendor `status --all` / check-updates exit code

## 0.6.0 — AI 集成（MCP · Skill · JSON API）

**目标**：供 Cursor 等 AI 客户端结构化调用 gitmove。

交付（详见 [ai-integration.md](../design/ai-integration.md)）：

- `gitmove-mcp` stdio 服务器 + read tools
- MCP Resources（文档、注册表、错误 catalog）
- Cursor Skills：`gitmove-ops`、`gitmove-mcp-setup`
- CLI `--json`（doctor / projects list / vendor status）
- 依赖 0.5 **F13** 错误 Envelope

Phase 2（0.6.x）：write tools + MCP Prompts + `GITMOVE_MCP_ALLOW_WRITE`

## 实现顺序建议

```
0.4.0（已完成）→ 0.5.0 Phase0(F13) + Phase1(F1–F6) → 0.5.x Phase2(F7–F12) → 0.6.0 AI(MCP+Skill)
```

## 不变约束（全版本）

- 不修改业务仓 `.gitignore`
- 仓库策略写在 `.git/gitmove.toml`
- 不替代 Git / 不强制团队同步本地配置

## 竞品与定位

与 repoverlay、shimmer、gitnook、dew、worktree 工具群等的对比与场景选型，见 [competitive-analysis.md](competitive-analysis.md)。
