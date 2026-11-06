# gitmove v2

项目工作区的版本控制与备份编排层：一个大项目由**多个 git 仓库**组成（主仓 + AI 规范库 + 工具库 + 本地素材仓），gitmove 把这些仓库当作 **Member** 管理，并把**代码（git）**与**大体积素材（restic）**编成同一个可回滚的**修订（Revision）**。

> 状态：**v0.10.0**（2026-11-06）。Rust 核心 + Electron/Vue 五页面；MCP 15 tools；文件级提交。Rust 核心接管：审计 / 修订（提交·时间线·回滚·重建）/ 多仓工作区 / 依赖清单 / **双盘资产备份** / 依赖回推 / MCP。Electron 五页面可用，Windows 安装包（NSIS）已产出。

## 文档

| 文档 | 内容 |
|---|---|
| [产品需求](docs/requirements/product-requirements.md) | 定位、场景、19 条 FR、验收、里程碑（已确认） |
| [架构](docs/design/architecture.md) | 分层、多仓模型、双盘备份、三路资产合并、数据模型 |
| [决策记录](docs/decisions/decisions.md) | ADR-0001…0015 |

## 结构

```
crates/
  core/        Rust 核心：registry / scan / audit / workspace / revision（SQLite + trailer）
  cli/         单二进制入口 gitmove-core（cli 命令 + 共享 JSON envelope）
src/main/      Electron 主进程：窗口 / IPC / sidecar（自动选择 Rust 核心或 Python 过渡）
src/preload/   contextBridge（仅暴露 gitmove.invoke）
src/renderer/  Vue 3 + Vite + Pinia：总览 / 提交图 / 工作区 / 设置
src/shared/    跨进程协议类型
```

## 已实现能力

| 能力 | 命令（Rust 核心） |
|---|---|
| 只读审计（真实文件数/体积，中文路径安全） | `audit --all` |
| 项目注册表 | `projects list` |
| **修订提交**（git commit + `Gitmove-Revision` trailer + SQLite 索引） | `commit -m "..." [--members]` |
| 修订时间线 / 详情 | `rev log` / `rev show <id>` |
| 双盘资产备份（互不阻塞，部分失败=2） | `asset init/status/backup/snapshots/check/restore` |
| 依赖清单（漂移/未生效） | `dep list` |
| 依赖回推（冲突不自动解决，断网降级 bundle） | `ws diff` / `ws contribute` |
| MCP（stdio，15 tools + prompt + resource） | `mcp` |
| 三路资产合并（判定表 + 冲突清单 + 强制应用） | `asset merge` / `asset ls` |
| 文件级变更 / 选择提交 / 放弃 | `changes` / `commit --path` / `discard --path` |
| 策略迁移（skip / link junction / worktree / apply） | `policy skip|link|worktree|apply` |
| 工作区分支/合并（逐成员 git 语义） | `ws branch-list|branch-create|branch-switch|merge` |
| 保留策略透传 / 体积守卫 | `asset prune` / `asset guard` |
| 配置导出导入 | `config export|import` |
| 合并冲突面板（GUI） | 备份页「三路合并」 |
| 同步检查 / 快进拉取 | `sync check` / `sync pull [--fetch]` |
| 排除预设 | `exclude preset-list / preset-enable / preset-disable` |
| vendor 模板清单 | `vendor template-list` |
| **回滚**（主仓 + 成员逐仓 checkout） | `checkout <id> [--force]` |
| 索引从 trailer 重建 | `index rebuild` |
| 多仓工作区状态（成员/角色/pin/dirty） | `ws status` |

桌面端：总览（项目与健康）、提交图（时间线 + 提交表单）、工作区（成员表）、设置（引擎信息）。
点击总览任一行可切换当前工作区。

## 打包

```powershell
cargo build --release
npm run build
npx electron-builder --win nsis   # dist/gitmove Setup 0.2.0.exe
```

安装包会把 `gitmove-core.exe` 放进 `resources/core/`。

## 构建与运行

```powershell
# Rust 核心（单二进制，约 3 MB）
cargo build --release                 # target/release/gitmove-core.exe
cargo test                            # 6 个集成测试

# 桌面端
npm install
npm run build
npm run dev                           # 开发模式

# 冒烟：核心 + 渲染层
$env:GITMOVE_CORE = "$PWD\target\release\gitmove-core.exe"
npm run smoke                         # SMOKE OK projects=6 / audit=6 / ws / revisions / renderer
```

引擎选择顺序：`GITMOVE_CORE` → 安装包 `resources/core` → `target/release` → `target/debug`。应用**不再需要 Python**。

## 里程碑

| 阶段 | 交付 | 状态 |
|---|---|---|
| M0 | 需求/架构/ADR 定稿 | ✅ |
| M1 | Electron + Vue 壳，接现有 CLI | ✅ |
| M2 | Rust 只读核心（scan/index/doctor/audit） | ✅ 只读部分 |
| M3 | Revision（commit/log/show/checkout + 重建） | ✅ |
| M4 | 写路径（策略/依赖/资产/回推） | ◐ 资产/依赖/回推已完成；`apply/skip/link` 仍在 Python |
| M5 | MCP + 全功能界面 | ◐ MCP 5 tools；五页面可用；三路资产合并未做 |
| M6 | Python 下线，单二进制发布 | ◐ Windows 安装包已产出；Python 尚未下线 |
