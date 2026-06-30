# gitmove 多项目管理

**状态**：已定稿  
**版本**：0.3.0（CLI）/ 0.3.1（GUI 侧栏）  
**依赖**：`gitmove-core.md`（v0.2.0+）、`config import/export`、`sync check/pull`

## 背景与问题

用户常在多台/多个 Git 仓库间切换，每个仓库各有 `.git/gitmove.toml`。当前 gitmove **一次只能操作一个仓库**（CLI 依赖 cwd，GUI 需手动「选择仓库」），缺少：

- 常用项目清单与快速切换
- 跨项目批量 `doctor` / `apply` / `sync`
- GUI 中一览多项目健康状态

## 目标

在用户主目录维护**本地项目注册表**，与 per-repo 配置解耦：

1. **注册**常用 Git 仓库（路径、别名、可选分组）
2. **解析**操作目标：全局 `-C` / `--repo`、别名、默认项目
3. **批量**健康检查、应用配置、远程 sync（交互式）
4. **GUI** 侧栏项目列表与切换（v0.3.1）

Per-repo 配置**仍仅**写入 `<repo>/.git/gitmove.toml`，注册表不复制 skip/link 内容。

## 不交付

- 修改团队 `.gitignore`
- 云端 / 跨机器同步项目注册表
- 团队共享项目列表或权限
- 自动扫描全盘 Git 仓库（仅手动注册 +「添加当前目录」）
- 一个全局 TOML 替代各仓库 `gitmove.toml`
- 多窗口同时编辑多个仓库
- 替代 Git 或 Git 托管平台 API

## 术语

| 术语 | 含义 |
|------|------|
| **注册表** | 用户级 `~/.gitmove/projects.toml`，记录项目指针 |
| **项目** | 一个已注册的 Git 仓库根目录 |
| **别名 (alias)** | 注册表内唯一短名，用于 `-C alias` |
| **仓库配置** | 各仓库内 `.git/gitmove.toml`（已有） |

## 数据模型

### 注册表路径

| 平台 | 路径 |
|------|------|
| 全部 | `~/.gitmove/projects.toml` |

目录不存在时首次写入自动创建。不进 Git、不提交到任何业务仓库。

### 注册表结构（TOML）

```toml
[settings]
default_project = "gitmove"   # 可选；别名

[[projects]]
path = "E:/项目/gitmove"        # 必填；规范化绝对路径
alias = "gitmove"               # 必填；注册表内唯一
group = "personal"                # 可选；用于 list --group 过滤
notes = ""                        # 可选
last_used = "2026-06-29T12:00:00" # ISO8601；切换时更新

[[projects]]
path = "E:/项目/other-app"
alias = "other"
group = "work"
```

**约束**：

- `path` 必须为绝对路径，保存前 `resolve()` 规范化
- `alias` 唯一；仅允许 `[a-zA-Z0-9_-]`，长度 1–64
- 同一 `path` 不可重复注册
- `path` 不必存在（允许先注册后 clone），但 `list` / `doctor` 须标记 `missing`

### 与仓库配置的关系

```
~/.gitmove/projects.toml          <repo>/.git/gitmove.toml
        │                                    │
        │  path 指针                          │ skip / link / worktree
        └──────────────┬─────────────────────┘
                       ▼
              gitmove 业务模块（doctor / apply / sync …）
```

## 操作目标解析优先级

所有支持仓库上下文的子命令，按以下顺序确定 `root: Path`：

1. 显式 `--repo` / `-C <path|alias>`
2. 环境变量 `GITMOVE_REPO`（路径或别名）
3. `[settings].default_project` 对应别名（若设置且路径有效）
4. 当前工作目录 `git rev-parse --show-toplevel`（与现行为一致）

未解析到有效 Git 仓库时，报错退出，exit code 1。

## CLI 契约

### 子命令组 `gitmove projects`

| 命令 | 说明 |
|------|------|
| `projects list [--group G]` | 表格：别名、路径、分组、已 init、路径存在、错误数摘要 |
| `projects add [path] [--alias A] [--group G]` | 注册；默认 path=cwd；alias 默认取目录名 |
| `projects remove <alias\|path>` | 从注册表移除（不删 `.git/gitmove.toml`） |
| `projects set-default <alias>` | 设置 `default_project` |
| `projects doctor [--all] [--group G]` | 单项目或批量 doctor |
| `projects apply [--all] [--group G]` | 单项目或批量 apply |
| `projects sync check [--all] [--group G]` | 批量 sync check |
| `projects sync pull [--all] [--group G]` | 批量交互式 sync pull |

**单项目模式**（无 `--all`）：须配合 `-C` / `default_project` / cwd 之一；行为等同对应根命令。

**`--all`**：对注册表中 `path` 存在的项目依次执行；`path` 缺失的项跳过并计入报告。

### 全局选项

```
gitmove --repo, -C <path|alias>  <子命令> ...
```

示例：

```bash
gitmove -C other doctor
gitmove -C E:/项目/gitmove sync pull
gitmove projects add . --alias gitmove --group personal
gitmove projects doctor --all
gitmove projects sync pull --all --group work
```

### 批量 doctor / apply 输出

- 使用 Rich 表格：项目、errors、warns、ok
- 任一项目 `error_count > 0` → 进程 exit code 1
- 路径不存在 → 行内标记 `MISSING`，不计入 exit code（仅警告）

### 批量 sync 交互模型

**两级交互**（默认开启，不可静默跳过文件级选择）：

**第一级 — 项目**（`sync pull --all` 时）：

```
=== 项目: other (E:/项目/other-app) ===
2 个 skip 路径需关注。是否处理此项目？
  [y] 继续  [n] 跳过整个项目
```

**第二级 — 文件**（复用现有 `sync.default_chooser`）：

对每个 `needs_attention` 的 skip 路径：

```
config.local.json  本地已改: 是  远程有更新: 是
  [l] 保留本地  [r] 采用远程  [m] 合并  [s] 跳过此文件
```

单项目 `gitmove sync pull`（非 `--all`）仅第二级，行为与 v0.2.x 一致。

**`sync check --all`**：仅输出报告，不交互。

### 与已有命令的关系

| 已有 | 多项目后 |
|------|----------|
| `gitmove doctor` | 不变；可加 `-C` |
| `gitmove apply` | 不变；可加 `-C` |
| `gitmove sync pull` | 不变；可加 `-C` |
| `gitmove config import` | 不变；可加 `-C`；import 后不自动注册（用户可 `projects add`） |

## GUI 契约（v0.3.1）

### 布局

- **左侧**：可滚动项目列表（别名 + 分组标签）；当前项高亮
- **右侧**：现有 Tab（概览 / Skip / 链接 / Worktree），绑定当前选中项目
- **底栏**：保留状态文本

### 行为

- 启动：读取注册表；若有 `default_project` 则选中，否则选第一项或空态
- 点击项目：调用现有 `set_repo(path)` + `touch_last_used`
- 「添加项目」：目录选择器 → `projects.add` → 刷新列表
- 「从当前目录添加」：若已打开有效仓库则一键注册
- 「全部 doctor」/「全部 apply」：后台队列执行，进度与结果摘要（不阻塞 UI）
- 单项目 sync：工具栏按钮（复用 CLI 交互逻辑或对话框链）

### 不在 v0.3.1 交付

- 批量 `sync pull --all` 的 GUI 向导（可后续版本）
- 注册表在线编辑分组/备注的复杂表单（v0.3.1 仅 add/remove）

## 模块划分

| 模块 | 职责 |
|------|------|
| `registry.py`（新） | 读写 `~/.gitmove/projects.toml`；增删查；解析 alias |
| `projects.py`（新） | 批量 doctor/apply/sync 编排；汇总 `ProjectSummary` |
| `cli.py` | `projects` 子命令；全局 `-C` 注入 |
| `gui/app.py` | 侧栏与批量操作（v0.3.1） |
| 既有 `doctor` / `skip` / `sync` / … | **不修改**业务语义，仅接收 `root: Path` |

## 验收标准

### v0.3.0（CLI）

- [x] 注册表读写与 alias 唯一性校验
- [x] `projects list|add|remove|set-default`
- [x] 全局 `-C` / `GITMOVE_REPO` 解析 alias 与绝对路径
- [x] `projects doctor --all` / `projects apply --all` 表格输出与 exit code
- [x] `projects sync check --all` 汇总报告
- [x] `projects sync pull --all` 两级交互；单文件策略与 `sync.py` 一致
- [x] 路径不存在时 list/doctor 标记 MISSING，不崩溃
- [x] 单元 + 集成测试；核心模块覆盖率 ≥ 80%
- [x] README 增加「多项目管理」章节

### v0.3.1（GUI）

- [x] 侧栏展示注册项目并切换
- [x] 添加 / 移除项目
- [x] 「全部 doctor」「全部 apply」后台执行
- [x] GUI 集成测试（headless 可测部分）

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 仓库搬家导致 path 失效 | `list` 显示 MISSING；文档说明 `projects remove` + `projects add` |
| `--all` 交互次数多 | 项目级可先跳过；`sync check --all` 先巡检 |
| Windows / Unix 路径混用 | 存盘统一绝对路径；不存 `~` 未展开形式 |
| GUI 与 CLI 注册表竞争写 | 单进程 GUI；CLI 短事务读写整文件 |

## 验证

```bash
pip install -e ".[dev]"
pytest tests/test_registry.py tests/test_projects.py -v --cov=gitmove

# 手工冒烟
gitmove projects add "E:/项目/gitmove" --alias gitmove --group personal
gitmove projects list
gitmove -C gitmove doctor
gitmove projects doctor --all
gitmove projects sync check --all
gitmove projects sync pull --all   # 交互
```

## 版本路线图

| 版本 | 范围 |
|------|------|
| **0.3.0** | 注册表 + CLI `projects` + `-C` + 批量 doctor/apply/sync |
| **0.3.1** | GUI 侧栏 + 全部 doctor/apply |
| **0.4.0**（占位） | `projects repair`、按分组模板 `config import`、导入后可选自动注册 |

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-29 | 初稿定稿：注册表、CLI 契约、批量 sync 两级交互、GUI v0.3.1 范围 |
