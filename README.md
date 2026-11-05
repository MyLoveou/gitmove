# gitmove v2

项目工作区的版本控制与备份编排层：一个大项目由**多个 git 仓库**组成（主仓 + AI 规范库 + 工具库 + 本地素材仓），gitmove 把这些仓库当作 **Member** 管理，并把**代码（git）**与**大体积素材（restic）**编成同一个可回滚的**修订（Revision）**。

> 状态：**需求已确认**（M0 完成，2026-11-06）。下一阶段 M1：Electron + Vue 壳。本仓库是新实现（Rust 核心 + Electron + Vue），Python 版 `gitmove` 冻结功能、仅修 bug，按里程碑逐面接管。

## 文档

| 文档 | 内容 |
|---|---|
| [产品需求](docs/requirements/product-requirements.md) | 定位、场景、功能需求（FR）、验收、里程碑 |
| [架构](docs/design/architecture.md) | 分层、Revision 流程、数据模型、daemon 协议 |
| [决策记录](docs/decisions/decisions.md) | ADR-0001…0008（Electron/Rust/双写/兼容策略） |

## 目标形态

```
gitmove <cmd>        # CLI
gitmove daemon       # JSON-RPC（Electron 使用）
gitmove mcp          # stdio MCP（AI 客户端使用）
```

同一个 Rust 二进制，三种入口。

关键能力：

- **多仓工作区**：主仓 + AI 规范库（可改可回推）+ 工具库（钉版本）+ 本地素材仓
- **双备份目标**：一次备份同时写本地移动硬盘与远程对象存储，互不阻塞
- **git 语义的分支与合并**：工作区分支 = 每成员分支映射；合并冲突交给 git，资产按策略选快照
- **可视化**：版本 DAG、成员/依赖图、备份矩阵、四平面变更面板

## 里程碑

| 阶段 | 交付 |
|---|---|
| M0 | 需求/架构/ADR 定稿（进行中） |
| M1 | Electron + Vue 壳，接现有 CLI |
| M2 | Rust 只读核心（scan/index/doctor/audit） |
| M3 | Revision（commit/log/show/checkout） |
| M4 | 写路径迁移（策略/依赖/资产） |
| M5 | MCP + 全功能界面 |
| M6 | Python 下线，单二进制发布 |

## 开发

暂无可运行代码（M0 阶段）。需求确认后按里程碑推进。
