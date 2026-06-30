# gitmove 使用说明书

> 版本：v0.4.0 · 适用平台：Windows / macOS / Linux

---

## 1. 产品是什么

**gitmove** 帮助你在**不修改团队 `.gitignore`** 的前提下，管理「只对自己生效」的 Git 本地策略：

| 能力 | 解决什么问题 |
|------|--------------|
| **skip-worktree** | 已追踪文件（如 `config.local.json`）本地改了，但不想出现在 `git status`、也不想误提交 |
| **link（外部链接）** | 仓库内某个目录实际放在磁盘其他位置（个人盘、同步盘等） |
| **worktree** | 同一仓库再开一个独立工作目录做实验 |
| **vendor（上游依赖）** | 某个目录的内容来自**另一个 Git 仓库**，可单独 pull 更新 |
| **多项目** | 同时管理多个业务仓库，批量巡检与应用 |
| **config / sync** | 配置换机迁移；业务仓远程更新后与 skip 文件交互式 reconcile |

**重要原则**：

- 配置写在 `<仓库>/.git/gitmove.toml`，**不会提交**到业务仓
- 同事 clone 后看不到你的本地策略；换电脑需重新 `init` / `import` / `apply`
- 仍依赖系统已安装的 `git` 命令

---

## 2. 安装与启动

### 2.1 从源码安装（开发/日常使用）

```bash
cd /path/to/gitmove
pip install -e .
```

验证：

```bash
gitmove --version
git --version    # 必须可用
```

### 2.2 使用打包好的 exe / 二进制

从 [GitHub Releases](https://github.com/MyLoveou/gitmove/releases) 下载对应平台产物，解压后将目录加入 PATH，或直接使用：

| 文件 | 用途 |
|------|------|
| `gitmove` / `gitmove.exe` | 命令行 |
| `gitmove-gui` / `gitmove-gui.exe` | 图形界面（无黑窗口） |

### 2.3 启动 GUI

```bash
gitmove-gui
# 或
gitmove gui
gitmove gui --repo E:/项目/my-app    # 指定仓库
```

---

## 3. 核心概念

### 3.1 两层配置

| 层级 | 文件位置 | 内容 |
|------|----------|------|
| **仓库级** | `<repo>/.git/gitmove.toml` | skip、link、worktree、vendor |
| **用户级** | `~/.gitmove/projects.toml` | 多项目注册表（路径、别名、分组） |
| **Vendor 缓存** | `~/gitmove-vendor/<name>/` | 上游仓库的本地 clone |

### 3.2 常用命令关系

```
init          → 创建 .git/gitmove.toml
skip/link/... → 修改配置
apply         → 按配置恢复 skip、链接、worktree、vendor
doctor        → 检查配置与真实状态是否一致
sync pull     → 业务仓 git pull + skip 文件交互处理
vendor sync   → 仅更新上游 cache（与业务仓 pull 无关）
```

---

## 4. 五分钟快速上手

在任意 Git 仓库根目录：

```bash
# 1. 初始化
gitmove init

# 2. 标记一个本地配置文件（示例）
gitmove skip add config.local.json

# 3. 应用并检查
gitmove apply
gitmove doctor
```

之后修改 `config.local.json`，`git status` 通常不再显示该文件的本地变更。

---

## 5. 图形界面（GUI）使用

### 5.1 界面布局

- **左侧**：已注册项目列表（多项目）；可添加、移除、切换
- **顶部**：当前仓库路径、刷新、初始化 / 一键应用 / 健康检查
- **标签页**：
  - **概览**：doctor 结果、外部目录根路径
  - **Skip-worktree**：已配置的 skip 路径
  - **外部链接**：junction/symlink 链接
  - **Worktree**：个人 worktree

### 5.2 典型操作

1. **首次使用**：选择仓库 → 点「初始化」→ 在对应标签页添加 skip/link → 点「一键应用」
2. **换电脑后**：导入配置（CLI `config import`）→ GUI 点「一键应用」
3. **多项目**：左侧「添加项目」或「从当前目录添加」→ 切换项目 → 「全部 doctor / 全部 apply」

---

## 6. CLI 命令参考

全局选项（放在子命令前）：

```bash
gitmove -C <路径或别名> <子命令> ...
```

环境变量 `GITMOVE_REPO` 作用类似 `-C`（`-C` 优先）。

### 6.1 基础

| 命令 | 说明 |
|------|------|
| `gitmove init [--external-base PATH]` | 创建 `.git/gitmove.toml` |
| `gitmove apply` | 应用 skip / link / worktree / vendor |
| `gitmove doctor` | 健康检查（有问题时 exit 1） |
| `gitmove gui [--repo PATH]` | 打开 GUI |

### 6.2 skip-worktree

| 命令 | 说明 |
|------|------|
| `gitmove skip add <路径>` | 添加 skip（文件或目录下已追踪项） |
| `gitmove skip remove <路径>` | 取消 skip 并从配置移除 |
| `gitmove skip list` | 列出状态 |

**适用**：`appsettings.Development.json`、`config.local.json` 等**已被 Git 追踪**、但你只想本地改的文件。

### 6.3 外部链接 link

| 命令 | 说明 |
|------|------|
| `gitmove link set-base <目录>` | 设置默认外部根目录 |
| `gitmove link add <仓库内路径> [--external PATH] [--migrate]` | 创建链接 |
| `gitmove link list` | 列出链接 |
| `gitmove link remove <路径> [--delete-external]` | 移除链接 |

| 平台 | 默认链接类型 |
|------|--------------|
| Windows | junction |
| macOS / Linux | symlink |

**适用**：个人工具目录、大体积缓存等放在仓库外。

### 6.4 worktree

| 命令 | 说明 |
|------|------|
| `gitmove worktree add <名称> <绝对路径> [--branch B] [--new-branch]` | 添加 |
| `gitmove worktree list` | 列出 |
| `gitmove worktree remove <名称> [--force]` | 移除 |

### 6.5 配置导入导出

| 命令 | 说明 |
|------|------|
| `gitmove config export <文件.toml>` | 导出当前仓配置 |
| `gitmove config import <文件.toml> [--merge\|--replace] [--apply]` | 从文件导入 |
| `gitmove config import --from-repo <其他clone路径> [--base-override PATH]` | 从另一 clone 导入 |

### 6.6 业务仓 sync（skip 文件）

| 命令 | 说明 |
|------|------|
| `gitmove sync check [--fetch\|--no-fetch]` | 检查 skip 路径本地/远程差异 |
| `gitmove sync pull` | pull 并对有冲突的 skip 文件**交互选择** |

**sync pull 文件级选项**（本地和远程都改过时）：

| 按键 | 含义 |
|------|------|
| `l` | 保留本地 |
| `r` | 采用远程 |
| `m` | stash → pull → pop 合并 |
| `s` | 跳过此文件 |

### 6.7 多项目 projects

| 命令 | 说明 |
|------|------|
| `gitmove projects add [path] [--alias A] [--group G]` | 注册项目 |
| `gitmove projects list [--group G]` | 列表（轻量状态：OK / MISSING / NO_INIT） |
| `gitmove projects remove <别名或路径>` | 从注册表移除 |
| `gitmove projects set-default <别名>` | 设置默认项目 |
| `gitmove projects doctor [--all] [--group G]` | 批量 doctor |
| `gitmove projects apply [--all] [--group G]` | 批量 apply |
| `gitmove projects sync check [--all]` | 批量 sync 检查 |
| `gitmove projects sync pull [--all]` | 批量 sync（先问项目，再问文件） |

### 6.8 上游 Vendor

| 命令 | 说明 |
|------|------|
| `gitmove vendor add <repo_path> --from <url> [--name N] [--ref main] [--migrate]` | 添加 |
| `gitmove vendor list` | 列表 |
| `gitmove vendor status [名称或路径]` | cache commit、落后 commit 数等 |
| `gitmove vendor sync [名称或路径]` | FF-only 同步 cache |
| `gitmove vendor sync --all` | 同步全部（任一失败 exit 1） |
| `gitmove vendor remove <名称> [--purge-cache] [--no-keep-skip]` | 移除 |

**注意**：

- `repo_path` 必须是你在业务仓内**指定的路径**（含已追踪的 `.cursor`）
- 目录已存在且非链接时，需加 `--migrate` 才会迁移内容到 cache
- `vendor sync` 只更新 `~/gitmove-vendor/`，**不** pull 业务仓

---

## 7. 场景手册

### 场景 A：新 clone 后恢复策略

```bash
cd my-app
gitmove init
gitmove apply
gitmove doctor
```

若你有备份配置：

```bash
gitmove config import ~/backup/my-app.toml --apply
```

### 场景 B：本地配置文件（已追踪）

```bash
gitmove skip add appsettings.Development.json
gitmove doctor
```

远程也更新了同一文件：

```bash
gitmove sync check
gitmove sync pull
```

### 场景 C：个人目录放到盘外

```bash
gitmove link set-base ~/gitmove-external/my-app
gitmove link add tools/personal
gitmove apply
```

目录已存在时加 `--migrate` 可把内容迁到外部再建链接。

### 场景 D：换机迁移

**旧电脑**：

```bash
gitmove config export ./my-app-backup.toml
# 复制 my-app-backup.toml 和外部目录（若有 link）
```

**新电脑**：

```bash
gitmove init
gitmove config import ./my-app-backup.toml \
  --base-override ~/gitmove-external/my-app --apply
gitmove doctor
```

或直接从旧 clone 导入：

```bash
gitmove config import --from-repo /old/path/to/my-app --apply
```

### 场景 E：管理多个业务仓库

```bash
gitmove projects add . --alias frontend --group work
gitmove projects add "E:/项目/backend" --alias backend --group work
gitmove projects set-default frontend

gitmove -C backend doctor
gitmove projects doctor --all
gitmove projects sync pull --all --group work
```

### 场景 F：从上游 Git 仓挂 `.cursor`（Vendor）

**未被业务仓追踪**：

```bash
gitmove vendor add .cursor \
  --from https://github.com/MyLoveou/cursor-project-spec \
  --name cursor-spec
gitmove vendor sync cursor-spec
gitmove doctor
```

**已被业务仓追踪**（必须用原路径 `.cursor`）：

```bash
gitmove vendor add .cursor \
  --from https://github.com/MyLoveou/cursor-project-spec \
  --name cursor-spec \
  --migrate
gitmove doctor
gitmove vendor sync cursor-spec
```

团队其他人 clone 后需各自执行 `vendor add` 或 `apply`（不会自动带上游内容到 Git 历史）。

### 场景 G：公司工具仓挂到 `tools/`

```bash
gitmove vendor add tools \
  --from git@github.com:org/platform-tools.git \
  --ref release \
  --name company-tools
gitmove vendor sync company-tools
```

---

## 8. 能力怎么选

| 你的需求 | 用 |
|----------|-----|
| 已追踪小文件本地改不提交 | **skip** |
| 整目录放盘外、内容自己管 | **link** |
| 同仓多目录/分支实验 | **worktree** |
| 目录内容来自另一个 Git 仓、可 pull | **vendor** |
| 多个业务仓批量巡检 | **projects** |
| 业务仓 `origin` 改了 skip 文件 | **sync pull** |
| 上游规范仓更新了 | **vendor sync** |
| 换机复制策略 | **config export/import** |

**不要**：

- 用 vendor 替代 submodule 并把 vendor 内容提交进业务仓
- 对 skip 文件直接裸 `git pull`（用 `gitmove sync pull`）
- 为绕过追踪改挂到 `.cursor-local` 等替代路径（产品不支持）

---

## 9. 环境变量

| 变量 | 作用 |
|------|------|
| `GITMOVE_REPO` | 默认操作目标（路径或 projects 别名） |
| `GITMOVE_HOME` | 覆盖 `~/.gitmove/`（项目注册表） |
| `GITMOVE_VENDOR_HOME` | 覆盖 `~/gitmove-vendor/`（Vendor 缓存根目录） |

---

## 10. 故障排查

### doctor 报错「skip-worktree 未生效」

```bash
gitmove apply
gitmove doctor
```

### link 断裂或目标不对

```bash
gitmove link list
gitmove apply
```

### vendor link 断裂 / cache 缺失

```bash
gitmove vendor list
gitmove apply          # 会尝试重建 link、补 clone
gitmove doctor
```

### vendor sync 失败

常见原因：

- cache 内有未提交修改 → 先处理 cache 内 Git 状态
- 上游非 fast-forward → 需在 cache 目录内手动处理，gitmove **不会**自动 merge

### 多项目路径失效（MISSING）

```bash
gitmove projects list    # 查看 MISSING
gitmove projects remove old-alias
gitmove projects add /新/路径 --alias old-alias
```

### 误把本地文件提交进 Git 历史

```bash
git rm --cached --sparse config.local.json
gitmove skip add config.local.json
gitmove apply
```

彻底清历史需团队协调，见仓库内 `scripts/purge-local-files-from-history.*`。

---

## 11. 配置文件示例

`.git/gitmove.toml`（勿提交）：

```toml
[skip-worktree]
paths = ["config.local.json", ".cursor/rules.md"]

[external]
base = "E:/gitmove-external/my-app"

[links]
"tools/personal" = { path = "E:/gitmove-external/my-app/tools/personal", type = "junction" }

[worktrees]
sandbox = { path = "E:/work/my-app-sandbox", branch = "experiment" }

[vendors.cursor-spec]
repo_path = ".cursor"
source_url = "https://github.com/MyLoveou/cursor-project-spec"
source_ref = "main"
cache_path = "E:/gitmove-vendor/cursor-spec"
link_type = "junction"
auto_skip_tracked = true
```

---

## 12. 相关文档

- [典型工作流（场景详解）](workflows.md)
- [架构概览](../design/overview.md)
- [竞品对比](../product/competitive-analysis.md)
- [版本路线图](../product/roadmap.md)

---

## 13. 获取帮助

```bash
gitmove --help
gitmove skip --help
gitmove vendor add --help
```

问题反馈：[GitHub Issues](https://github.com/MyLoveou/gitmove/issues)
