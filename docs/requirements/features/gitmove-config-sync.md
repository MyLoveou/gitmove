# gitmove 配置迁移与远程同步

**状态**：已定稿  
**版本**：0.2.x  
**依赖**：`gitmove-core.md`

## 目标

1. **配置 import/export** — 换机、备份、团队模板、跨项目复制
2. **sync check/pull** — 业务仓远程更新时，对 skip-worktree 文件做交互式 reconcile

## 不交付

- 跨机器自动同步配置云
- 自动 merge 业务仓与 skip 文件冲突（用户交互选择）
- 修改 `.gitignore`

## 配置导入导出

### 两种方式

| 方式 | 命令 | 适用 |
|------|------|------|
| 任意 TOML 文件 | `gitmove config import ./file.toml` | 备份、模板、手工编辑 |
| 另一仓库 clone | `gitmove config import --from-repo ../other` | 从已配置项目复制 |

格式与 `.git/gitmove.toml` 相同；**不**自动 `projects add`（多项目功能另见 multi-project 文档）。

### 选项

| 选项 | 默认 | 说明 |
|------|------|------|
| `--merge` | 是 | skip 并集；同名 link/wt 保留当前仓 |
| `--replace` | 否 | 整体替换 |
| `--base-override` | 无 | 设置 external base 并展开 `${EXTERNAL_BASE}` |
| `--apply` | 否 | 导入后执行 apply |

### 模板变量

```toml
[links]
"tools/personal" = { path = "${EXTERNAL_BASE}/tools/personal", type = "junction" }
```

### 验收（已实现）

- [x] `config export` / `import` / `import --from-repo`
- [x] merge / replace / base-override
- [x] 路径穿越拒绝
- [x] 单元测试 `tests/test_config_import.py`

## 远程 sync（业务仓）

针对 **skip-worktree 已生效**且**业务仓远程**有更新的路径。

### 命令

```bash
gitmove sync check [--fetch/--no-fetch]
gitmove sync pull [--fetch/--no-fetch]
```

### 检测逻辑

- `local_modified`：工作区文件 ≠ `HEAD`
- `remote_modified`：`HEAD` ≠ `@{upstream}` 对该路径内容
- `needs_attention`：`skip_active` 且 `remote_modified`

### 交互策略（单项目 `sync pull`）

对每个需关注路径：

| 键 | 策略 |
|----|------|
| l | 保留本地：unskip → stash → pull → pop → re-skip |
| r | 采用远程：unskip → 恢复 HEAD → pull → re-skip |
| m | 合并：同 local，stash pop 可能冲突则报错 |
| s | 跳过此文件：暂存本地 → pull → 写回本地 → re-skip |

仅远程改、本地未改：`r` / `s`。

### 约束

- `git pull --ff-only`；失败则中止
- 不修改 `.gitignore`
- 与 **vendor sync**（上游 cache）独立

### 验收（已实现）

- [x] `sync check` / `sync pull`
- [x] 交互式 chooser
- [x] skip 路径在 pull 时被保留（s 策略）
- [x] 测试 `tests/test_sync.py`、`tests/test_sync_unit.py`

## 与多项目 / Vendor 的关系

| 能力 | 文档 |
|------|------|
| `projects sync pull --all` | [gitmove-multi-project.md](gitmove-multi-project.md) |
| `vendor sync` | [gitmove-vendor.md](gitmove-vendor.md) |

## 验证

```bash
pytest tests/test_config_import.py tests/test_sync.py tests/test_sync_unit.py -v
```
