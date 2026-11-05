# gitmove v2 · 需求文档（定稿中）

> 状态：**待确认**（2026-11-06）。确认后本文件冻结为 v2.0 基线，改动走变更记录。
> 仓库：`D:\Project\GitMove\gitmove-v2`（**新仓库**，与 Python 版 `gitmove` 并行，逐步接管）
> 已定技术决策见 [decisions](../decisions/decisions.md)；架构见 [architecture](../design/architecture.md)。

---

## 1. 产品定位

**一句话**：gitmove 是**项目工作区的版本控制与备份编排层**——把"代码（git）"和"大体积素材（restic）"编成同一个可回滚的**修订（Revision）**，并管理项目对其它项目的依赖。

它**不是** git 的替代品，而是 git 之上的编排层：

| 平面 | 引擎 | 谁负责 |
|---|---|---|
| 代码平面 | git | 提交/历史/分支/合并全部用 git |
| 资产平面 | restic | 去重/加密/快照/恢复全部用 restic |
| 依赖平面 | `project.lock.toml` + vendor cache | gitmove 声明与校验 |
| 可再生平面 | `[env]` 配方 | gitmove 编排重建 |

### 1.1 目标用户（真实场景）

**场景 A：依赖组合型项目**

```
my-app
├── 依赖 ai-spec（AI 规范库：skills/rules/adapters）  → 需要「改完回推上游」
├── 依赖 infra（工具库，多个 venv 实装）              → 需要「版本锚点 + 漂移检测」
└── 自己的代码                                       → 普通 git
```

**场景 B：资产密集型项目（视频制作）**

```
video
├── 工程文件/脚本/配置   → 小，进 git
├── 素材（拍摄/配音/模型）→ 38 GB，隐私，不能上 GitHub
└── 交付物               → 大，需要版本化但不进 git
```

两者是同一模型的不同权重；gitmove 必须同时服务。

---

## 2. 核心概念

| 概念 | 定义 |
|---|---|
| **Workspace（工作区）** | 一个被 gitmove 纳管的项目根目录；含四个平面 |
| **Revision（修订）** | 一次提交产生的不变量：`git_commit` + `asset_snapshot` + `deps` + `env_hash` |
| **Plane（平面）** | 代码 / 资产 / 依赖 / 配方；每平面可独立运作，也可被 Revision 绑定 |
| **Dependency（依赖）** | 项目对另一个项目的声明（名字、ref/commit、实装版本、漂移） |
| **Contribution（回推）** | 在依赖的工作副本里改动并推送回上游（分支 + bundle 降级） |
| **Recipe（配方）** | `[env]` 步骤：重建 venv / node_modules / 模型等可再生内容 |
| **Policy（策略）** | 冻结（skip-worktree）、外部链接、忽略规则 |

---

## 3. 功能需求

优先级：P0 = 2.0 必须有；P1 = 2.1；P2 = 以后。

### FR-1 工作区纳管（P0）

- `gitmove init [--repo <path>]`：在已有 git 仓库初始化 `.gitmove/`（config + index）
- `gitmove project add|list|remove|scan|repair`：多项目注册表（沿用现有语义）
- 读取旧版 `.git/gitmove.toml`（只读兼容），新写入 `.gitmove/config.toml`

**验收**
- [ ] 对已有 git 仓库 `init` 后，`stack` 不破坏现有工作区（无改动、无新 commit）
- [ ] 旧配置可读：字段逐项映射，未知字段保留不报错
- [ ] 未初始化仓库上执行读命令（`status`/`doctor`）给出明确引导而非崩溃

### FR-2 变更可视化（P0）

- `gitmove status`：一次列出四个平面的状态（代码改动数、资产待备份量、依赖漂移、配方过期）
- `--json`：稳定 schema（`schema_version` 字段）

**验收**
- [ ] 视频项目：显示"代码 0 改动 / 资产有 12 个新文件约 3.2 GB 待备份"
- [ ] 依赖项目：显示"infra v0.5.0 → 实装 0.2.1（漂移）"

### FR-3 Revision 提交（P0）

- `gitmove commit -m "..."`：
  1. 代码平面：`git add -A` + commit（`--no-code` 可跳过）
  2. 资产平面：restic 备份（`--no-assets` 可跳过；无 `[depot]` 时跳过）
  3. 依赖平面：快照 `project.lock.toml`
  4. 写入 Revision：**SQLite 索引 + git commit trailer 双写**
- 提交是原子的：任一平面失败 → 不写 Revision，返回明确错误
- `--async`：资产备份转后台任务，UI 显示进度（大素材不能阻塞界面）

**验收**
- [ ] 提交后 `git log -1 --format=%B` 含 `Gitmove-Revision: <id>`
- [ ] SQLite `revisions` 行与 trailer 的 id/commit 一致
- [ ] 资产备份失败（拔盘）→ 退出码非 0，且不产生 Revision
- [ ] 无 `[depot]` 的项目提交只走代码平面，不报错

### FR-4 时间线与回滚（P0）

- `gitmove log [--json]`：Revision 列表（id、message、git commit、快照、依赖、时间）
- `gitmove show <rev>`：这一修订里三个平面各发生了什么
- `gitmove checkout <rev>`：
  - 代码平面：`git checkout <commit>`（默认 detached 或 `--branch`）
  - 资产平面：restic 恢复到工作区（预览 → 确认）
  - 默认**先预览**；`--force` 才在脏工作区执行

**验收**
- [ ] 回滚后文件内容与素材与该 Revision 一致（抽查 + 校验和）
- [ ] 脏工作区回滚必须 `--force`，否则拒绝并列出将被覆盖的文件
- [ ] `--code-only` / `--assets-only` 可单平面回滚

### FR-5 依赖声明与漂移（P0，承接 1.1）

- 读取项目根 `project.lock.toml`（项目级公开契约，gitmove 只读）
- `gitmove dep list|status`：声明版本 / 实装版本 / 漂移
- `gitmove doctor` 依赖检查：未注册、漂移、锚点过期、ref 与 commit 不一致

**验收**
- [ ] 6 个真实仓库巡检：未初始化项目不显示"0 文件"假数据
- [ ] 中文路径体积正确（quotePath 安全）
- [ ] 漂移在 UI 与 CLI 中一致可见

### FR-6 依赖回推（P0，承接 F 组）

- `gitmove dep diff <name>`：预览将回推的内容
- `gitmove dep contribute <name> [--branch] [--no-push]`：commit → fetch → rebase → push
- 冲突：中止 rebase、保留现场、列出冲突文件，**不自动解决**
- 推送失败：生成 `contrib-<name>-<日期>.bundle`，退出码 0，打印导入指令

**验收**
- [ ] 无改动时明确提示，不产生空 commit
- [ ] bundle 可被 `git clone` 打开
- [ ] 冲突后 cache 不处于 rebase 中间态

### FR-7 资产平面（P0，承接 E 组）

- `gitmove asset init|status|backup|snapshots|check|prune|restore`
- 保留策略透传 restic（不重造 `--keep-*` 语言）
- restic 不捆绑；缺失时给安装指引，代码平面仍可用

**验收**
- [ ] 视频项目：应备份 ≈ 4 GB（不是 38 GB），二次备份传输 ≈ 0
- [ ] 拔盘时 `check` 给出"目标不可达"而非崩溃
- [ ] 目标路径不可写 → 明确报"目标问题"

### FR-8 灾难恢复（P1）

- `gitmove restore <alias> --target <空目录> [--rev <id>] [--env]`
- 顺序：git clone → 配置导入 → 策略应用 → 资产恢复 → 配方执行

**验收**
- [ ] 目标非空时拒绝
- [ ] 恢复后的项目能通过自身 `doctor`

### FR-9 多项目管理（P0）

- 批量：`apply` / `doctor` / `backup` / `audit`（`--all`、`--group`）
- 视图：`--deps-of <alias>` 只显示该项目 + 其依赖
- GUI：侧栏全量导航，右侧按依赖过滤

### FR-10 CLI 契约（P0）

- 命令名沿用 1.x（降低迁移成本），新增 `commit/log/show/checkout/daemon/mcp`
- 所有读命令支持 `--json`（稳定 schema + `schema_version`）
- 退出码：0 成功 / 1 用户错误 / 2 环境缺失（restic 不在 PATH 等）

### FR-11 MCP（P1）

- stdio MCP server：tools（读写分离）、prompts（诊断/安全写/依赖接入）、resources（错误目录、注册表、文档）
- 写工具双门禁：`confirm=true` + 环境变量允许写
- 与 CLI 同源（同一核心库，不复制逻辑）

### FR-12 GUI（P0）

Electron 主进程 + Vue 渲染层，页面：

| 页面 | 内容 |
|---|---|
| 总览 | 工作区状态（四平面）、一键建议动作、健康摘要 |
| 变更 | 未提交改动：代码 diff 摘要 + 资产待备份清单 |
| 时间线 | Revision 列表、详情、回滚（预览）+ 提交对话框 |
| 依赖 | 声明/实装/漂移、回推（diff → contribute）、依赖图 |
| 备份 | depot 状态、快照、备份/校验/清理、恢复 |
| 设置 | 排除策略、配方、MCP、路径 |

**验收**
- [ ] 视频项目：从打开到完成一次提交（含资产）不超过 3 次点击
- [ ] 所有破坏性操作有确认对话框，并显示"将影响什么"

---

## 4. 非功能需求

| 类别 | 要求 |
|---|---|
| 启动 | 冷启动到可交互 < 1.5 s（6 项目注册表） |
| 只读性能 | `audit --all` < 500 ms（有索引）/ < 2 s（冷） |
| 安装包 | Electron 版 < 100 MB（安装后 < 250 MB） |
| 内存 | 空闲 daemon < 80 MB；UI 主进程 < 250 MB |
| 安全 | 渲染层 `contextIsolation: true`、`nodeIntegration: false`、严格 CSP；默认不联网 |
| 可观测 | 结构化日志（JSON lines）、`--verbose`、日志位置可在设置中打开 |
| 数据 | 索引可删除重建；git/restic 是事实源 |
| 平台 | Windows 优先（x64）；macOS/Linux 编译可跑，不承诺安装包 |

---

## 5. 验收基准（真实项目）

| 场景 | 期望 |
|---|---|
| 视频项目（38 GB） | 提交一次：代码 commit + 资产快照，UI 显示进度；回滚可还原指定集 |
| 依赖项目（6 仓库） | `audit` 真实文件数（infra 294 / resmgr 1012 / mysite 810 / spec 234） |
| 依赖回推 | 在项目内改 spec skill → `dep diff` 可见 → `contribute` 生成分支/PR 前置 |
| 断网 | `contribute` 降级 bundle，退出码 0 |
| 旧项目迁移 | 读旧 `.git/gitmove.toml`，命令行为与 1.1 一致（金样测试） |

---

## 6. 里程碑

| 阶段 | 交付 | 退出条件 |
|---|---|---|
| **M0** | 本需求定稿 + 架构 + ADR | 本文标注"已确认" |
| **M1** | Electron+Vue 壳接现有 Python CLI（`--json`） | 5 个核心场景可用；安装包可装 |
| **M2** | Rust core 只读（scan/index/doctor/audit） | 与 Python 逐字段 JSON 对比一致 |
| **M3** | Revision（commit/log/show/checkout） | 视频项目实测提交+回滚 |
| **M4** | 写路径（apply/skip/link/dep/asset） | 1.x 金样测试全过 |
| **M5** | MCP + Vue 全功能 | 三端同源验证 |
| **M6** | Python 下线 | 单二进制发布 |

---

## 7. 范围外（不做）

1. 自研 git 对象库/历史/diff/merge
2. 自研去重/压缩/加密/存储引擎（restic）
3. git LFS / annex 式素材入 git
4. 云同步 / 团队协作后端 / 远端托管
5. 通用备份工具（全盘备份）
6. 在 gitmove 里渲染 AI 规范（spec 职责）
7. 为"新语言"而新语言：只有实测瓶颈才引入优化

---

## 8. 开放问题（需确认）

| # | 问题 | 建议 |
|---|---|---|
| 1 | Revision id 形态 | 每工作区自增整数（易读，trailer 短） |
| 2 | 提交时资产备份是否默认同步 | 默认同步；>1 GB 或 `--async` 转后台 + 进度条 |
| 3 | `checkout` 默认模式 | detached HEAD + 明确提示；`--branch` 才建分支 |
| 4 | 依赖名用 alias 还是 lock 里的 name | 优先 lock 的 `name`，回退 alias |
| 5 | GUI 是否内置终端 | 不做；保留"打开所在目录/编辑器" |
| 6 | 是否保留 1.x 全部 27 个命令名 | 是（迁移友好），废弃项标 deprecated 一个版本 |
