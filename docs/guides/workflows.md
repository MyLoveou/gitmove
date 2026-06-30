# 典型工作流

本文档说明常见场景下如何组合 gitmove 能力。命令中带 **（规划）** 的尚未实现。

---

## 1. 新 clone 后恢复本地策略

```bash
cd my-app
gitmove init                    # 若无 .git/gitmove.toml
gitmove apply
gitmove doctor
```

若曾在其他机器 export 过配置：

```bash
gitmove config import ~/backup/my-app.gitmove.toml --apply
```

---

## 2. 本地配置文件（已追踪）

```bash
gitmove skip add appsettings.Development.json
gitmove doctor
```

远程也改了同一文件时：

```bash
gitmove sync check
gitmove sync pull               # 按提示 l/r/m/s 选择
```

---

## 3. 个人目录放到盘外（未追踪或整目录）

```bash
gitmove link set-base ~/gitmove-external/my-app
gitmove link add tools/personal
gitmove apply
```

---

## 4. 换机：从旧项目复制配置

```bash
# 方式 A：TOML 文件
gitmove config export ./backup.toml          # 在旧机
gitmove config import ./backup.toml --apply  # 在新机

# 方式 B：旧 clone 仍在磁盘
gitmove config import --from-repo /old/path/to/my-app \
  --base-override ~/gitmove-external/my-app --merge
```

---

## 5. 多项目日常巡检（规划 0.3）

```bash
gitmove projects add . --alias my-app --group work
gitmove projects add ../other --alias other --group work

gitmove projects doctor --all
gitmove projects apply --all
gitmove projects sync check --all
gitmove projects sync pull --all    # 先问项目，再问每个 skip 文件
```

单仓指定别名：

```bash
gitmove -C other doctor
```

---

## 6. 从上游 Git 仓取用目录（规划 0.4 · Vendor）

### 场景 A：`.cursor` 未被业务仓追踪

```bash
gitmove vendor add .cursor \
  --from https://github.com/MyLoveou/cursor-project-spec \
  --ref main
gitmove vendor sync .cursor
gitmove doctor
```

### 场景 B：`.cursor` 已被业务仓追踪（必须用 `.cursor` 路径）

```bash
gitmove vendor add .cursor \
  --from https://github.com/MyLoveou/cursor-project-spec \
  --migrate
# 自动：整仓 link + 批量 skip-worktree
gitmove doctor
gitmove vendor sync .cursor    # 仅更新上游；冲突则中止
```

### 场景 C：公司工具仓挂到 `tools/`

```bash
gitmove vendor add tools \
  --from git@github.com:org/platform-tools.git \
  --ref release
```

### Vendor 与业务仓 pull 分工

| 操作 | 更新什么 |
|------|----------|
| `gitmove vendor sync` | 上游供应商 cache（如 cursor-project-spec） |
| `gitmove sync pull` | 业务仓 `origin` + skip 文件 reconcile |
| `git pull`（裸用） | 不推荐；skip 文件易冲突 |

---

## 7. 能力选型简表

| 需求 | 用 |
|------|-----|
| 已追踪小文件本地改不提交 | skip-worktree |
| 整目录放盘外、自己管内容 | link |
| 同仓另一分支/目录开发 | worktree |
| 目录内容来自**另一个 Git 仓**、可 pull 更新 | vendor（规划） |
| 配置换机迁移 | config import/export |
| 业务仓远程改了 skip 文件 | sync pull |
| 管多个业务仓 | projects（规划） |

---

## 8. 禁止 / 不推荐

- 为绕过追踪而把 vendor 改挂到 `docs/spec`、`.cursor-local`（产品**不提供**此能力）
- 用 vendor 替代 submodule 并提交 vendor 内容到业务仓
- 在 skip 文件上直接 `git pull` 而不走 `sync pull`

---

## 相关文档

- [架构概览](../design/overview.md)
- [路线图](../product/roadmap.md)
- [需求索引](../README.md)
