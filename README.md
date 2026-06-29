# gitmove

在不修改 `.gitignore` 的前提下，管理**仅本地生效**的 Git 排除策略：

- **skip-worktree** — 已追踪文件的本地修改不出现在 `git status`，也不会被提交
- **外部目录链接** — 用 Junction/Symlink 把仓库内路径指向仓库外 personal 目录
- **个人 worktree** — 独立工作区做实验，与主目录隔离

配置保存在 **`.git/gitmove.toml`**，不会进入版本库。

## 安装

```powershell
cd E:\项目\gitmove
pip install -e .
```

## 快速开始

在任意 Git 仓库内：

```powershell
# 1. 初始化（创建 .git/gitmove.toml）
gitmove init

# 2. 已追踪文件：本地改但不提交
gitmove skip add src/config.local.json

# 3. 个人目录：链到仓库外（Windows 默认 junction，无需管理员）
gitmove link add tools/personal

# 4. 新 clone 后一键恢复
gitmove apply

# 5. 检查状态
gitmove doctor
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `gitmove init` | 初始化配置 |
| `gitmove apply` | 应用 skip / link / worktree |
| `gitmove doctor` | 诊断配置与实际状态 |
| `gitmove skip add <path>` | 启用 skip-worktree |
| `gitmove skip remove <path>` | 取消 skip-worktree |
| `gitmove skip list` | 列出 skip 状态 |
| `gitmove link add <path>` | 创建外部目录链接 |
| `gitmove link add <path> --migrate` | 迁移已有目录到外部 |
| `gitmove link set-base <dir>` | 设置默认外部根目录 |
| `gitmove link list` | 列出链接 |
| `gitmove link remove <path>` | 移除链接（默认保留外部数据） |
| `gitmove worktree add <name> <path>` | 添加个人 worktree |
| `gitmove worktree list` | 列出 worktree |
| `gitmove worktree remove <name>` | 移除 worktree |

## 配置示例

`.git/gitmove.toml`（自动生成，勿提交）：

```toml
[skip-worktree]
paths = [
  "appsettings.local.json",
]

[external]
base = "E:/personal/myrepo"

[links]
"tools/personal" = { path = "E:/personal/myrepo/tools/personal", type = "junction" }

[worktrees]
"sandbox" = { path = "E:/personal/myrepo-sandbox", branch = "personal/sandbox" }
```

## 典型工作流

### 已追踪配置文件

```powershell
gitmove skip add appsettings.json
# 本地修改 appsettings.json，git status 不再显示
```

pull 前若远程也改了同一文件：

```powershell
gitmove skip remove appsettings.json
git stash push -m "local" -- appsettings.json
git pull
git stash pop
gitmove skip add appsettings.json
```

### 个人工具目录

```powershell
gitmove link set-base E:\personal\myrepo
gitmove link add tools/personal
# 实际文件在 E:\personal\myrepo\tools\personal
```

### 个人实验分支

```powershell
gitmove worktree add sandbox E:\personal\myrepo-sandbox --new-branch --branch personal/sandbox
```

## 设计说明

- 不修改 `.gitignore`，团队无感知
- 配置在 `.git/` 内，clone 后不自带，需 `gitmove apply` 恢复
- skip-worktree 是本地索引标记，换机器需重新 apply
- link 默认用 Windows Junction（目录），一般不需要开发者模式

## License

MIT
