# gitmove 文档

本目录沉淀 gitmove 的产品需求、架构设计与使用指南。实现前须以 **状态：已定稿** 的需求文档为准（见 `.cursor/constraints.md`）。

## 文档地图

```
docs/
├── README.md                 ← 本索引
├── design/
│   ├── overview.md           架构与能力关系
│   └── ai-integration.md     AI / MCP / Skill 集成设计
├── product/
│   ├── roadmap.md            版本路线图
│   └── competitive-analysis.md 竞品对比分析
├── guides/
│   └── user-manual.md        使用说明书（推荐阅读）
│   └── workflows.md          典型工作流与场景
└── requirements/features/
    ├── gitmove-core.md       核心能力（v0.2.0，已实现）
    ├── gitmove-config-sync.md 配置导入导出与远程 sync（v0.2.x，已实现）
    ├── gitmove-multi-project.md 多项目管理（v0.3.x，已实现）
    ├── gitmove-vendor.md     上游依赖 Vendor（v0.4.0，已实现）
    └── gitmove-gui-ux-redesign.md  GUI 场景指引与交互优化（评审中）
    └── gitmove-ai-integration.md    AI/MCP/Skill 集成（草案）
```

## 需求文档状态

| 文档 | 版本 | 状态 | 说明 |
|------|------|------|------|
| [gitmove-core](requirements/features/gitmove-core.md) | 0.2.0 | **已定稿 · 已实现** | skip / link / worktree / CLI / GUI |
| [gitmove-config-sync](requirements/features/gitmove-config-sync.md) | 0.2.x | **已定稿 · 已实现** | config import/export、sync check/pull |
| [gitmove-multi-project](requirements/features/gitmove-multi-project.md) | 0.3.x | **已定稿 · 已实现** | 项目注册表、批量操作、`-C` |
| [gitmove-vendor](requirements/features/gitmove-vendor.md) | 0.4.0 | **已定稿 · 已实现** | 上游整仓 link、vendor sync |
| [gitmove-0.5-enhancements](requirements/features/gitmove-0.5-enhancements.md) | 0.5.0 | **已定稿 · 已实现** | F13 错误引导、Vendor 模板/shallow/include、repair、GUI batch sync |
| [gitmove-cursor-vendor-profile](requirements/features/gitmove-cursor-vendor-profile.md) | 0.5.x | **已定稿 · Phase 2 已实现** | 已追踪 `.cursor` + 个人 Vendor + Profile 切换（方案 A+C） |
| [gitmove-gui-ux-redesign](requirements/features/gitmove-gui-ux-redesign.md) | 0.5.3 | **评审中 · Phase 1 已实现** | GUI 场景指引、Vendor/Profile Tab、概览可行动化 |
| [gui-vendor-phase2](design/gui-vendor-phase2.md) | 0.5.3 | **设计稿** | Vendor Tab 可视化 add/sync/remove |
| [gitmove-ai-integration](requirements/features/gitmove-ai-integration.md) | 0.6.0 | **草案 · 设计已完成** | MCP、Skill、CLI `--json` |

## 配置存储（两层模型）

| 层级 | 路径 | 作用 |
|------|------|------|
| **仓库级** | `<repo>/.git/gitmove.toml` | skip、link、worktree、vendor（规划） |
| **用户级** | `~/.gitmove/projects.toml` | 多项目注册表（规划） |
| **用户级** | `~/gitmove-vendor/<name>/` | Vendor 上游 clone 缓存（规划） |

仓库级配置**不提交**到业务仓；用户级配置**不进**任何 Git 仓库。

## 快速跳转

- 想了解整体设计 → [design/overview.md](design/overview.md)
- 想看 AI/MCP 集成 → [design/ai-integration.md](design/ai-integration.md)
- 想看版本计划 → [product/roadmap.md](product/roadmap.md)
- 想看竞品对比 → [product/competitive-analysis.md](product/competitive-analysis.md)
- 想看怎么用 → [guides/user-manual.md](guides/user-manual.md)（**使用说明书**）
- 想看场景示例 → [guides/workflows.md](guides/workflows.md)
- 用户手册（安装、命令表）→ 仓库根目录 [README.md](../README.md)
