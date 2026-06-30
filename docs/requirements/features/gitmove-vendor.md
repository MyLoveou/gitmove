# gitmove 上游依赖（Vendor）

**状态**：已定稿  
**版本**：0.4.0  
**依赖**：`gitmove-core.md`（link、skip-worktree、doctor、apply）

## 背景

开发者常需从**其他 Git 仓库**取用内容，在本项目**指定目录**下本地使用，场景包括但不限于：

| 场景 | 典型 `repo_path` | 上游示例 |
|------|------------------|----------|
| AI / Cursor 规范 | `.cursor` | `cursor-project-spec` |
| 内部工具链 | `tools/`、`scripts/vendor/` | 公司 tools  monorepo |
| 设计 token / 组件快照 | `packages/ui-kit/` | 设计系统仓库 |
| 文档模板 | `docs/templates/` | 文档中心仓库 |
| 个人开发套件 | `dev/` | 个人 dotfiles 仓库 |

共性需求：

- 上游可 **git pull** 更新
- 挂载点由用户**指定**（含已被业务仓 Git 追踪的路径）
- **不**改团队 `.gitignore`
- 配置仅本地 `.git/gitmove.toml`

**不提供**「改挂到 `docs/spec` / `.cursor-local` 等替代路径」的规避方案；用户给定的 `repo_path` 即为唯一挂载点。

## 目标

引入 **Vendor（上游依赖）** 能力：

1. 将远程 Git 仓库 **整仓 clone** 到本机缓存目录（cache）
2. 用 **junction/symlink** 将业务仓库内 `repo_path` **整仓 link** 到 cache 根目录
3. `vendor sync` 在 cache 内 **fast-forward pull**；**有冲突则中止并提示**，不自动 merge
4. 若 `repo_path` 下存在**已追踪**文件，自动配合 **skip-worktree**（批量），避免 `git status` 污染与误提交
5. `doctor` / `apply` 与现有 link、skip 一致恢复

## 不交付

- git submodule / subtree 写入业务仓 `.git`
- 修改团队 `.gitignore`
- 稀疏子目录 link（`include_paths` 裁剪上游仅 v2 考虑；**v1 仅整仓 link**）
- 自动 merge 上游冲突
- 向供应商仓库 push
- 私有仓凭据托管（沿用系统 `git` 凭据）
- 强制改挂到未追踪替代路径

## 术语

| 术语 | 含义 |
|------|------|
| **Vendor** | 一条「上游仓库 → cache → repo_path link」记录 |
| **cache** | 本机克隆目录，如 `~/gitmove-vendor/<vendor-name>/` |
| **repo_path** | 业务仓库内挂载点（相对路径，必须在仓库内） |
| **整仓 link** | `repo_path` 指向 cache **根目录**（上游仓库工作区根） |

## 数据模型

### TOML 配置（`.git/gitmove.toml`）

```toml
[vendors.cursor-spec]
repo_path = ".cursor"
source_url = "https://github.com/MyLoveou/cursor-project-spec"
source_ref = "main"
cache_path = "~/gitmove-vendor/cursor-project-spec"
link_type = "junction"
auto_skip_tracked = true

[vendors.company-tools]
repo_path = "tools"
source_url = "git@github.com:org/tools.git"
source_ref = "release"
# cache_path 省略时默认 ~/gitmove-vendor/<vendor-name>
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `repo_path` | 是 | 业务仓内相对路径；**允许已被 Git 追踪** |
| `source_url` | 是 | 上游 clone URL |
| `source_ref` | 否 | branch/tag/commit；默认 `main` |
| `cache_path` | 否 | 默认 `~/gitmove-vendor/<vendor-name>` |
| `link_type` | 否 | `junction`（Windows）/ `symlink`（Unix）；走 `resolve_link_type` |
| `auto_skip_tracked` | 否 | 默认 `true`；对 `repo_path` 下已追踪文件批量 skip |

`vendor-name` 为 TOML 表名（如 `cursor-spec`），与 `repo_path` 可不一一对应（一个上游可多条 vendor 仅 v2；**v1 一 vendor 一上游一 repo_path**）。

### 架构

```
source_url (远程 Git)
      │  clone / pull (仅作用于 cache)
      ▼
~/gitmove-vendor/<name>/     ← cache（整仓工作副本）
      │  junction / symlink（整仓 link）
      ▼
<业务仓>/repo_path/          ← 开发者看到的内容
      │
      ├─ 若路径曾被追踪 → skip-worktree（批量，配置持久化）
      └─ 业务仓 .git/gitmove.toml 记录 vendor + skip_paths
```

## 行为规格

### `vendor add`

```bash
gitmove vendor add <repo_path> \
  --from <url> \
  [--name <vendor-name>] \
  [--ref main] \
  [--cache ~/gitmove-vendor/foo] \
  [--migrate]   # repo_path 已存在且为普通目录时，迁移内容到 cache
```

**步骤（必须按序，失败则回滚已写配置）**：

1. 校验 `repo_path` 在仓库内（`resolve_repo_path`）
2. 若 cache 不存在：`git clone --branch <ref> <url> <cache>`（shallow 可选 v2）
3. 若 `repo_path` 已存在：
   - 已是正确 link → 仅更新配置
   - 是普通目录 → 无 `--migrate` 则**报错退出**；有 `--migrate` 则移动内容到 cache 后删除原目录
4. 创建 **整仓 link**：`repo_path` → `cache` 根目录
5. 若 `auto_skip_tracked`（默认 true）：
   - `git ls-files <repo_path>` 得到已追踪列表
   - 对每个路径 `update-index --skip-worktree` 并写入 `skip_paths`
6. 写入 `[vendors.<name>]` 并 `save_config`

**追踪路径策略（硬约束）**：

- **不得**建议或自动改挂 `docs/spec`、`.cursor-local` 等替代路径
- 已追踪时通过 **skip-worktree + link** 共存，不用改 `.gitignore`
- `doctor` 对「应 skip 但未 skip」报 **error**

### `vendor sync`

```bash
gitmove vendor sync [<repo_path|vendor-name>]
gitmove vendor sync --all
```

在 **cache 目录**执行：

```bash
git fetch
git merge --ff-only <ref>   # 或 pull --ff-only
```

| 结果 | 行为 |
|------|------|
| FF 成功 | 打印旧→新 commit；`repo_path` 经 link 自动可见新内容 |
| 非 FF / 冲突 / 本地 cache 有未提交改动 | **立即中止**；stderr 说明原因；**不** merge、**不**改 link |
| 网络失败 | 中止；cache 保持原状 |

同步**不**修改业务仓 Git 索引（仅 cache 内 Git 操作）。

### `vendor remove`

```bash
gitmove vendor remove <repo_path|vendor-name> [--purge-cache] [--keep-skip]
```

- 移除 link（保留外部 cache 默认）
- 从配置删除 vendor 记录
- 默认**不**自动 `skip remove`（避免恢复大段 status）；`--keep-skip false` 时可批量取消 skip
- `--purge-cache` 删除 cache 目录

### `vendor list` / `vendor status`

- **list**：vendor 名、repo_path、url、ref、link 是否正常
- **status**：cache 当前 commit、上游落后 commit 数（`git fetch` + rev-list）、工作区是否干净

### 与现有命令集成

| 命令 | 集成 |
|------|------|
| `gitmove apply` | 重建 vendor link；重新 apply skip；cache 不存在时 clone |
| `gitmove doctor` | vendor link 有效；cache 存在；tracked+vendor 的 skip 生效；可选 warn 上游落后 |
| `gitmove link add` | 与 vendor **互斥**同一 `repo_path`；vendor 优先 |

## CLI 契约汇总

| 命令 | 说明 |
|------|------|
| `vendor add <repo_path> --from URL` | 添加 vendor（整仓 link） |
| `vendor sync [name\|path]` | FF 同步 cache |
| `vendor sync --all` | 全部 vendor；任一失败则 exit 1，已成功的保留 |
| `vendor list` | 列表 |
| `vendor status [name\|path]` | 上游版本与 link 状态 |
| `vendor remove <name\|path>` | 移除 |

全局 `-C` / `projects` 注册表（若已实现）适用于 vendor 子命令。

## 已追踪 `repo_path` 说明（重要）

当 `.cursor` 等路径**已被业务仓追踪**时：

1. **仍挂载在该路径**（用户硬性要求）
2. link 后索引中仍为原 blob/树条目，工作区由上游 cache 提供内容
3. **必须**对原追踪路径启用 skip-worktree，否则 `git status` 大量脏文件
4. `doctor` 检查项：
   - `[error]` link 断裂或目标非 cache
   - `[error]` 已配置 vendor 且文件在 `ls-files` 但 skip 未生效
   - `[warn]` 上游落后 N 个 commit
5. 团队其他成员 clone 后：各自 `gitmove vendor add`（或 `apply` 从配置恢复 link + skip），**不**依赖提交 vendor 内容

**风险告知（文档/README，非阻断）**：追踪目录做 vendor 后，团队若也改同路径需协调；gitmove 不负责团队合并策略。

## 验收标准

- [x] `vendor add` 整仓 clone + link + 追踪路径批量 skip
- [x] **拒绝**自动改挂替代路径；`repo_path` 严格按用户指定
- [x] `vendor sync` 仅 FF；冲突/非 FF **中止并提示**，无自动 merge
- [x] `vendor sync --all` 部分失败时报告汇总
- [x] `apply` / `doctor` 覆盖 vendor
- [x] `repo_path` 已存在普通目录时无 `--migrate` 报错
- [x] Windows `CREATE_NO_WINDOW` 子进程（与 gitmove 0.2.x 一致）
- [x] 单元 + 集成测试；`vendor.py` 覆盖率纳入门禁 ≥ 80%
- [x] README「上游依赖 Vendor」章节含多场景示例

## 验证

```bash
pip install -e ".[dev]"
pytest tests/test_vendor.py -v --cov=gitmove

# 场景 A：未追踪路径
gitmove vendor add tools --from https://github.com/org/tools.git
gitmove vendor sync tools

# 场景 B：已追踪 .cursor（业务仓内已有提交）
gitmove vendor add .cursor --from https://github.com/MyLoveou/cursor-project-spec --migrate
gitmove doctor
gitmove vendor sync .cursor   # 上游冲突时应失败并提示
```

## 版本与依赖

| 版本 | 内容 |
|------|------|
| **0.4.0** | Vendor 全量（本文） |
| 0.3.x | 多项目管理（独立，可并行开发） |
| 0.5.0（占位） | vendor 模板、`include_paths` 子目录 link、shallow clone |

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-29 | 定稿：通用多场景；允许已追踪 repo_path；禁止替代路径；整仓 link；sync 冲突中止 |
