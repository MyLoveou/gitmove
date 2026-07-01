# gitmove · 已追踪 `.cursor` + 个人 Vendor + Profile 切换

**状态**：已定稿  
**目标版本**：0.5.x（工作流与文档）/ 0.5.2（Profile 切换补强，若实现）  
**依赖**：`gitmove-vendor.md`（已定稿 · 已实现）、`gitmove-0.5-enhancements.md` F9 Profile（已实现）、Link/Exclude（master · 已实现）  
**定稿日期**：2026-07-01（用户确认方案 A + 方案 C）

## 文档说明

业务仓库 **已在 Git 中追踪 `.cursor/`**（公司团队规范），开发者另有 **个人远程仓库**（仓库根即 `.cursor` 内容，如 `cursor-project-spec`）。本文档沉淀 **方案 A（Vendor + migrate + skip）** 与 **方案 C（Profile 公司/个人切换）** 的组合需求、验收标准与 TDD 测试计划。

**硬约束（继承 vendor 需求）**：

- 挂载点必须是 `.cursor`，不提供 `.cursor-local` 等替代路径
- 不改业务仓 `.gitignore`
- 配置仅存 `.git/gitmove.toml` 与 `.git/gitmove.profiles/`，不提交业务仓

---

## Scope Check

| 结论 | 说明 |
|------|------|
| **IN SCOPE** | 方案 A 操作规格；方案 C 双 Profile 定义与切换；doctor/apply 验收；集成测试计划；用户手册/workflow 更新 |
| **Phase 1** | 文档 + 基于现有 CLI 的可执行 playbook（无代码变更） |
| **Phase 2（可选）** | Profile 切换时 orphan vendor link 清理（见 §6.3） |
| **OUT OF SCOPE** | 新 mount 路径；submodule/subtree；自动 merge 上游冲突；把 Vendor 内容 push 进公司业务仓 |

---

## 背景与问题

| 侧 | 现状 |
|----|------|
| 业务仓 | 公司已在 Git 追踪 `.cursor/`（rules、skills 等） |
| 个人 Vendor 仓 | 远程仓库根目录即一套 `.cursor` 内容 |
| 冲突 | 同一 `repo_path` 不能改挂；需本地共存且可切换 |

**目标用户**：在同一公司项目 clone 上，有时遵循公司 `.cursor` 基线，有时切换为个人 Vendor 规范，且 `git status` 不被 `.cursor` 污染。

---

## 方案概述

### 方案 A · Vendor + `--migrate` + 自动 skip（Personal Profile 基线）

```bash
gitmove vendor add .cursor \
  --from <个人-cursor-仓库-url> \
  --ref main \
  --pin <tag-or-sha> \
  --migrate \
  --name personal-cursor
```

行为（现有实现）：

1. Clone 个人 Vendor → `~/gitmove-vendor/personal-cursor/`
2. `--migrate`：业务仓现有 `.cursor/` **合并**进 cache（`copytree` dirs_exist_ok）
3. 删除原目录，建立 **整仓 link**：`.cursor` → cache 根
4. `auto_skip_tracked=true`：对 `.cursor` 下已追踪文件批量 **skip-worktree**
5. `exclude_linked_paths`（默认 true）：同步 `.git/info/exclude` 托管段

### 方案 C · Profile 切换（Company ↔ Personal）

| Profile | 名称建议 | 配置要点 |
|---------|----------|----------|
| **公司模式** | `company` | 无 `[vendors.*]`；保留公司 `.cursor` 追踪文件的 skip（若需本地 diff）；或空 gitmove 策略 + 纯 Git 检出 |
| **个人模式** | `personal` | 含方案 A 的 `[vendors.personal-cursor]` + 对应 `skip_paths` |

```bash
gitmove profile save company    # 在公司模式下保存
gitmove profile save personal     # 在个人 Vendor 模式保存
gitmove profile use personal      # 切换并 apply
gitmove profile use company --dry-run  # 切换前预检
```

---

## 用户故事

### US-1 · 首次挂载个人 Vendor（方案 A）

- **作为** 开发者  
- **我希望** 在已有追踪 `.cursor` 的业务仓执行 `vendor add .cursor --migrate`  
- **以便** 磁盘上 `.cursor` 指向个人 Vendor cache，且已追踪文件被 skip，不污染 `git status`

**Given** 业务仓已 init，`git ls-files .cursor` 非空  
**When** 执行 `vendor add .cursor --from <url> --migrate --pin v1.0.0`  
**Then**

- `.cursor` 为 junction/symlink，目标为 cache 根
- `git ls-files .cursor` 路径仍在索引中
- 上述路径 `skip-worktree` 生效（`doctor` 无 skip error）
- `git status` 不列出 `.cursor` 下 modified（exclude + skip）
- `vendor sync personal-cursor` 仅更新 cache

### US-2 · 保存双 Profile（方案 C）

- **作为** 开发者  
- **我希望** 分别保存 `company` 与 `personal` 两套 gitmove 配置  
- **以便** 一条命令切换模式

**Given** 已在公司模式下 `profile save company`  
**When** 配置 personal vendor 后 `profile save personal`  
**Then**

- `.git/gitmove.profiles/company.toml` 与 `personal.toml` 均存在
- `profile list` 显示两者
- `profile use personal` 后 active 为 `personal`，且 `apply_all` 已执行

### US-3 · 切换回公司模式

- **作为** 开发者  
- **我希望** `profile use company` 恢复公司基线行为  
- **以便** 临时对齐团队 `.cursor` 策略

**Given** 当前为 `personal` profile，`.cursor` 为 vendor link  
**When** 执行 `profile use company`  
**Then**（Phase 1 最低验收）

- active profile 为 `company`
- `doctor` **无 error**（warn 可接受，须文档说明）
- 操作步骤文档化（见 §5.2）

**Then**（Phase 2 完整验收，若实现 §6.3）

- `.cursor` 不再指向个人 vendor cache（恢复为普通目录或公司策略 link）
- 公司追踪文件可编辑/可见策略与 profile 定义一致

### US-4 · 更新个人规范

- **作为** 开发者  
- **我希望** `vendor sync` + `source_pin` 固定可复现版本  
- **以便** 个人规范升级可控

**When** `vendor sync personal-cursor`  
**Then** cache FF 到 pin；`vendor status` 无 `pinned_drift`

### US-5 · 公司业务仓 pull 与 skip 协作

- **作为** 开发者  
- **我希望** 公司 remote 更新 `.cursor` 追踪文件时有明确流程  
- **以便** 不与 vendor 本地视图 silently 冲突

**When** 公司 `.cursor` 有 remote 变更  
**Then** 使用 `gitmove sync check` / `sync pull`，禁止裸 `git pull` 忽略 skip 文件（文档强制）

---

## 数据模型（Profile 快照）

### Personal Profile 示例（`.git/gitmove.profiles/personal.toml`）

```toml
[settings]
exclude_linked_paths = true

[vendors.personal-cursor]
repo_path = ".cursor"
source_url = "https://github.com/you/cursor-project-spec"
source_ref = "main"
source_pin = "v1.0.0"
link_type = "symlink"
auto_skip_tracked = true
shallow = true

[skip-worktree]
paths = [
  ".cursor/rules/company-rule.mdc",
  # vendor add 自动追加 .cursor 下已追踪路径
]
```

### Company Profile 示例（`.git/gitmove.profiles/company.toml`）

```toml
[settings]
exclude_linked_paths = true

# 无 vendors 段

[skip-worktree]
paths = [
  # 可选：仅 skip 需本地 diff 的少数公司文件；默认空
]
```

`.git/gitmove.active` 内容为当前 profile 名（如 `personal`）。

---

## 操作 Playbook（Phase 1 · 可立即执行）

### 5.1 首次 setup（Personal）

```bash
cd /path/to/company-repo
gitmove init

# 备份
cp -a .cursor ~/backup/company-cursor-$(date +%Y%m%d)

# 方案 A
gitmove vendor add .cursor \
  --from https://github.com/you/cursor-project-spec \
  --ref main \
  --pin v1.0.0 \
  --migrate \
  --name personal-cursor

gitmove doctor
gitmove profile save personal
```

### 5.2 建立 Company Profile（切换前）

**Phase 1 手动流程**（Profile 切换不自动拆除 vendor link 时）：

```bash
# 若当前为 personal 且需纯公司视图：
gitmove vendor remove personal-cursor --keep-skip   # 或按团队策略保留 skip
git checkout -- .cursor                             # 从 Git 恢复公司 .cursor 树
gitmove doctor
gitmove profile save company
```

**Phase 2**（若实现 §6.3）：`profile use company` 一步完成上述等效操作。

### 5.3 日常切换

```bash
gitmove profile use personal
gitmove vendor sync personal-cursor

gitmove profile use company    # Phase 1 见 §5.2 前置条件
gitmove doctor
```

### 5.4 与 `projects` 分组

```bash
gitmove projects add . --alias authwebapp --group work
# 公司仓 batch doctor 不影响 personal profile 语义
gitmove projects doctor --all --group work
```

---

## 验收标准

### 6.1 方案 A（Vendor + migrate）

- [ ] **VA-1** `vendor add .cursor --migrate` 后 cache 含上游 clone + 原 `.cursor` 合并内容
- [ ] **VA-2** `.cursor` 为 link，`vendor list` 显示 `link_ok=true`
- [ ] **VA-3** `git ls-files .cursor` 非空时，对应路径均在 `skip_paths` 且 skip 生效
- [ ] **VA-4** `git status` 无 `.cursor` 下 bulk modified
- [ ] **VA-5** `vendor sync` 在 pin 下 FF/detach 成功；`pinned_drift` 可检测
- [ ] **VA-6** `doctor` 无 error；`migrate_skipped` 仅 warn（若目录 migrate 适用）

### 6.2 方案 C（Profile）

- [ ] **VC-1** `profile save` / `use` / `list` / `delete` 对 `company`/`personal` 命名正常
- [ ] **VC-2** `profile use personal` 后 config 含 `[vendors.personal-cursor]` 且 `apply_all` 恢复 link
- [ ] **VC-3** `profile use personal --dry-run` 在 config 无效时 fail 且不写盘
- [ ] **VC-4** `active_profile_name` 与 `.git/gitmove.active` 一致
- [ ] **VC-5** Phase 1：文档 §5.2 手动切换步骤可复现且 `doctor` 无 error
- [ ] **VC-6** Phase 2（可选）：`profile use company` 自动清理 orphan vendor link（见 §6.3）

### Phase 2 补强（已实现）

**设计文档**：[profile-reconcile.md](../../design/profile-reconcile.md)

**实现**：`profile_reconcile.py` + `vendor.ensure_vendor_mount`；`profile use` 自动 teardown/mount（D1–D3 已落地）

**验收**：

- [x] **VP-1** personal → company 后 `.cursor` 非 personal cache link
- [x] **VP-2** company → personal 后 `.cursor` 恢复 vendor link
- [x] **VP-3** 往返切换 `doctor` 无 error

---

## TDD 测试计划（`tests/test_cursor_vendor_profile.py`）

> 实现 Phase 2 或文档化 Phase 1 回归时执行；遵循 RED → GREEN → refactor。

| ID | 测试用例 | 类型 | 对应验收 |
|----|----------|------|----------|
| T-1 | `test_vendor_add_cursor_migrate_with_tracked_files` | 集成 | VA-1–VA-4 |
| T-2 | `test_vendor_add_cursor_sets_skip_for_tracked` | 集成 | VA-3 |
| T-3 | `test_profile_save_personal_and_company` | 单元 | VC-1 |
| T-4 | `test_profile_use_personal_applies_vendor_link` | 集成 | VC-2 |
| T-5 | `test_profile_use_company_after_personal_manual_teardown` | 集成 | VC-5（Phase 1 文档流程 mock） |
| T-6 | `test_profile_use_company_removes_orphan_vendor_link` | 集成 | VP-1（Phase 2，先 RED） |
| T-7 | `test_profile_roundtrip_personal_company_doctor_ok` | 集成 | VP-3 |
| T-8 | `test_personal_profile_vendor_sync_respects_pin` | 集成 | VA-5 |

**RED 门禁**：T-6 在 Phase 2 实现前必须 fail；T-1–T-5 可对现有实现先 GREEN。

**运行**：

```bash
python -m pytest tests/test_cursor_vendor_profile.py -q
```

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| migrate 同名文件覆盖 | 操作前备份 `.cursor`（§5.1） |
| personal→company 残留 link | Phase 1 手动 §5.2；Phase 2 自动清理 |
| 公司 remote 更新 `.cursor` | 强制 `sync pull` 流程（US-5） |
| pin + shallow 找不到 SHA | `vendor add --no-shallow` 或 tag pin |
| 误提交 Vendor 内容 | skip + exclude；不 commit gitmove.toml |

---

## 文档同步清单

- [ ] `docs/guides/workflows.md` — 新增 §「已追踪 .cursor + Profile」
- [ ] `docs/guides/user-manual.md` — Vendor 场景 B 扩展 + Profile 切换章节
- [ ] `docs/README.md` — 需求索引新增本文件

---

## 开放问题（已关闭）

| ID | 问题 | 决议 |
|----|------|------|
| Q1 | 选哪种方案？ | **A + C**（用户 2026-07-01 确认） |
| Q2 | 是否改 mount 路径？ | **否**（产品硬约束） |
| Q3 | Profile 切换是否自动拆 vendor link？ | Phase 1 **手动**；Phase 2 **实现 VP-*** |

---

## 下一步

| 阶段 | 动作 |
|------|------|
| **现在** | 按 §5 Playbook 在业务仓落地；更新 workflows / user-manual |
| **plan-workflow** | Phase 2 若做 VP-*：拆 `implement-feature` 任务 |
| **TDD** | 新增 `tests/test_cursor_vendor_profile.py`，先写 T-6 RED |
| **verification-gate** | 全量 pytest + 业务仓 `doctor` + `git status` 手工 DoD |

---

## 相关文档

- [gitmove-vendor.md](gitmove-vendor.md)
- [gitmove-0.5-enhancements.md](gitmove-0.5-enhancements.md) · F9 Profile
- [workflows.md](../../guides/workflows.md)
- [user-manual.md](../../guides/user-manual.md)
