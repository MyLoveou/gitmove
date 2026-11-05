# gitmove v2

项目工作区的版本控制与备份编排层：一个大项目由**多个 git 仓库**组成（主仓 + AI 规范库 + 工具库 + 本地素材仓），gitmove 把这些仓库当作 **Member** 管理，并把**代码（git）**与**大体积素材（restic）**编成同一个可回滚的**修订（Revision）**。

> 状态：**M1 进行中**（2026-11-06）。需求已确认（v2.0 基线），桌面壳已可运行，核心仍是 Python CLI，M2 起由 Rust 接管。

## 文档

| 文档 | 内容 |
|---|---|
| [产品需求](docs/requirements/product-requirements.md) | 定位、场景、19 条 FR、验收、里程碑（已确认） |
| [架构](docs/design/architecture.md) | 分层、多仓模型、双盘备份、三路资产合并、数据模型 |
| [决策记录](docs/decisions/decisions.md) | ADR-0001…0015 |

## 目标形态

```
gitmove <cmd>        # CLI
gitmove daemon       # JSON-RPC（Electron 使用）
gitmove mcp          # stdio MCP（AI 客户端使用）
```

同一个 Rust 二进制，三种入口。关键能力：

- **多仓工作区**：主仓 + AI 规范库（可改可回推）+ 工具库（钉版本）+ 本地素材仓
- **双备份目标**：一次备份同时写两块本地盘，互不阻塞
- **git 语义的分支与合并**：工作区分支 = 每成员分支映射；资产按三路分析合并
- **可视化**：提交图（DAG）、成员/依赖图、备份矩阵、四平面变更面板

## M1 已实现（桌面壳）

```
src/main/       Electron 主进程：窗口、IPC、sidecar 桥（调 Python CLI --json）
src/preload/    contextBridge，渲染层只拿到 gitmove.invoke
src/renderer/   Vue 3 + Vite + Pinia + Router：总览页（项目表 / 统计 / 刷新）
src/shared/     协议类型（Envelope、ProjectRow、AuditRow、Op）
```

数据链路：Vue → preload → main → `python -m gitmove … --json` → 共享 envelope → 渲染。

## 开发

```powershell
npm install                 # 依赖（electron 33.4.11，使用本机缓存）
npm run build               # 生产构建（out/）
npm run dev                 # 开发模式（Electron + Vite HMR）

# 冒烟：读取现有 Python 版 CLI，验证主进程 + 渲染层
$env:GITMOVE_PYTHON = "D:\Project\GitMove\gitmove\.venv\Scripts\python.exe"
npm run smoke               # 期望：SMOKE OK projects=N / SMOKE OK renderer
```

环境变量：

| 变量 | 作用 |
|---|---|
| `GITMOVE_PYTHON` | 指向装有 `gitmove` 的 Python（默认 `python`） |
| `ELECTRON_RUN_AS_NODE` | 若被外部置 1，Electron 会退化成 Node；启动前需清除 |

## 里程碑

| 阶段 | 交付 | 状态 |
|---|---|---|
| M0 | 需求/架构/ADR 定稿 | ✅ |
| M1 | Electron + Vue 壳，接现有 CLI | 🚧 可运行（总览页 + 冒烟） |
| M2 | Rust 只读核心（scan/index/doctor/audit） | ⬜ |
| M3 | Revision（commit/log/show/checkout） | ⬜ |
| M4 | 写路径迁移（策略/依赖/资产） | ⬜ |
| M5 | MCP + 全功能界面 | ⬜ |
| M6 | Python 下线，单二进制发布 | ⬜ |
