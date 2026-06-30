# gitmove 产品路线图

## 版本总览

| 版本 | 主题 | 状态 | 需求文档 |
|------|------|------|----------|
| **0.2.0** | 核心 + GUI + 打包 | 已发布 | [gitmove-core](../requirements/features/gitmove-core.md) |
| **0.2.x** | 配置迁移 + 远程 sync | 已实现 | [gitmove-config-sync](../requirements/features/gitmove-config-sync.md) |
| **0.3.0** | 多项目 CLI | 已实现 | [gitmove-multi-project](../requirements/features/gitmove-multi-project.md) |
| **0.3.1** | 多项目 GUI 侧栏 | 已实现 | 同上 |
| **0.4.0** | 上游 Vendor | 已实现 | [gitmove-vendor](../requirements/features/gitmove-vendor.md) |
| **0.5.0** | 占位 | 未规划 | vendor 模板、子目录 link、shallow clone |

## 0.2.0 — 核心能力（已完成）

- skip-worktree / link / worktree
- `init` · `apply` · `doctor`
- CustomTkinter GUI
- PyInstaller 三平台 CI
- 路径穿越防护、测试覆盖率 ≥ 80%

## 0.2.x — 配置与同步（已完成）

- `gitmove config export` / `import`（含 `--from-repo`）
- `gitmove sync check` / `sync pull`（skip 文件交互式 reconcile）
- Windows 子进程无 CMD 闪烁
- 刷新性能优化（合并 `ls-files`、doctor 复用数据）

## 0.3.0 — 多项目管理 · CLI

**目标**：同时管理多个业务仓库。

交付：

- `~/.gitmove/projects.toml` 注册表
- `gitmove projects list|add|remove|set-default`
- 全局 `-C` / `GITMOVE_REPO`
- `projects doctor|apply|sync --all`
- 批量 sync：**项目级** + **文件级** 两级交互

不交付：云端同步注册表、自动扫描全盘 Git 仓。

## 0.3.1 — 多项目管理 · GUI

- 左侧项目列表与切换
- 「全部 doctor」「全部 apply」（后台队列）
- 批量 sync 向导（可选，可延后）

## 0.4.0 — 上游 Vendor

**目标**：从任意上游 Git 仓整仓取用内容到指定 `repo_path`。

交付：

- `vendor add|sync|list|status|remove`
- 整仓 link 到 `~/gitmove-vendor/<name>/`
- **已追踪 `repo_path`**：批量 skip-worktree（禁止改挂替代路径）
- `vendor sync` 仅 FF，冲突**中止不 merge**
- `apply` / `doctor` 集成

典型场景：AI 规范 `.cursor`、公司 tools 仓、文档模板等（见 vendor 需求文档场景表）。

## 0.5.0 — 占位

- Vendor 配置模板（如 `cursor-spec` 一键套用）
- `include_paths` 子目录 link（非整仓）
- `projects repair` 路径修复
- import 后自动 `projects add`

## 实现顺序建议

```
0.2.x（已完成）→ 0.3.0 CLI → 0.3.1 GUI → 0.4.0 Vendor
```

0.3 与 0.4 **设计可并行**，实现建议先完成 0.3.0（多项目编排层），再 0.4.0（vendor 复用 link + skip）。

## 不变约束（全版本）

- 不修改业务仓 `.gitignore`
- 仓库策略写在 `.git/gitmove.toml`
- 不替代 Git / 不强制团队同步本地配置

## 竞品与定位

与 repoverlay、shimmer、gitnook、dew、worktree 工具群等的对比与场景选型，见 [competitive-analysis.md](competitive-analysis.md)。
