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

## ADR-0009 · 工作区 = 多仓组合（Member 一等公民）

- **日期**：2026-11-06
- **状态**：已定
- **背景**：真实大项目由多个 git 仓库组成（主仓 + AI 规范库 + 工具库 + 本地素材仓）。
  1.x 把"依赖"降级为 `project.lock.toml` 里的一条声明：能看漂移，但不能同步、不能定位成"工作区成员"、Revision 也无法绑定成员 commit。
- **决定**：
  1. 引入 `Workspace` 与 `Member` 两个一等概念；`workspace.toml` 声明，`workspace.lock.toml` 解析。
  2. Member 有 `role`（main/editable/readonly/local）与 `strategy`（clone/vendor/link）。
  3. **Revision 记录每个成员的 commit**；`checkout <rev>` 逐仓还原。
  4. 成员脏时默认**拒绝提交**，`--members` 才一并提交（避免误提交别人的仓）。
- **理由**：
  - 用户真实诉求就是"管理一层多仓"：AI 规范库要在项目内改并回推，工具库要钉版本，素材仓只备份。
  - 只记录主仓 commit 的 Revision 在回滚时会把成员留在"未来版本"，语义不成立。
- **代价**：
  - 提交/回滚变成多仓事务，需要逐仓预检与错误提示。
  - 需要处理 Windows junction、嵌套 `.git`、备份排除规则。
- **兼容**：`project.lock.toml` 保留（包级实装版本），与 `workspace.lock.toml`（仓库级 commit）分工明确。

## ADR-0010 · `checkout` 默认 detached，成员逐仓还原

- **日期**：2026-11-06
- **状态**：已定
- **决定**：`gitmove checkout <rev>` 对主仓与每个成员执行 detached `git checkout <commit>`；
  需要分支时用 `--branch <name>`；任一仓脏时要求 `--force`。
- **理由**：回滚语义应"精确到 commit"，避免意外推进分支；分支操作是另一个显式动作。

## ADR-0011 · 资产平面支持多备份目标（本地 + 远程）

- **日期**：2026-11-06
- **状态**：已定
- **背景**：素材既要有"本地移动硬盘"这类离线副本，也要有"异地/云端"副本；单仓库配置只能二选一。
- **决定**：`workspace.toml` 支持 `[[backup.target]]` 数组，每个目标有 `kind`(local/remote)、`repo`、密码源、`priority`；
  **2.0 只实现 `kind = "local"`（两块本地盘）**，`remote` 字段保留、2.1 再评估；
  一次 `asset backup` 遍历所有启用目标，逐目标记录 `revision_target` 快照。
- **规则**：目标互不阻塞；部分失败退出码 2；`asset restore` 按 `--from` 或 `priority` 选源；凭据只走环境变量/密码文件。
- **理由**：restic 原生支持 s3/sftp/rest/b2/azure，gitmove 不需要自研上传；多目标天然满足"3-2-1"备份原则。
- **代价**：备份时间 × 目标数；需要 UI 分列展示与"远程副本落后"告警。

## ADR-0012 · 分支以 git 为准，工作区分支是成员分支的映射

- **日期**：2026-11-06
- **状态**：已定
- **决定**：
  - 分支/合并语义完全交给 git（每成员各自的分支）；
  - 工作区分支 = 每成员分支名 + 资产基准的映射，存 `refs/gitmove/branches/<name>`（JSON）并在索引里缓存；
  - `switch` 逐成员切换（脏仓拒绝），`merge` 逐成员合并（冲突即停，不自动解决）。
- **理由**：git 的分支/合并是成熟语义，自研会制造第二套 bug；用户要的是"和 git 一样"，那就用 git。
- **代价**：多仓下"切换/合并"是 N 次操作，失败可能只完成一半 → 必须输出逐仓结果并支持重试。

## ADR-0013 · 资产合并 = 三路文件级分析（不是二选一）

- **日期**：2026-11-06
- **状态**：已定（原"资产只做快照选择"作废）
- **背景**：二进制素材不能做内容拼接，但"哪个文件该留、哪个是冲突"是可以分析的：
  只要知道每个快照里每个文件的 `path/size/mtime/hash`，就能按三方祖先做文件级判定。
- **决定**：
  1. 以共同祖先快照为 base，逐文件判定（见架构 §2.7 判定表）；
  2. **无歧义自动合并**（并集/单侧改动/两侧相同内容）；
  3. **冲突** = 同路径两侧内容不同，或删除 vs 修改；冲突不覆盖任何一侧，进入合并状态；
  4. 冲突必须显式解决（ours/theirs/both-rename）后才能 `--continue`；
  5. 判定依据优先用 `blake3` 索引；缺失时才流式哈希（避免读 38 GB）。
- **理由**：用户要的是"能分析出来"，不是"猜一个默认值"。
- **代价**：需要维护快照的文件索引（`snapshot_file`），首次建索引有成本；冲突 UI 必须做。
