# gitmove · Agent 开发指引

> 运行时配置均在 `.cursor/`；完成定义见 `verification-gate` Skill。

## 1. 仓库

| 目录 | 技术栈 | 职责 |
|------|--------|------|
| `src/gitmove/` | Python 3.10+ | CLI / GUI 核心逻辑 |
| `docs/` | Markdown | 需求、设计、产品、工作流 |
| `docs/README.md` | 文档总索引 |

## 2. Cursor 索引

| 文档 | 用途 |
|------|------|
| `.cursor/constraints.md` | 硬约束 |
| `.cursor/skills/workflow-triggers/SKILL.md` | 工作流触发表 |
| `.cursor/workflows/` | 需求/设计/开发/交付剧本 |
| `docs/requirements/features/` | 单功能需求（定稿后实现） |
| `docs/design/overview.md` | 架构与能力关系 |
| `docs/design/ai-integration.md` | AI / MCP / Skill 设计 |
| `docs/product/roadmap.md` | 版本路线图 |
| `docs/guides/workflows.md` | 典型场景工作流 |

## 3. 完成定义

见 `verification-gate` Skill + 本项目 `constraints.md`。

## 4. 项目说明

gitmove 是在不修改 `.gitignore` 的前提下管理本地 Git 排除策略的工具：

- skip-worktree（已追踪文件本地冻结）
- 外部目录链接（Junction / Symlink）
- 个人 worktree 管理
- 配置 import/export、sync check/pull（v0.2.x）
- CLI + 跨平台 GUI（CustomTkinter）

**规划（需求已定稿，待实现）**：

- 0.5 增强（`gitmove-0.5-enhancements.md` · F1–F13）
- AI 集成（`gitmove-ai-integration.md` · v0.6 · MCP / Skill / `--json`）

**已实现**：多项目管理（v0.3）、上游 Vendor（v0.4）。详见 `docs/README.md`。
