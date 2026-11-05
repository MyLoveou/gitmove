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

## 2. 关键决策（摘要）

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

## 3. Revision 流程

### 3.1 提交

```
1. 预检：workspace 已初始化、工作区干净度、restic 可用性（若含资产）
2. 预留 revision id：INSERT INTO revisions(project, status='pending')
3. 代码平面：git add -A && git commit -m "<msg>\n\nGitmove-Revision: <id>"
4. 资产平面：restic backup（excludes 来自策略）
5. 依赖平面：读 project.lock.toml → deps_json
6. 配方平面：hash([env].steps)
7. UPDATE revisions SET status='ok', git_commit, snapshot, ...
   任一步失败 → DELETE pending 行（或标 failed），返回错误
```

### 3.2 回滚

```
gitmove checkout <rev> [--code-only|--assets-only] [--force]
1. 解析 rev（SQLite；缺则扫 git trailer 重建）
2. 预检：脏工作区必须 --force；列出将被覆盖的文件
3. 代码平面：git checkout <commit>
4. 资产平面：restic restore <snapshot> --target <workspace>（预览 → 执行）
5. 校验：抽查文件哈希；失败则报告"部分恢复"
```

### 3.3 trailer 恢复（换机场景）

SQLite 丢失时，`gitmove index rebuild`：遍历 `git log --format=%B`，解析 `Gitmove-Revision:`，重建 revisions 表（无资产快照信息 → 标记 `snapshot=null`，并提示用户提供 restic 仓库）。

---

## 4. 数据模型（SQLite）

```sql
CREATE TABLE workspace(
  id INTEGER PRIMARY KEY, path TEXT UNIQUE, name TEXT,
  created_at TEXT, legacy_config INTEGER DEFAULT 0
);
CREATE TABLE revision(
  id INTEGER, workspace_id INTEGER, status TEXT,      -- pending|ok|failed
  git_commit TEXT, snapshot TEXT, env_hash TEXT,
  deps_json TEXT, message TEXT, created_at TEXT,
  PRIMARY KEY(workspace_id, id)
);
CREATE TABLE snapshot(
  workspace_id INTEGER, snapshot_id TEXT, size_bytes INTEGER,
  files INTEGER, created_at TEXT, PRIMARY KEY(workspace_id, snapshot_id)
);
CREATE TABLE audit_cache(
  workspace_id INTEGER, key TEXT, value_json TEXT, computed_at TEXT,
  PRIMARY KEY(workspace_id, key)
);
```

索引可删：`gitmove index rebuild` 从 git/restic/文件系统重建。

---

## 5. 磁盘布局

```
<workspace>/
├── .git/
├── .gitmove/
│   ├── config.toml        # 策略/配方/depot 配置（替代 .git/gitmove.toml）
│   └── index.sqlite       # 索引（可重建）
├── project.lock.toml      # 依赖声明（项目级公开契约，入库）
└── ...

%APPDATA%/gitmove/
├── projects.toml          # 注册表
├── cache/<vendor>/        # vendor cache
├── logs/daemon.log        # JSON lines
└── bin/                   # 可选：sidecar 与 restic 指引
```

---

## 6. daemon 协议（JSON-RPC 2.0）

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

## 7. 模块划分（Rust workspace）

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

## 8. 与 1.x 的关系

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

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 索引与 git 不一致 | trailer 为权威；`index rebuild` 可重建；提交时双写校验 |
| 资产备份阻塞 UI | `--async` + 进度事件；超过阈值自动转后台 |
| restic 版本差异 | 启动时探测版本并记录；只依赖稳定参数（backup/restore/forget/check/snapshots） |
| Rust 学习曲线 | 先只读路径，写路径逐条迁移；金样测试护航 |
| Electron 体积/安全 | `contextIsolation`、CSP、不发网络请求、sidecar 只走 stdio |
| 迁移期双语言 | 冻结 Python 新功能，只修 bug；Rust 逐个接管 |
