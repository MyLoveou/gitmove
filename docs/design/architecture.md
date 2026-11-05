# 架构（v2）

> 状态：**分析定稿**（2026-11-06）。实现按里程碑推进（见需求文档 §6）。

---

## 1. 分层

```
┌──────────────────────────── Electron (Node) ─────────────────────────────┐
│ main: 窗口 / 菜单 / 对话框 / 自动更新 / 日志 / 原生通知                   │
│   │  contextBridge + IPC（渲染层不接触 node/fs）                          │
│ renderer: Vue 3 + Vite + Pinia + Vue Router                              │
│   总览 · 变更 · 时间线 · 依赖 · 备份 · 设置                                │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ JSON-RPC 2.0 over stdio（长驻 sidecar，单进程）
┌───────────────▼──────────────────────────────────────────────────────────┐
│ gitmove-core (Rust)                                                      │
│  cli      clap，命令名兼容 1.x                                            │
│  daemon   JSON-RPC 服务（Electron / 其它客户端）                          │
│  mcp      stdio MCP（tools/prompts/resources）                            │
│  domain   workspace / revision / dependency / policy / recipe             │
│  planes   code(git CLI) · asset(restic CLI) · dep(lock) · env(recipe)     │
│  index    SQLite（rusqlite）：workspace / revision / audit 缓存           │
│  scan     并行遍历、哈希、ignore、quotePath 安全                          │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ 进程调用（不拥有存储引擎）
          git · restic · 系统 shell（配方步骤）
```

**一个二进制，三种入口**：`gitmove <cmd>`、`gitmove daemon`、`gitmove mcp`。避免三套逻辑。

---

## 2. 工作区模型（多仓组合）

一个大项目 = **Workspace**，由 1..N 个 **Member** 组成。这是 v2 与 1.x 最大的结构差异：
1.x 把"依赖"当成项目内的一条声明；v2 把"依赖仓"当成**一等成员**，有身份、有策略、有 commit。

```
big-project/
├── workspace.toml            # 声明（入库）：成员、角色、策略、跟随分支/钉版本
├── workspace.lock.toml       # 生成（入库）：每个成员的 exact commit + 状态快照
├── .gitmove/                 # 索引/配置（索引可重建）
├── .git/                     # 主仓（可选；纯容器工作区没有）
├── app/                      # member: main
├── spec/                     # member: editable（AI 规范库；vendor + junction）
├── infra/                    # member: readonly（工具库；clone）
└── assets/                   # member: local（无远端；只备份）
```

### 2.1 成员的四类角色

| role | 典型 | 可改 | 可回推 | 进 Revision | 进资产备份 |
|---|---|---|---|---|---|
| `main` | 自己的主仓 | ✅ | —（它就是上游） | ✅ | 按策略 |
| `editable` | AI 规范库 | ✅ | ✅ | ✅ | 按策略 |
| `readonly` | 工具库/三方库 | ❌ | ❌ | ✅（只记录 commit） | 否 |
| `local` | 素材仓/私有代码 | ✅ | ❌（无远端） | ✅ | ✅ |

### 2.2 三种落盘策略

| strategy | 机制 | 适用 |
|---|---|---|
| `clone` | 直接在工作区内 `git clone`（嵌套真仓） | readonly 上游、local 仓 |
| `vendor` | clone 到用户缓存目录 + junction/symlink 进工作区 | editable 上游（改的是 cache 里的真文件，天然可回推） |
| `link` | 链接一个已存在的目录（不归 gitmove 管） | 外部共享目录 |

选择规则：**要回推就必须 `vendor`**（`clone` 也能改，但工作区里的仓会被 `.gitignore`/备份策略复杂化）。

### 2.3 两个 lock 的分工

| 文件 | 层级 | 内容 | 谁写 |
|---|---|---|---|
| `workspace.lock.toml` | 仓库级 | 每个 member 的 commit / ref / dirty / remote | gitmove 生成，入库 |
| `project.lock.toml` | 包级 | 某个成员内部的包实装版本（如 venv 里的 infra-watermark） | 项目/人工维护，入库 |

Revision 同时记录两者 hash，缺一不可。

### 2.4 同步语义

| 命令 | 做什么 | 改变 pin？ |
|---|---|---|
| `ws sync` | fetch + 检出到 lock 里的 commit | ❌ |
| `ws update --to <ref>` | 把成员前进到新 ref，写回 lock | ✅（需确认） |
| `ws status` | pin / HEAD / 漂移 / dirty / ahead / behind | ❌ |
| `ws contribute` | 把成员本地改动推回上游 | ❌（只推分支） |

### 2.5 资产平面：多目标备份

```
backup.target[]                 # workspace.toml
  ├── local  (E:/backup/...)    # 移动硬盘
  └── local  (F:/backup/...)    # 另一块盘 / NAS 挂载盘

# 2.0 只实现 local；remote 的字段保留，2.1 再开

asset backup --target all
  ├── 本地目标：restic backup → snapshot A  ── 记录到 revision_target
  └── 远程目标：restic backup → snapshot B  ── 记录到 revision_target
```

规则：

| 规则 | 说明 |
|---|---|
| 目标独立 | 每个目标有自己的 repo / 密码源 / 优先级；互不阻塞 |
| 备份结果按目标记录 | `revision_target(revision_id, target, snapshot_id, size, duration)` |
| 部分成功 | 退出码 2；UI 分列显示；`doctor` 对"远程副本落后"报警 |
| 恢复选源 | `--from <target>`；缺省按 `priority` 找第一个可达且含该 rev 快照的目标 |
| 凭据 | 环境变量 / 密码文件；密码文件不得位于任何 Git 仓库内 |
| 远程失败隔离 | 本地备份绝不因远程不可达而失败；反之亦然 |

### 2.6 分支与合并

**分支以 git 为准**，gitmove 只维护"工作区分支"的映射：

```
refs/gitmove/branches/feature-x   (git ref，内容是 JSON)
{
  "members": {"main": "feature-x", "spec": "feature-x", "infra": "v0.5.0-detached"},
  "assets": {"base_revision": 12}
}
```

- `switch <branch>`：逐成员 `git checkout <其分支>`；任一仓脏 → 拒绝
- `merge <branch>`：逐成员 `git merge <成员分支>`；冲突即停（不自动解决）
- 工作区合并成功后生成合并 Revision：`parents = [HEAD, branch]`
- 资产**不做内容合并**：`--assets ours|theirs|both`
  - `ours`（默认）：工作区素材保持当前；另一侧快照仅存档
  - `theirs`：恢复到被合并分支的最新快照
  - `both`：先备份当前，再恢复 theirs（保留两份）
- 合并 Revision 的 `revision_target` 记录实际使用的快照；`parents` 保留双亲，DAG 可画汇合

### 2.7 资产合并：三路文件级分析

资产（二进制）无法做内容拼接，但**可以分析**——以共同祖先为 base，逐文件判定归属。

#### 三方来源

| 侧 | 快照 |
|---|---|
| base | 合并双方的最近共同祖先 Revision 的资产快照 |
| ours | 当前工作区 HEAD Revision 的资产快照 |
| theirs | 被合并分支最新 Revision 的资产快照 |

#### 判定表（path 维度）

| base | ours | theirs | 结果 |
|---|---|---|---|
| 无 | 有 | 无 | 取 ours（新增） |
| 无 | 无 | 有 | 取 theirs（新增） |
| 无 | 有 | 有 | 内容哈希相同 → 一份；不同 → **冲突** |
| 有 | 改 | 未改 | 取 ours |
| 有 | 未改 | 改 | 取 theirs |
| 有 | 改 | 改 | 哈希相同 → 自动；不同 → **冲突** |
| 有 | 删 | 未改 | 删除 |
| 有 | 未改 | 删 | 删除 |
| 有 | 删 | 改 | **冲突**（删 vs 改） |
| 有 | 改 | 删 | **冲突**（改 vs 删） |
| 有 | 删 | 删 | 删除 |

#### 数据来源（不读全量内容）

`snapshot_file` 索引记录每个快照的 `path / size / mtime / blake3`：

- `path/size/mtime` 来自 `restic ls --json`（快，不读数据）
- `blake3` 由 core 扫描时增量维护（`mtime+size` 未变则复用缓存）
- 判定"内容是否相同"用 `blake3`；缺失时只在**双方 size/mtime 都不同**才判冲突，必要时用 `restic dump` 流式哈希（仅少数文件）

#### 合并状态与收尾

```
.gitmove/merge-state.toml
  base = 12
  ours = 20
  theirs = 18
  conflicts = [
    { path = "素材/第1集/a.mp4", reason = "both-modified", ours_hash, theirs_hash, ours_size, theirs_size },
    { path = "素材/第1集/b.wav", reason = "delete-vs-modify" },
  ]
  auto_merged = [ ... ]
```

- `auto`：应用无歧义结果，写冲突清单，工作区进入"合并中"；`ws commit` 被拒绝，直到冲突清零
- 冲突解决：`ws merge --resolve <path> --take ours|theirs|both`（`both` 会重命名为 `<name>.theirs.<ext>`）
- `ws merge --continue` 生成合并 Revision（parents=[ours, theirs]，`revision_target` 记录实际快照）
- `ws merge --abort`：恢复合并前工作区与 Revision

#### UI

冲突面板按 reason 分组，显示两侧 size/hash 与（可选）视频首帧缩略图；每行三个动作（保留我们/保留他们/都留）。

---

## 3. 关键决策（摘要）

| ID | 决策 | 理由 |
|---|---|---|
| ADR-0001 | Electron + Vue 3 + Vite | 用户指定；打包与生态成熟 |
| ADR-0002 | Rust 核心，单二进制三入口 | 单文件分发、并发扫描、SQLite |
| ADR-0003 | git 用 CLI，`gix` 仅只读加速 | 行为与真 git 一致，避免第二套语义 |
| ADR-0004 | restic 为资产引擎，不捆绑 | 已实测增量 0 B；缺失可降级 |
| ADR-0005 | Revision 双写：SQLite + git trailer | 索引快，trailer 让换机/裸仓库也能读 |
| ADR-0006 | 新仓库增量接管，不推倒重来 | 450 个测试是行为金样 |
| ADR-0007 | 前端只经 JSON-RPC sidecar | 壳可换（Tauri）、崩溃隔离 |
| ADR-0008 | 工作区布局 `.gitmove/`，旧配置只读 | 不污染 `.git/`，迁移平滑 |

详见 [decisions](../decisions/decisions.md)。

---

## 4. Revision 流程

### 4.1 提交（含成员）

```
1. 预检：workspace 已初始化；成员路径存在；成员是否干净；restic 可用性（若含资产）
2. 预留 revision id：INSERT INTO revision(status='pending')
3. 代码平面（若主仓存在）：git add -A && git commit -m "<msg>\n\nGitmove-Revision: <id>"
   — 成员脏且未传 --members → 拒绝（不产生 Revision）
   — --members：对每个脏成员各做一次 commit，消息后缀 "[rev <id>]"
4. 成员平面：对每个 member 执行 git rev-parse HEAD → revisions_members
5. 资产平面：对每个启用的 backup.target 各做一次 restic backup（互不阻塞，按目标记录结果）
6. 依赖平面：读 project.lock.toml → deps_json
7. 配方平面：hash([env].steps)
8. UPDATE revision SET status='ok', git_commit, snapshot, lock_hash, branch
   任一步失败 → 删除 pending 行，返回错误（已提交的 git commit 不回退，明确告知）
   注：多目标部分失败仍视为成功提交（status='ok'，对应 target 行标 failed），退出码 2
```

### 4.2 回滚

```
gitmove checkout <rev> [--code-only|--assets-only] [--members-only] [--force]
1. 解析 rev（SQLite；缺则扫 git trailer 重建）
2. 预检：任一仓脏则要求 --force，并列出将被覆盖的文件（按仓分组）
3. 代码平面：对主仓与每个成员 git checkout <rev 记录的 commit>（detached）
4. 资产平面：restic restore <snapshot> --target <workspace>（预览 → 执行）
5. 校验：逐仓断言 HEAD == 记录值；抽查文件哈希；失败报告"部分恢复"并列出未还原项
```

### 4.3 trailer 恢复（换机场景）

SQLite 丢失时，`gitmove index rebuild`：遍历 `git log --format=%B`，解析 `Gitmove-Revision:`，重建 revisions 表（无资产快照信息 → 标记 `snapshot=null`，并提示用户提供 restic 仓库）。

---

## 5. 数据模型（SQLite）

```sql
CREATE TABLE workspace(
  id INTEGER PRIMARY KEY, path TEXT UNIQUE, name TEXT,
  created_at TEXT, legacy_config INTEGER DEFAULT 0
);
CREATE TABLE revision(
  id INTEGER, workspace_id INTEGER, status TEXT,      -- pending|ok|failed
  git_commit TEXT, snapshot TEXT, env_hash TEXT,
  deps_json TEXT, message TEXT, created_at TEXT,
  branch TEXT,                                        -- 工作区分支（可空）
  PRIMARY KEY(workspace_id, id)
);
CREATE TABLE revision_parent(
  workspace_id INTEGER, revision_id INTEGER, parent_id INTEGER,
  PRIMARY KEY(workspace_id, revision_id, parent_id)
);
CREATE TABLE revision_target(                         -- 每个备份目标的快照
  workspace_id INTEGER, revision_id INTEGER, target TEXT,
  snapshot_id TEXT, size_bytes INTEGER, duration_ms INTEGER,
  status TEXT,                                        -- ok|failed
  PRIMARY KEY(workspace_id, revision_id, target)
);
CREATE TABLE snapshot(
  workspace_id INTEGER, target TEXT, snapshot_id TEXT, size_bytes INTEGER,
  files INTEGER, created_at TEXT, PRIMARY KEY(workspace_id, target, snapshot_id)
);
CREATE TABLE snapshot_file(
  workspace_id INTEGER, target TEXT, snapshot_id TEXT, path TEXT,
  size INTEGER, mtime INTEGER, blake3 TEXT,
  PRIMARY KEY(workspace_id, target, snapshot_id, path)
);
CREATE TABLE branch(
  workspace_id INTEGER, name TEXT, members_json TEXT, assets_base INTEGER,
  updated_at TEXT, PRIMARY KEY(workspace_id, name)
);
CREATE TABLE member(
  workspace_id INTEGER, name TEXT, path TEXT, role TEXT,
  strategy TEXT, source TEXT, track TEXT, pin_ref TEXT, backup INTEGER,
  PRIMARY KEY(workspace_id, name)
);
CREATE TABLE revision_member(
  workspace_id INTEGER, revision_id INTEGER, member TEXT,
  commit_sha TEXT, dirty INTEGER DEFAULT 0,
  PRIMARY KEY(workspace_id, revision_id, member)
);
CREATE TABLE audit_cache(
  workspace_id INTEGER, key TEXT, value_json TEXT, computed_at TEXT,
  PRIMARY KEY(workspace_id, key)
);
```

索引可删：`gitmove index rebuild` 从 git/restic/文件系统重建。

---

## 6. 磁盘布局

```
<workspace>/
├── .git/
├── .gitmove/
│   ├── config.toml        # 策略/配方/depot 配置（替代 .git/gitmove.toml）
│   └── index.sqlite       # 索引（可重建）
├── workspace.toml         # 多仓组合声明（入库）
├── workspace.lock.toml    # 成员 commit 锚点（生成、入库）
├── project.lock.toml      # 包级依赖声明（项目级公开契约，入库）
└── ...

%APPDATA%/gitmove/
├── projects.toml          # 注册表
├── cache/<vendor>/        # vendor cache
├── logs/daemon.log        # JSON lines
└── bin/                   # 可选：sidecar 与 restic 指引
```

---

## 7. daemon 协议（JSON-RPC 2.0）

```jsonc
// 请求
{"jsonrpc":"2.0","id":1,"method":"status","params":{"workspace":"D:/Project/视频制作"}}
// 响应
{"jsonrpc":"2.0","id":1,"result":{"schema_version":1,"code":{...},"asset":{...},"dep":{...}}}
// 长任务
{"jsonrpc":"2.0","id":2,"method":"commit","params":{"message":"第一集","assets":true}}
{"jsonrpc":"2.0","method":"progress","params":{"job":"commit","phase":"backup","percent":42}}
{"jsonrpc":"2.0","id":2,"result":{"revision":12,"commit":"a1b2c3d","snapshot":"9f8e7d"}}
```

错误统一：`{code: "GITMOVE_XXX", message, data:{hint, steps[]}}`（沿用 1.x 错误目录，可作为 MCP resource 暴露）。

---

## 8. 模块划分（Rust workspace）

```
crates/
├── core/       # domain + planes + index + scan（无 UI 依赖）
├── cli/        # clap 命令
├── daemon/     # JSON-RPC 服务
├── mcp/        # rmcp server
└── xtask/      # 开发任务（生成 schema、跑金样对比）
```

规则：`core` 不得依赖 `cli/daemon/mcp`；`cli/daemon/mcp` 只做协议转换。

---

## 9. 与 1.x 的关系

| 1.x（Python） | 2.0（Rust） |
|---|---|
| `.git/gitmove.toml` | 只读导入 → `.gitmove/config.toml` |
| `depot`（restic 编排） | 资产平面 |
| `manifest` / `audit` / `doctor` | `status` / `audit` / `doctor`（索引加速） |
| `vendor`（含 contribute） | 依赖平面 |
| `env` / `bootstrap` | 配方平面 |
| MCP 26 tools | 同名迁移 + 新增 revision 工具 |

**兼容策略**：M1 的 Electron 壳直接调用 1.x CLI（`--json`），因此 2.0 的 UI 先于 Rust 核心可用；M2 起 Rust 只读核对，M4 写路径切换。

---

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| 索引与 git 不一致 | trailer 为权威；`index rebuild` 可重建；提交时双写校验 |
| 资产备份阻塞 UI | `--async` + 进度事件；超过阈值自动转后台 |
| restic 版本差异 | 启动时探测版本并记录；只依赖稳定参数（backup/restore/forget/check/snapshots） |
| Rust 学习曲线 | 先只读路径，写路径逐条迁移；金样测试护航 |
| Electron 体积/安全 | `contextIsolation`、CSP、不发网络请求、sidecar 只走 stdio |
| 迁移期双语言 | 冻结 Python 新功能，只修 bug；Rust 逐个接管 |
