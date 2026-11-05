# gitmove v2 · 需求文档（定稿中）

> 状态：**待确认**（2026-11-06）。确认后本文件冻结为 v2.0 基线，改动走变更记录。
> 仓库：`D:\Project\GitMove\gitmove-v2`（**新仓库**，与 Python 版 `gitmove` 并行，逐步接管）
> 已定技术决策见 [decisions](../decisions/decisions.md)；架构见 [architecture](../design/architecture.md)。

---

## 1. 产品定位

**一句话**：gitmove 是**项目工作区的版本控制与备份编排层**——把"代码（git）"和"大体积素材（restic）"编成同一个可回滚的**修订（Revision）**，并管理项目对其它项目的依赖。

更进一步：**一个大项目往往由多个 git 仓库组成**——自己的主仓 + AI 规范库 + 工具库 + 本地素材仓。
gitmove 把这种组合称为 **Workspace**，把每个仓库称为 **Member**；并要求**每个 Revision 记录所有成员的 commit**。
于是「回滚」不是只回主仓，而是整组代码（每仓回到当时的 commit）+ 素材（回到当时的快照）一起还原。

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
| **Workspace（工作区）** | 由 1..N 个 Member 组成的"大项目"；主仓可有可无（纯容器也合法） |
| **Member（成员仓）** | 工作区里的一个 git 仓库，带 `role` / `strategy` / `pin` |
| **MemberRole** | `main` 自己的主仓 · `editable` 可改并回推的上游（AI 规范库） · `readonly` 只读上游（工具库） · `local` 无远端、只备份（素材/私有代码） |
| **Strategy** | 成员的落盘方式：`clone`（嵌套真仓）· `vendor`（cache + junction）· `link`（外部目录链接） |

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

### FR-13 工作区组合（多仓管理）（P0）

一个 Workspace 用 `workspace.toml`（入库）声明成员；`workspace.lock.toml`（生成、入库）记录每个成员的精确 commit。

```toml
version = 1
[workspace]
name = "big-project"

[[member]]
name = "main"          # 主仓（可省略）
path = "."
role = "main"

[[member]]
name = "spec"          # AI 规范库：可改、可回推
path = "spec"
role = "editable"
source = "git@github.com:MyLoveou/cursor-project-spec.git"
track = "main"
strategy = "vendor"

[[member]]
name = "infra"         # 工具库：只读、钉版本
path = "infra"
role = "readonly"
source = "https://github.com/MyLoveou/infra.git"
pin = "v0.5.0"
strategy = "clone"

[[member]]
name = "assets"        # 本地素材仓：无远端、只备份
path = "assets"
role = "local"
backup = true
```

命令：

```
gitmove ws init                      # 识别当前目录下的仓库并生成 workspace.toml 草稿
gitmove ws add <path|url> [--role] [--strategy] [--pin]
gitmove ws list / ws status          # 成员：pin / HEAD / 漂移 / dirty / ahead / 待回推
gitmove ws sync [--member name]      # fetch + 检出到 lock 的 commit（不前进 pin）
gitmove ws update [--to <ref>]       # 前进 pin 并更新 lock（需确认）
gitmove ws remove <name>
```

**验收**
- [ ] 主仓 + spec + infra + assets 四成员：`ws status` 一次列清四个仓的 pin/HEAD/dirty
- [ ] 成员路径被误删 → 标 `MISSING` 并可 `ws sync` 重建
- [ ] `ws sync` 不改变 pin；`ws update` 才前进 pin，且要求确认
- [ ] Windows 下 `vendor` 策略用 junction，不复制 `.git`

### FR-14 多仓 Revision（P0）

- Revision 记录 **每个成员的 commit**（map），不只主仓
- `gitmove commit` 默认**只提交主仓**，并要求成员干净；成员脏 → 拒绝并提示
- `--members`：把脏成员一并提交（每个成员各自 commit，消息带 `[rev N]`）
- `--sync`：先把成员同步到 lock 再提交
- 无主仓（纯容器工作区）时，Revision 只含成员 commits + 资产快照
- `gitmove checkout <rev>`：主仓 + 每个成员都 checkout 到记录值，资产恢复到快照
- trailer 写入主仓 commit（无主仓时写入 `.gitmove/index.sqlite` 与 `workspace.lock.toml` 的 `revision` 字段）

**验收**
- [ ] `log` 显示的成员 commit 与 `git -C spec rev-parse HEAD` 一致
- [ ] 回滚到 rev N 后，四个仓的 HEAD 与记录完全一致（逐仓断言）
- [ ] 成员脏 + 不带 `--members` → 退出码非 0，且不产生 Revision
- [ ] 纯容器工作区（无主仓）可提交并可回滚

### FR-15 成员依赖的查看与回推（P0）

- `ws status` 每个可编辑成员显示：`pin → HEAD`、`dirty N`、`ahead N`、`上游 behind N`
- `gitmove ws diff <member>`：预览回推内容
- `gitmove ws contribute <member> [--branch] [--no-push]`：commit → fetch → rebase → push；冲突中止不自动解决；推送失败降级 bundle
- `readonly` 成员禁止 contribute（明确报错）

**验收**
- [ ] `spec` 有改动时 `ws status` 显示「待回推」，`ws contribute spec` 生成分支
- [ ] `readonly` 的 `infra` 上执行 contribute → 明确报错，不动仓
- [ ] 断网 contribute → bundle + 退出码 0

### FR-16 工作区级视图（P0）

- `gitmove status` 聚合：主仓改动 + 每个成员 dirty/pin 漂移 + 资产待备份 + 配方过期
- GUI：工作区页展示成员表（名字/角色/策略/pin/HEAD/漂移/dirty/待回推），点成员可跳转其页面
- 依赖图：workspace → members；一个成员自身还可以有包级依赖（`project.lock.toml`）

**验收**
- [ ] 成员表按角色分组，`editable` 的贡献状态一眼可见
- [ ] 从成员行可直接执行 sync / contribute / 打开目录

### FR-17 双备份目标：本地 + 远程（P0）

资产平面支持**多个备份目标同时存在**，一次备份同时写本地与远程；任一目标失败不阻断其它目标。

```toml
[[backup.target]]
name = "local-e"          # 本地移动硬盘
kind = "local"
repo = "E:/backup/big-project-restic"
password_file = "D:/secure/restic-pass.txt"

[[backup.target]]
name = "remote-s3"        # 远程对象存储（restic 原生后端）
kind = "remote"
repo = "s3:https://s3.example.com/bucket/big-project"
password_env = "RESTIC_PASSWORD_REMOTE"
priority = 2              # restore 时的尝试顺序（越小越优先）
```

命令：

```
gitmove asset target add|list|remove|test
gitmove asset backup [--target all|<name>]        # 默认 all
gitmove asset check  [--target all|<name>]
gitmove asset restore <rev> [--from <target>]     # 默认按 priority 找第一个可达目标
```

- Revision 记录**每个目标的 snapshot id**（同一份内容、不同仓库）
- 部分成功语义：本地成功、远程失败 → 退出码 2，UI 把远程标红，`doctor` 提示"远程副本过期"
- 凭据只从环境变量/密码文件读，绝不写入配置或日志

**验收**
- [ ] 一次 `asset backup` 后，本地与远程仓库都有快照，Revision 记录两条 snapshot id
- [ ] 拔掉移动硬盘：远程仍成功，退出码 2，本地目标标红（不阻塞）
- [ ] `asset restore --from remote-s3` 可从远程还原；`--from` 缺省时按 priority 选可达目标
- [ ] 密码文件位于 Git 仓库内 → 明确拒绝

### FR-18 分支与合并（P0，git 语义）

**代码平面直接用 git 的分支/合并**，gitmove 只做编排与可视化：

```
gitmove branch list|create <name>|switch <name>|delete <name>
gitmove merge <branch> [--assets ours|theirs|both] [--no-code]
```

- **工作区分支** = 每个成员当前所在分支的映射 + 资产指针，记在 `refs/gitmove/branches/<name>`（主仓）或索引里
- `switch`：逐成员切换；任一仓有未提交改动 → 拒绝并列出
- `merge`：逐成员 `git merge`；任一仓冲突 → 停止并列出冲突文件（**不自动解决**，与 git 一致）
- 合并成功 → 生成**合并 Revision**（`parents = [当前, 被合并]`），`log` 能画出分叉/汇合
- **资产没有内容合并**：`--assets ours|theirs|both`，默认 `ours`；另一侧快照仍保留可查，合并 Revision 记录两条 lineage
- 冲突解决后 `gitmove merge --continue` 收尾；`--abort` 回到合并前

**验收**
- [ ] 三个成员各建 `feature/x` 并切换：`branch list` 显示三仓一致，`switch main` 逐仓回到 main
- [ ] 制造成员冲突：`merge` 退出码非 0、列出冲突文件、不产生 Revision，`--abort` 可回退
- [ ] 合并 Revision 有两个 parents，`log --graph` 可画出汇合点
- [ ] `--assets theirs` 合并后工作区素材与 theirs 快照一致（抽查哈希）

### FR-19 可视化（P0）

| 视图 | 内容 |
|---|---|
| **版本 DAG** | Revision 节点 + 分支 + 合并点；点击节点看该 rev 的成员 commits / 快照 / 依赖 |
| **成员/依赖图** | workspace → members；member → 包级依赖；标出 editable/readonly/local |
| **备份矩阵** | target × 最近快照 × 大小 × 耗时 × 状态（本地/远程并排） |
| **变更面板** | 四平面：代码 diff 摘要、资产待备份量、依赖漂移、配方过期 |

**验收**
- [ ] 四个视图都能从总览一步进入
- [ ] 200+ revisions 下 DAG 滚动流畅（虚拟化）
- [ ] 备份矩阵在远程离线时清晰标红，且不影响本地列

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
| 备份可靠性 | 多目标互不阻塞；单目标失败退出码 2；远程凭据不进配置/日志 |
| 可视化性能 | 版本 DAG / 成员图 / 备份矩阵：200+ 节点可交互（虚拟化渲染） |

---

## 5. 验收基准（真实项目）

| 场景 | 期望 |
|---|---|
| 视频项目（38 GB） | 提交一次：代码 commit + 资产快照，UI 显示进度；回滚可还原指定集 |
| 多仓工作区 | `ws status` 列出主仓 + spec + infra + assets；`commit` 后 `log` 可见四个 commit |
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
| 7 | 成员脏时默认提交策略 | 默认**拒绝**，`--members` 才一并提交（避免误提交别人的仓） |
| 8 | 默认 strategy | 要改并回推 → `vendor`；只读上游 → `clone`；本地素材 → `clone`（本地仓） |
| 9 | `workspace.lock.toml` 与旧 `project.lock.toml` 关系 | 前者=仓库级 commit 锚点；后者=包级实装版本；Revision 同时记录两者 hash |
| 10 | 资产合并不冲突时的默认策略 | 默认 `ours`（保留当前），另一侧快照仍可查 |
| 11 | 远程备份后端范围 | 先用 restic 原生：`s3` / `sftp` / `rest` / `b2` / `azure`；不做自研上传 |
| 12 | 工作区分支是否也记录成员分支名 | 是：分支 = 每成员分支 + 资产指针，切换时可逐仓还原 |
