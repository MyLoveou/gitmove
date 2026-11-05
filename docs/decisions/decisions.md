# 决策记录（ADR）

> 每条决策一旦定稿，改动需新增一条"变更"说明，不直接改写历史。

---

## ADR-0001 · 前端采用 Electron + Vue 3

- **日期**：2026-11-06
- **状态**：已定
- **决定**：桌面端使用 Electron（主进程）+ Vue 3 + Vite + Pinia + Vue Router。
- **理由**：用户明确要求；打包（electron-builder → NSIS）、自动更新、调试工具链成熟；Web 技术栈能实现时间线、依赖图、进度条等 CustomTkinter 做不到的交互。
- **代价**：安装包 100–200 MB、内存 200–400 MB。
- **保留退路**：核心只经 JSON-RPC sidecar 通信，未来可换 Tauri 而不动核心。

## ADR-0002 · 核心语言采用 Rust，单二进制三入口

- **日期**：2026-11-06
- **状态**：已定
- **决定**：新核心用 Rust；同一二进制提供 `gitmove`（CLI）、`gitmove daemon`（JSON-RPC）、`gitmove mcp`（stdio）。
- **理由**：单文件分发、并行扫描、SQLite 绑定（rusqlite）、MCP SDK（rmcp）；避免 Python 运行时与 PyInstaller 打包问题（1.0.1 曾因缺 Tcl/Tk DLL 出事）。
- **代价**：开发速度低于 Python；需要团队具备 Rust 能力。
- **替代方案**：Go（放弃：git 库语义与真 git 差距大）；Node（放弃：重 I/O 与冷启动不占优）。

## ADR-0003 · git 操作以 git CLI 为准

- **日期**：2026-11-06
- **状态**：已定
- **决定**：所有写操作与语义敏感读操作调用 `git` 可执行文件；`gix` 仅用于只读、高频、批量查询（如遍历 ref）。
- **理由**：1.x 的 450 个测试建立在真 git 行为上（quotePath、skip-worktree、junction、worktree）；自行实现的 git 语义会制造第二套 bug。
- **代价**：每次调用有进程开销；通过批量参数与索引缓解。

## ADR-0004 · 资产平面继续使用 restic，不捆绑

- **日期**：2026-11-06
- **状态**：已定
- **决定**：资产快照/恢复/校验/清理全部委托 restic CLI；gitmove 只编排。
- **理由**：已实测（视频项目 3.9 GB / 553 文件 / 二次增量 0 B）；自研去重加密不可维护。
- **降级**：restic 不在 PATH 时，代码平面仍可用；`doctor` 给出安装指引，退出码 2。

## ADR-0005 · Revision 双写（SQLite 索引 + git commit trailer）

- **日期**：2026-11-06
- **状态**：已定
- **决定**：每次提交写入两处：
  1. `.gitmove/index.sqlite` 的 `revision` 表（快速查询）
  2. git commit message 的 trailer `Gitmove-Revision: <id>`
- **理由**：索引快；trailer 让索引丢失、换机、裸仓库 clone 后仍能重建修订历史。
- **实现要点**：先预留 id（pending 行）→ 带 trailer 提交 → 回填 commit/snapshot；失败则删除 pending。
- **一致性**：`gitmove index rebuild` 从 trailer 重建；提交后校验两处 id 一致。

## ADR-0006 · 新仓库增量接管，不推倒重写

- **日期**：2026-11-06
- **状态**：已定
- **决定**：在 `D:\Project\GitMove\gitmove-v2` 新建仓库；Python 版 `gitmove` 冻结新功能，仅修 bug；Rust 逐面接管。
- **理由**：450 个测试是行为金样（编码、quotePath、junction、depot 边界）；一次性重写等于重踩坑。
- **节奏**：M1 Electron 壳接 1.x CLI → M2 Rust 只读 → M3 Revision → M4 写路径 → M6 下线 Python。

## ADR-0007 · 前端与核心之间用 JSON-RPC 2.0 sidecar

- **日期**：2026-11-06
- **状态**：已定
- **决定**：Electron 主进程 `spawn` 核心二进制，走 stdio 上的 JSON-RPC 2.0；渲染层通过 IPC 调主进程。
- **理由**：崩溃隔离（核心挂了 UI 不崩）、跨语言边界简单、未来可换 Tauri、CLI/MCP 复用同一核心。
- **替代方案**：napi-rs 原生模块（性能更好但耦合、崩溃共命运）——暂不采用。

## ADR-0008 · 工作区布局 `.gitmove/` + 旧配置只读兼容

- **日期**：2026-11-06
- **状态**：已定
- **决定**：新配置写 `<workspace>/.gitmove/config.toml` 与 `index.sqlite`；读取时若存在 `.git/gitmove.toml` 则导入（只读，不自动删除）。
- **理由**：不把状态塞进 `.git/`（用户可读、可备份、可忽略）；迁移平滑。
- **兼容**：`project.lock.toml` 仍在项目根，格式不变。
