# gitmove

在不修改 `.gitignore` 的前提下，管理**仅本地生效**的 Git 排除策略：

- **skip-worktree** — 已追踪文件的本地修改不出现在 `git status`，也不会被提交
- **外部目录链接** — 用 Junction/Symlink 把仓库内路径指向仓库外 personal 目录
- **个人 worktree** — 独立工作区做实验，与主目录隔离

配置保存在 **`.git/gitmove.toml`**，不会进入版本库。

支持 **Windows / macOS / Linux**，提供 **CLI + 可视化 GUI**。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档索引与需求状态 |
| [docs/design/overview.md](docs/design/overview.md) | 架构与能力关系 |
| [docs/product/roadmap.md](docs/product/roadmap.md) | 版本路线图（0.3 多项目 · 0.4 Vendor） |
| [docs/guides/workflows.md](docs/guides/workflows.md) | 典型工作流与场景选型 |

## 安装

```bash
cd /path/to/gitmove
pip install -e .
```

## 可视化界面（推荐）

```bash
# 方式一：独立命令
gitmove-gui

# 方式二：CLI 子命令
gitmove gui

# 指定仓库路径
gitmove gui --repo /path/to/your/repo
```

GUI 功能：

- 左侧项目列表：注册、切换、批量 doctor/apply
- 选择 / 切换 Git 仓库
- 概览页：健康检查、外部目录配置
- Skip-worktree / 外部链接 / Worktree 分页管理
- 一键初始化、一键应用配置

界面跟随系统浅色/深色主题（`System` 模式）。

## CLI 快速开始

在任意 Git 仓库内：

```bash
gitmove init
gitmove skip add src/config.local.json
gitmove link add tools/personal
gitmove apply
gitmove doctor
```

## 多项目管理（v0.3）

在用户目录维护项目注册表 `~/.gitmove/projects.toml`（可用环境变量 `GITMOVE_HOME` 覆盖目录）。各仓库策略仍在 `.git/gitmove.toml`，注册表只保存路径指针。

```bash
# 注册常用仓库
gitmove projects add . --alias my-app --group work
gitmove projects add "E:/项目/other" --alias other --group work
gitmove projects list
gitmove projects set-default my-app

# 用别名操作任意已注册仓库（无需 cd）
gitmove -C other doctor
gitmove -C my-app sync pull

# 批量巡检 / 应用 / 同步
gitmove projects doctor --all
gitmove projects apply --all --group work
gitmove projects sync check --all
gitmove projects sync pull --all    # 先问项目，再问每个 skip 文件
```

环境变量 `GITMOVE_REPO` 与 `-C` 类似，可作为默认仓库路径或别名（`-C` 优先级更高）。

## 上游依赖 Vendor（v0.4）

从其他 Git 仓库整仓取用到业务仓指定路径（如已追踪的 `.cursor`），配置仍在 `.git/gitmove.toml`。缓存目录默认 `~/gitmove-vendor/<name>/`，测试可用 `GITMOVE_VENDOR_HOME` 覆盖。

```bash
# 未追踪目录
gitmove vendor add tools --from https://github.com/org/tools.git --name company-tools
gitmove vendor sync company-tools

# 已追踪 .cursor（需迁移本地目录）
gitmove vendor add .cursor \
  --from https://github.com/MyLoveou/cursor-project-spec \
  --name cursor-spec --migrate
gitmove vendor list
gitmove vendor status cursor-spec
gitmove vendor sync --all
gitmove doctor
```

`vendor sync` 仅在 cache 内 fast-forward pull；cache 脏或非 FF 时中止。与 `gitmove sync pull`（业务仓远程）独立。

## 多平台说明

| 平台 | 默认链接类型 | 说明 |
|------|-------------|------|
| Windows | `junction` | 目录联结，一般无需管理员权限 |
| macOS / Linux | `symlink` | 符号链接，自动 fallback |

手动指定链接类型：

```bash
gitmove link add tools/personal --type symlink
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `gitmove gui` | 打开可视化界面 |
| `gitmove-gui` | 同上（独立入口） |
| `gitmove init` | 初始化配置 |
| `gitmove apply` | 应用 skip / link / worktree |
| `gitmove doctor` | 诊断配置与实际状态 |
| `gitmove skip add/remove/list` | skip-worktree 管理 |
| `gitmove link add/list/remove/set-base` | 外部链接管理 |
| `gitmove config export/import` | 导出 / 导入配置（含 `--from-repo`） |
| `gitmove sync check` | 检查 skip 路径的本地 / 远程变更 |
| `gitmove sync pull` | 交互式 pull 并 reconcile skip 文件 |
| `gitmove projects list/add/remove/set-default` | 多项目注册表 |
| `gitmove projects doctor/apply [--all]` | 单仓或批量健康检查 / 应用 |
| `gitmove projects sync check/pull [--all]` | 单仓或批量 sync |
| `gitmove -C <path\|alias>` | 全局指定操作目标仓库 |
| `gitmove vendor add/list/status/sync/remove` | 上游 Git 整仓 link |

## 配置示例

`.git/gitmove.toml`（自动生成，勿提交）：

```toml
[skip-worktree]
paths = [
  "appsettings.local.json",
]

[external]
base = "/home/user/personal/myrepo"

[links]
"tools/personal" = { path = "/home/user/personal/myrepo/tools/personal", type = "symlink" }

[worktrees]
"sandbox" = { path = "/home/user/myrepo-sandbox", branch = "personal/sandbox" }
```

## 打包发布（Windows / macOS / Linux）

### 本地打包

```bash
# 安装打包依赖
pip install -e ".[build]"

# 生成 CLI + GUI 可执行文件（单文件）
python scripts/build.py --target all --onefile
```

产物：

| 路径 | 说明 |
|------|------|
| `dist/gitmove` 或 `dist/gitmove.exe` | CLI |
| `dist/gitmove-gui` 或 `dist/gitmove-gui.exe` | GUI（无控制台窗口） |
| `artifacts/gitmove-<version>-<platform>-<arch>.zip/.tar.gz` | 发布压缩包 |

快捷脚本：

```powershell
# Windows
powershell -File scripts/build.ps1
```

```bash
# macOS / Linux
chmod +x scripts/build.sh
./scripts/build.sh
```

Linux GUI 打包前需安装 Tk：

```bash
sudo apt-get install python3-tk   # Debian/Ubuntu
```

macOS 需已安装 Python 3.10+（系统或 Homebrew），自带 tkinter。

### CI 多平台自动打包

推送版本 tag 触发 GitHub Actions（`.github/workflows/release.yml`）：

```bash
git tag v0.2.0
git push origin v0.2.0
```

将在 **windows-latest / macos-latest / ubuntu-latest** 三端并行构建，并上传 Release 附件。

也可在 GitHub Actions 页面手动 **Run workflow**（workflow_dispatch）。

### 使用打包产物

```bash
# CLI
./gitmove init
./gitmove skip add config.local.json
./gitmove doctor

# GUI — 双击 gitmove-gui，或：
./gitmove-gui
```

**注意**：打包版仍依赖系统已安装 `git` 命令且在 PATH 中。

## 开发与测试

```bash
pip install -e ".[dev]"
pytest --cov=gitmove --cov-report=term-missing
```

Linux headless 环境（CI）使用 `xvfb-run -a pytest ...` 运行 GUI 集成测试。

CI 工作流：`.github/workflows/test.yml`（Windows / macOS / Linux 三端）

## 清理误提交本地文件

若曾将 `config.local.json` 等本地文件提交进 Git：

```bash
# 1. 停止追踪（保留工作区文件）
git rm --cached --sparse config.local.json

# 2. 如需从历史中彻底删除（会改写历史，需团队协调）
pip install git-filter-repo
powershell -File scripts/purge-local-files-from-history.ps1   # Windows
# 或 ./scripts/purge-local-files-from-history.sh            # macOS/Linux
```

## 设计说明

- 不修改 `.gitignore`，团队无感知
- 配置在 `.git/` 内，clone 后不自带，需 `gitmove apply` 或 GUI「一键应用」恢复
- skip-worktree 是本地索引标记，换机器需重新 apply
- GUI 基于 CustomTkinter，跨平台原生窗口

## License

MIT
