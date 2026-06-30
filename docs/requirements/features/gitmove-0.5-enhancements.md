# gitmove 0.5+ 高契合增强能力包

**状态**：已定稿  
**目标版本**：0.5.0（核心） / 0.5.x–0.6（部分可拆分）  
**依赖**：`gitmove-core.md`、`gitmove-config-sync.md`、`gitmove-multi-project.md`、`gitmove-vendor.md`（均已定稿 · 已实现）  
**定稿日期**：2026-06-29（用户确认开放问题 Q1–Q12 全部采纳建议）

## 文档说明

本文档对 [竞品对比分析](../../product/competitive-analysis.md) 中标记为**高契合**、且与 gitmove 定位一致的能力进行需求沉淀。  
**已定稿**，可进入 `implement-feature`。

---

## Scope Check · 0.5 高契合能力包

| 结论 | 说明 |
|------|------|
| **IN SCOPE** | Epic A–D 共 13 项（F1–F12 + **F13 错误可视化与修复引导**） |
| **Phase** | roadmap 0.5.0 占位 + 0.5.x / 0.6 扩展 |
| **硬约束** | 不改业务仓 `.gitignore`；仓库策略仍在 `.git/gitmove.toml`；CLI/GUI 共用业务模块 |

| ID | 能力 | 建议版本 | 与 roadmap 关系 |
|----|------|----------|-----------------|
| F1 | Vendor 一键模板 | 0.5.0 | 已在占位 |
| F2 | Vendor 子目录 link（`include_paths`） | 0.5.0 | 已在占位 |
| F3 | Vendor shallow clone | 0.5.0 | 已在占位 |
| F4 | `projects repair` | 0.5.0 | 已在占位 |
| F5 | config import 后自动 `projects add` | 0.5.0 | 已在占位 |
| F6 | GUI 批量 sync 向导 | 0.5.0 | 补全 0.3.1 未交付项 |
| F7 | Vendor pin commit/tag/SHA | 0.5.x | 新增 |
| F8 | Git hooks 可选集成 | 0.5.x | 新增 |
| F9 | 策略 Profile 切换 | 0.5.x | 新增 |
| F10 | `projects scan` 目录扫描注册 | 0.5.x | **修订** 0.3「不扫描」边界 |
| F11 | `projects update` 批量 git pull | 0.5.x | 新增 |
| F12 | Vendor 上游变更通知 | 0.6 | 新增 |
| **F13** | **错误可视化与可行动修复引导** | **0.5.0（横切）** | **用户强制要求；覆盖全命令** |

**横切约束（F13）**：Epic A–C 及既有命令（skip/link/vendor/projects/sync 等）**凡用户可见报错**，均须符合 [Epic D · F13](#epic-d--错误可视化与可行动修复引导-f13) 规格；不得仅抛出原始 Git stderr 或 `messagebox.showerror("错误", str(exc))`。

**OUT OF SCOPE（本包）**：

- 云端同步注册表 / 配置
- AI worktree 工作站（Grove/Canopy 类）
- dew 式加密密钥托管全功能
- gitnook 式嵌套隐藏 Git
- submodule/subtree 写入业务仓
- repoverlay marketplace 插件生态

---

## Epic A · Vendor 增强（F1–F3、F7、F12）

### F1 · Vendor 一键模板

#### 背景

用户反复输入 `vendor add .cursor --from ... --ref main`；repoverlay/shimmer 提供 preset。gitmove 0.4 已支持手动 add，缺**内置配方**降低门槛。

#### 用户故事

- **US-F1-1**：作为开发者，我希望 `gitmove vendor add --template cursor-spec .cursor`，以便一条命令完成常见 AI 规范仓挂载。
- **US-F1-2**：作为团队维护者，我希望在用户目录维护自定义模板，以便公司内统一 vendor 源而不改业务仓。

#### 行为规格

```bash
gitmove vendor template list
gitmove vendor add <repo_path> --template <id> [--ref override] [--migrate]
```

**内置模板（v1 至少 1 个）**：

| template id | 默认 repo_path | source_url | source_ref |
|-------------|----------------|------------|------------|
| `cursor-spec` | `.cursor` | `https://github.com/MyLoveou/cursor-project-spec` | `main` |

**用户模板路径**：`~/.gitmove/templates.toml`（或 `GITMOVE_HOME/templates.toml`）

```toml
[[templates]]
id = "company-tools"
repo_path = "tools"
source_url = "git@github.com:org/tools.git"
source_ref = "release"
auto_skip_tracked = true
```

**解析优先级**：`--template` 展开后与普通 `vendor add` 相同；CLI 显式 `--from` / `--ref` **覆盖**模板字段。

#### 验收标准

- [ ] `vendor template list` 显示内置 + 用户模板
- [ ] `--template cursor-spec` 等价于手动指定 url/ref（集成测试）
- [ ] 用户模板 id 冲突内置时：**用户优先**或报错（须定稿时二选一）
- [ ] 无效 template id → exit 1 + 可用 id 列表
- [ ] README / user-manual 更新

#### 不交付

- 远程 marketplace URL 拉取模板
- 模板版本自动升级业务仓 vendor 配置

---

### F2 · Vendor 子目录 link（`include_paths`）

#### 背景

0.4 仅整仓 link；用户可能只需上游 `packages/ui/` 或 `templates/`。repoverlay/shimmer 支持局部 overlay。

#### 用户故事

- **US-F2-1**：作为开发者，我希望只 link 上游仓库的 `docs/templates/` 到业务仓 `docs/templates/`，避免整仓污染 mount 点。

#### 数据模型扩展

```toml
[vendors.ui-kit]
repo_path = "packages/ui-kit"
source_url = "https://github.com/org/design-system.git"
source_ref = "main"
include_paths = ["packages/ui-kit"]   # 新增；省略 = 整仓（与 0.4 兼容）
```

| 字段 | 说明 |
|------|------|
| `include_paths` | 非空时：cache 仍**整仓 clone**；link 目标为 cache 内对应子目录（非 cache 根） |
| 互斥 | 同一 `repo_path` 仍只允许一条 vendor 或 link |

#### 行为规格

1. `vendor add`：`include_paths` 校验路径存在于 cache clone 后工作区（不存在 → 报错）
2. `repo_path` link 指向 `cache / include_paths[0]`（v1 **仅支持单元素**；多元素 → 后续版本）
3. `doctor`：link 目标必须是 cache 内预期子目录
4. `vendor sync`：仍 FF-only 整 cache；link 自动反映子目录更新
5. **已追踪路径**：`auto_skip_tracked` 仍对 `repo_path` 下 `git ls-files` 生效

#### 验收标准

- [ ] 无 `include_paths` 时行为与 0.4 完全一致（回归）
- [ ] 单元素 `include_paths` add/sync/doctor/apply 通过
- [ ] cache 子目录不存在时 add 失败且配置回滚
- [ ] 与整仓 vendor 并存于不同 repo_path 的集成测试

#### 不交付（F2 v1）

- 多 `include_paths` 合并到一个 repo_path
- sparse checkout（仅 clone 子目录）

---

### F3 · Vendor shallow clone

#### 背景

大上游仓首次 clone 慢、占磁盘；Git 原生 `--depth 1` 常见。

#### 用户故事

- **US-F3-1**：作为用户，我希望 vendor 默认 shallow clone，以便快速首次 add。

#### 行为规格

| 项 | 规格 |
|----|------|
| 默认 | `vendor add` 使用 `git clone --depth 1 --branch <ref> <url>` |
| 配置 | `shallow = true`（默认 true）；`shallow = false` 全量 clone |
| sync | FF-only pull；若 shallow 导致无法 FF → **中止**并提示 `git fetch --unshallow` 或设置 `shallow=false` 重建 |
| 已有 cache | 不自动 unshallow；doctor 可选 `[warn] shallow cache` |
| migrate | 与 shallow 无关 |

#### 验收标准

- [ ] 新 vendor 默认 depth=1（mock git 参数断言）
- [ ] `shallow=false` 全量 clone 仍可用
- [ ] sync 非 FF 时错误信息含 shallow 提示（若相关）
- [ ] TOML 往返 `shallow` 字段

---

### F7 · Vendor pin（commit / tag / SHA）

#### 背景

submodule/shimmer 可固定版本；0.4 仅 `source_ref` branch/tag 名，sync 跟踪浮动 ref。

#### 用户故事

- **US-F7-1**：作为用户，我希望 pin 到 tag `v1.2.0` 或 commit SHA，以便可复现的上游快照。
- **US-F7-2**：作为用户，我希望 `vendor status` 显示「当前 commit vs pin 目标」差异。

#### 数据模型

```toml
[vendors.cursor-spec]
source_ref = "main"           # 仍用于 clone 默认分支（首次）
source_pin = "v1.2.0"         # 可选：tag 或 40 位 SHA；设置后 sync 检出/FF 到该 pin
# 或 source_pin = "abc1234..."
```

**语义（建议）**：

- 无 `source_pin`：与 0.4 相同，sync FF 到 `origin/<source_ref>`
- 有 `source_pin`：
  - 若为 SHA：sync 时 fetch 后 `git merge --ff-only <sha>` 或 `git checkout <sha>` detached（**须定稿**）
  - 若为 tag：fetch tag 后 FF 到 tag commit
  - `vendor status` 显示 `pinned` / `drift`（pin 与 HEAD 不一致）

#### 验收标准

- [ ] add 时可 `--pin v1.0.0`
- [ ] status 显示 pin 与当前 HEAD
- [ ] sync 在非 FF 到 pin 时中止（与 0.4 一致）
- [ ] doctor：pin 的 tag/SHA 在 remote 不存在 → error

#### 开放问题

- Q-F7-1：pin SHA 时 sync 是否允许 detached HEAD cache？（建议：允许，文档说明）

---

### F12 · Vendor 上游变更通知

#### 背景

shimmer 团队通过 PR 感知 overlay 更新；用户希望批量感知「哪些 vendor 落后」。

#### 用户故事

- **US-F12-1**：作为用户，我希望 `vendor status --all` 汇总落后项，exit code 2 表示有更新可 sync。
- **US-F12-2**：作为用户，我希望 `projects doctor --all` 对 vendor 落后仅 warn（已有部分）并可选升级。

#### 行为规格

```bash
gitmove vendor status --all [--fetch]
# 表格：name, repo_path, behind, dirty, pinned_drift

gitmove vendor check-updates [--all]   # 可选别名；仅检查不 sync
```

- `--fetch`：默认 true（与 sync check 一致）
- exit code：0=全部最新且干净；1=错误；2=有 behind 或 pinned_drift（**须定稿**）

#### 验收标准

- [ ] `--all` 表格与单 vendor status 一致
- [ ] 脚本友好 exit code  documented
- [ ] 不修改 cache（只 fetch + rev-list）

#### 不交付

- 桌面通知 / email
- 自动 `vendor sync --all`

---

## Epic B · 多项目增强（F4–F6、F10、F11）

### F4 · `projects repair`

#### 背景

0.3 文档：仓库搬家后 path MISSING，只能 remove + add。myrepos 类工具有 repair 概念。

#### 用户故事

- **US-F4-1**：作为用户，我把项目从 `E:/old/app` 移到 `E:/new/app`，希望 `projects repair` 批量修复注册表路径。
- **US-F4-2**：作为用户，我希望交互式逐条确认 old→new 映射。

#### 行为规格

```bash
gitmove projects repair [--auto] [--dry-run]
```

| 模式 | 行为 |
|------|------|
| 交互（默认） | 对每个 MISSING：提示输入新 path 或 skip |
| `--auto` | 在同父目录下按目录名 fuzzy 匹配（**可选**，风险高） |
| `--dry-run` | 只打印建议，不写注册表 |

**repair 启发式（`--auto` 限定）**：

- 仅处理 `status=MISSING`
- 在旧 path 的**父目录的兄弟目录**中查找同名文件夹且为 Git 根
- 多匹配 → 跳过并报告

#### 验收标准

- [ ] 交互 repair 单条更新 path 后 list 为 OK
- [ ] `--dry-run` 不写文件
- [ ] `--auto` 有单元测试（多匹配不瞎改）
- [ ] alias / group / notes 保留

#### 不交付

- 自动搜索全盘（见 F10）
- 修改 `.git/gitmove.toml` 内路径

---

### F5 · config import 后自动 `projects add`

#### 背景

0.3 明确 import 不自动注册；换机流程多一步。高契合增强：可选联动。

#### 用户故事

- **US-F5-1**：作为用户，`config import --apply` 后希望当前仓库自动进入注册表，alias 默认目录名。

#### 行为规格

```bash
gitmove config import ./backup.toml --apply --register [--alias A] [--group G]
```

| 项 | 规格 |
|----|------|
| 触发 | 仅显式 `--register`；**非默认**（保持 0.3 兼容） |
| 冲突 | alias 已存在 → 报错或 `--merge-registry` 更新 path（须定稿） |
| 路径 | 注册**当前 `-C` 目标仓库**根，非 TOML 内路径 |

#### 验收标准

- [ ] 无 `--register` 行为与 0.3 完全一致
- [ ] `--register` 写入 projects.toml 且 list 可见
- [ ] 非 Git 目录 import 失败（已有）

---

### F6 · GUI 批量 sync 向导

#### 背景

0.3.1 交付了 batch doctor/apply，**未交付** batch sync pull GUI；CLI 已有两级交互。

#### 用户故事

- **US-F6-1**：作为 GUI 用户，我希望「全部 sync」走向导：先项目级 y/n，再 per-file l/r/m/s，与 CLI 行为一致。

#### GUI 规格

1. 侧栏或工具栏新增「全部 sync check」「全部 sync pull」
2. **sync check**：后台跑 `projects sync check --all`，结果对话框表格（项目、attention 数）
3. **sync pull**：
   - 模态向导逐步推进（不可一次弹所有文件）
   - 项目级：Continue / Skip project（等同 CLI y/n）
   - 文件级：四个按钮 l/r/m/s + 显示路径与 local/remote 摘要
   - 取消：中止后续项目，已完成项目保留结果
4. 长操作后台线程；完成摘要写底栏

#### 验收标准

- [ ] headless 可测：核心逻辑委托 `projects.sync_pull_batch`（不测 Tk 细节）
- [ ] 与 CLI 同一 chooser 回调（不重复 reconcile 逻辑）
- [ ] 空注册表 / 全 MISSING 友好空态

#### 不交付

- 非交互「一键全部 remote」
- diff 可视化（归中契合 F19，另文档）

---

### F10 · `projects scan`（修订 0.3 边界）

#### 背景

0.3 **不交付**全盘扫描；竞品 mr / Worktree Manager 有 workspace 发现。0.5 **可选 opt-in** 减轻手动 add 负担。

#### 用户故事

- **US-F10-1**：作为用户，我希望 `projects scan ~/work --group work --max-depth 3` 列出未发现 Git 根并询问是否注册。

#### 行为规格

```bash
gitmove projects scan <root> [--group G] [--max-depth N] [--dry-run] [--yes]
```

| 项 | 规格 |
|----|------|
| 扫描 | BFS/DFS 找含 `.git` 的目录（非 submodule 内 .git 文件需处理：仅接受 `git rev-parse` 成功的根） |
| 默认 max-depth | 4 |
| 已注册 path | 跳过 |
| 交互 | 每个候选 `[y/n/a=all/none]`；`--yes` 全部注册；`--dry-run` 只列 |
| alias 默认 | 目录 basename；冲突加 `-2` 后缀 |

#### 验收标准

- [ ] 不扫描 `node_modules`、`.gitmove-vendor` 等（排除目录列表可配置常量）
- [ ] 深度限制生效
- [ ] 与手动 `projects add` 等价的注册结果

#### 风险

- 扫描误注册大量仓 → 默认交互、限制 depth

#### 开放问题

- Q-F10-1：是否接受修订 0.3「不扫描」为「不默认扫描、opt-in scan」？（建议：是）

---

### F11 · `projects update`（批量 git pull）

#### 背景

myrepos `mr update` 批量 pull；gitmove `projects sync pull` 只管 skip reconcile，不代替普通 pull。

#### 用户故事

- **US-F11-1**：作为用户，我希望对注册表项目执行**裸 `git pull --ff-only`**，以便先更新业务仓再跑 sync。

#### 行为规格

```bash
gitmove projects update [--all] [--group G] [--ff-only] [--dry-run]
```

| 项 | 规格 |
|----|------|
| 默认 | 每仓 `git pull --ff-only`（失败则记录继续下一仓） |
| 与 sync 关系 | **独立命令**；文档建议顺序：`update` → `sync check` → `sync pull` |
| 脏工作区 | 跳过并 warn（不 stash） |
| exit code | 任一失败 → 1 |

#### 验收标准

- [ ] `--all` 表格：alias, pull结果, old→new commit
- [ ] NOT_GIT / MISSING 跳过
- [ ] 不调用 gitmove apply/doctor

---

## Epic C · 策略编排（F8、F9）

### F8 · Git hooks 可选集成

#### 背景

repoverlay apply 脚本、Grove hooks；用户希望 pull/checkout 后自动恢复 gitmove 状态。

#### 用户故事

- **US-F8-1**：作为用户，我希望 `gitmove hooks install` 在业务仓安装可选 hook，以便 merge 后自动 `gitmove apply`。
- **US-F8-2**：作为用户，我可以选择 hook 类型与是否仅 warn。

#### 行为规格

```bash
gitmove hooks install [--post-merge] [--post-checkout] [--run apply|doctor|sync-check]
gitmove hooks uninstall
gitmove hooks status
```

**安装位置**：`<repo>/.git/hooks/`（标准 Git hooks，**不进** gitmove.toml）

**hook 脚本内容（建议）**：

- 调用 `gitmove apply -C <repo>` 或 `gitmove doctor -C <repo>`（exit doctor 失败不阻断 git 操作 — **须定稿**）
- 脚本内嵌 repo 绝对路径；移动仓库需 reinstall

**用户级默认**（可选 v2）：`~/.gitmove/settings.toml` 的 `default_hook_run=apply`

#### 验收标准

- [ ] install/uninstall 幂等
- [ ] 已有第三方 hook 时：**链式调用**或拒绝覆盖（须定稿，建议备份 `.sample`）
- [ ] Windows 下 hook 可执行（shebang / git bash）
- [ ] 文档：hooks 为 per-repo 本地，不提交

#### 不交付

- core.hooksPath 全局劫持
- husky/pre-commit 框架集成

---

### F9 · 策略 Profile 切换

#### 背景

repoverlay switch、shimmer 多 overlay；用户 work/home 两套 skip+link 策略。

#### 用户故事

- **US-F9-1**：作为用户，我希望保存命名 profile，并在 `gitmove profile use work` 时切换 active 配置。

#### 数据模型

**方案 A（推荐）**：profile 为独立 TOML 快照

```
.git/gitmove.profiles/
  work.toml
  home.toml
.git/gitmove.toml          # 当前 active（apply 目标）
.git/gitmove.active        # 单行：work
```

**方案 B**：单文件内 `[profiles.work]` — 解析复杂，不首选。

#### 行为规格

```bash
gitmove profile list
gitmove profile save <name>     # 当前 gitmove.toml → profiles/<name>.toml
gitmove profile use <name>      # 复制 profile → gitmove.toml + apply
gitmove profile delete <name>
```

| 项 | 规格 |
|----|------|
| vendor 路径 | profile 含 vendors 段；切换后 apply 重建 link |
| 安全 | save 不删除当前 active；use 前可选 `--dry-run` doctor |
| GUI | v2：profile 下拉（0.5 可仅 CLI） |

#### 验收标准

- [ ] save/use 往返后 doctor 与切换前等价（同一 profile）
- [ ] 切换 profile 不修改 `.gitignore`
- [ ] 与 config import 不冲突（import 覆盖 active toml）

#### 风险

- 用户误以为 profile 会提交 → 文档强调全在 `.git/` 内

---

## Epic D · 错误可视化与可行动修复引导（F13）

> **用户要求**：对这些操作如果出现报错，应提供**可视化解决方法**以及**详细提示如何解决**。  
> 本 Epic 为**横切能力**，与 Epic A–C 同步交付；0.5.0 Phase 1 **必须先落地 F13 基础框架**，再实现各功能错误 catalog。

### 背景与问题（现状）

| 现状 | 问题 |
|------|------|
| CLI 捕获异常后 `console.print(str(exc))` + exit 1 | 用户只见 Git 原始 stderr，不知下一步 |
| `doctor` 仅输出 `message` 字符串 | 无结构化「原因 / 步骤 / 命令」 |
| GUI `_run_background` 失败 → `messagebox.showerror("错误", str(payload))` | 无修复按钮、无分步说明、长文本不可读 |
| 批量操作部分失败 | 汇总不完整，缺少 per-item 修复入口 |

### 目标

1. **统一错误模型**：每条可恢复错误带 **错误码、人话说明、分步修复、可复制命令、可选 GUI 动作**
2. **CLI 富文本引导**：Rich Panel 展示「发生了什么 → 为什么 → 怎么做」
3. **GUI 可视化修复**：错误对话框 + **主操作按钮**（一键 apply / repair / 打开目录等）+ 可展开详情
4. **doctor 可行动化**：每条 issue 绑定 remediation，概览页可点「修复」
5. **覆盖范围**：**全部** gitmove 命令与子流程（含 0.5 新增与既有 0.2–0.4）

### 不交付

- 自动静默修复（须用户确认或显式点按钮，除明确的「一键 apply」类安全操作）
- 多语言 i18n（v1 仅简体中文）
- 在线文档 URL 跳转依赖外网（可本地复制命令为主）

---

### 数据模型 · `Remediation` / `GitMoveError`

新增模块建议：`src/gitmove/errors.py`（或 `remediation.py`）

```python
@dataclass
class RemediationStep:
    title: str              # 步骤标题，如「1. 应用本地配置」
    detail: str             # 说明
    command: str | None     # 可复制 CLI，如 "gitmove apply"
    gui_action: str | None  # GUI 动作 id，如 "apply" | "vendor_sync" | "open_cache"

@dataclass
class GitMoveError(Exception):
    code: str               # 稳定错误码，如 VENDOR_CACHE_DIRTY
    message: str            # 简短摘要（一行）
    cause: str              # 原因说明（人话）
    steps: list[RemediationStep]
    context: dict           # path, vendor_name, alias 等占位符数据
    doc_anchor: str | None  # user-manual 锚点，如 "#vendor-sync-失败"
```

**DoctorIssue 扩展**（向后兼容）：

```python
@dataclass
class DoctorIssue:
    level: str
    category: str
    message: str
    code: str | None = None           # 新增
    remediation: list[RemediationStep] | None = None  # 新增
```

---

### CLI 展示规格

失败时**禁止**仅打印 `str(exception)`。标准输出结构：

```
✗ vendor sync 失败  [VENDOR_FF_BLOCKED]

原因
  上游 cache 无法 fast-forward 到 origin/main，可能存在本地提交或非 FF 历史。

建议操作
  1. 进入 cache 查看状态
     cd ~/gitmove-vendor/cursor-spec && git status
  2. 若可丢弃本地改动，重置后重试
     cd ~/gitmove-vendor/cursor-spec && git reset --hard origin/main
  3. 回到业务仓重新同步
     gitmove vendor sync cursor-spec

文档
  docs/guides/user-manual.md#vendor-sync-失败
```

实现：Rich `Panel` + `Syntax`（命令高亮）+ `--json` 时输出机器可读 remediation（供脚本）。

**`gitmove doctor --fix-hints`（默认开启）**：每条 issue 下追加 remediation 块；`--quiet` 仅计数。

---

### GUI 展示规格

#### 1. 统一错误对话框 `ErrorDialog`（新组件）

替换裸 `messagebox.showerror`，结构：

```
┌─────────────────────────────────────────────┐
│  ✗ Vendor 同步失败                          │
├─────────────────────────────────────────────┤
│  上游 cache 无法 fast-forward…（cause）      │
│                                             │
│  建议步骤：                                  │
│  ○ 1. 打开 cache 目录                       │
│  ○ 2. 检查 git status                       │
│  ○ 3. 重置后重新 sync                       │
│                                             │
│  [ 打开 cache 目录 ]  [ 一键 apply ]  [ 关闭 ] │
│  ▼ 展开技术详情（stderr / 错误码）           │
└─────────────────────────────────────────────┘
```

| 规则 | 说明 |
|------|------|
| 主按钮 | 取 `remediation[0].gui_action` 映射的安全操作（apply、打开文件夹、跳转 repair 向导） |
| 次按钮 | 「复制命令」写入剪贴板 |
| 技术详情 | 默认折叠，含 `code`、原始 stderr |
| 长文本 | 可滚动 `CTkTextbox`，最小 480×320 |

#### 2. 概览页 · doctor 可行动列表

将 `_render_overview` 从纯文本改为 **issue 列表**（或文本 + 每行「修复」按钮）：

- `[错误] skip 未生效: config.local.json` → 按钮 **「应用 skip」** → 调 `skip_mod.apply` + 刷新
- `[错误] vendor cache 缺失` → **「重建 vendor」** → `vendor_mod.apply_vendors`
- `[警告] 项目路径 MISSING` → **「修复路径」** → 打开 F4 repair 迷你向导（输入新 path）

#### 3. 批量操作结果页

「全部 doctor / apply / sync」完成后展示 **结果表格**（非仅 messagebox 字符串列表）：

| 项目 | 状态 | 问题数 | 操作 |
|------|------|--------|------|
| my-app | 失败 | 2 | [查看并修复] |
| other | 成功 | 0 | — |

点「查看并修复」→ 切换该项目 + 打开 ErrorDialog / doctor 面板。

#### 4. 操作前校验（预防性提示）

常见误操作在**执行前**弹确认向导，而非失败后才发现：

- 非 Git 目录选为仓库 → 说明 + 「选择其他目录」
- `vendor add` 目录已存在且无 migrate → 解释 `--migrate` + 勾选「迁移并继续」

---

### 错误码 Catalog（v1 必须覆盖）

以下 **至少** 实现 remediation（单元测试断言 `code` + `steps` 非空）：

#### 通用 / 仓库上下文

| code | 触发场景 | GUI 主操作 |
|------|----------|------------|
| `REPO_NOT_GIT` | 非 Git 目录 | 选择目录 |
| `REPO_NOT_INIT` | 无 gitmove.toml | 一键 init |
| `REPO_CONTEXT_ALIAS_MISSING` | `-C` 别名不存在 | 打开 projects list |
| `PROJECT_PATH_MISSING` | 注册 path 不存在 | 启动 repair 向导 |

#### skip / link / worktree

| code | 触发场景 | 建议命令 / GUI |
|------|----------|----------------|
| `SKIP_NOT_ACTIVE` | skip 未生效 | `gitmove apply` / 应用 skip |
| `LINK_MISSING` | 链接缺失 | `gitmove apply` |
| `LINK_TARGET_MISMATCH` | 目标不一致 | `gitmove link remove` + re-add 或 apply |
| `LINK_VENDOR_CONFLICT` | 与 vendor 路径冲突 | 文档说明 + 跳转 vendor 页 |
| `WORKTREE_NOT_REGISTERED` | worktree 丢失 | `gitmove worktree add` 或 apply |

#### vendor

| code | 触发场景 | 建议 |
|------|----------|------|
| `VENDOR_CACHE_MISSING` | cache 不存在 | `gitmove apply` |
| `VENDOR_CACHE_DIRTY` | cache 有未提交改动 | 打开 cache + status 说明 |
| `VENDOR_FF_BLOCKED` | sync 非 FF | reset cache 步骤 |
| `VENDOR_CLONE_FAILED` | clone 失败 | 检查 URL/网络/凭据 |
| `VENDOR_PATH_EXISTS` | 目录存在需 migrate | `--migrate` 说明 + GUI 勾选 |
| `VENDOR_LINK_BROKEN` | link 断裂 | `gitmove apply` |
| `VENDOR_TRACKED_NOT_SKIP` | 追踪路径未 skip | `gitmove apply` |

#### sync / projects

| code | 触发场景 | 建议 |
|------|----------|------|
| `SYNC_NO_UPSTREAM` | 无 upstream | `git branch -u` 说明 |
| `SYNC_PULL_CONFLICT` | pull 冲突 | `gitmove sync pull` 交互 / 文档 |
| `SYNC_SKIP_CONFLICT` | skip 文件冲突 | l/r/m/s 说明 |
| `PROJECTS_ALIAS_CONFLICT` | 别名重复 | `--alias` 换名 |
| `PROJECTS_UPDATE_FF_FAILED` | pull 非 FF | 手动 merge 步骤 |

#### config / template（0.5 新增）

| code | 触发场景 | 建议 |
|------|----------|------|
| `CONFIG_IMPORT_INVALID` | TOML 无效 | 行号 + export 对比 |
| `TEMPLATE_NOT_FOUND` | 模板 id 不存在 | `vendor template list` |
| `INCLUDE_PATH_NOT_IN_CACHE` | include_paths 无效 | 检查上游目录结构 |

---

### 用户故事

- **US-F13-1**：CLI 报错时，我希望看到分步骤中文说明和可复制命令，而不是 Git 英文 stderr。
- **US-F13-2**：GUI 报错时，我希望有「一键修复」或「打开相关目录」按钮，而不是只有「确定」。
- **US-F13-3**：doctor 概览里每条问题都能点「修复」或看到对应命令。
- **US-F13-4**：批量操作失败时，我希望按项目查看问题并逐个修复，而不是只看一行汇总。

### 验收标准

- [ ] `GitMoveError` + `RemediationStep` 模型；既有 `VendorError`/`RegistryError`/`GitError` 包装或映射为带 remediation 的错误
- [ ] CLI：上述 catalog **≥ 20** 个 code 有测试；失败输出含「原因 + 建议操作 + 命令」三块
- [ ] CLI：`gitmove doctor` 每条 error/warn 带 remediation（`--fix-hints` 默认开）
- [ ] GUI：`ErrorDialog` 替代所有 `messagebox.showerror` 用于 gitmove 业务错误（系统级异常可保留简短框）
- [ ] GUI：概览页 doctor error 至少 **skip / link / vendor** 三类有「修复」按钮且可用
- [ ] GUI：批量 doctor/apply 结果表格含「查看并修复」
- [ ] 文档：`user-manual.md` 增加「常见错误与修复」章节，与 error code 对齐
- [ ] Epic A–C 新增命令（F1–F12）的错误 **纳入 catalog**，不得裸抛异常

### 实现顺序（F13 子阶段）

```
F13-a  errors.py 模型 + CLI Rich 渲染 + 20 码 catalog + 测试
F13-b  doctor issue remediation + CLI doctor 输出
F13-c  GUI ErrorDialog + 概览修复按钮
F13-d  批量结果页 + 预防性确认向导
F13-e  0.5 新功能错误码补全 + user-manual 章节
```

**Phase 1 门禁**：F13-a + F13-b + F13-c 与 F1–F6 同期合并；不得先发功能后补提示。

---

## 跨 Epic 依赖与实现顺序

```
Phase 0 (0.5.0 前置，与 Phase 1 并行启动)
  F13-a errors 模型 + CLI 渲染
  F13-b doctor remediation
  F13-c GUI ErrorDialog + 概览修复按钮

Phase 1 (0.5.0 核心)
  F3 shallow ──┐
  F1 template ─┼─► F2 include_paths（依赖 vendor 稳定）
  F4 repair    │     （repair 与 F13 PROJECT_PATH_MISSING 联动）
  F5 register  │
  F6 GUI sync  │     （失败走 ErrorDialog + 结果表格 F13-d）
  F13-d/e      │     （批量结果 + catalog 补全 + 文档）

Phase 2 (0.5.x)
  F7 pin ──► F12 check-updates
  F11 update
  F10 scan
  F8 hooks
  F9 profile
```

---

## 全局验收（本包 DoD）

- [ ] 各 Epic 单元 + CLI 集成测试；vendor/projects/errors 相关模块覆盖率 ≥ 80%
- [ ] **F13**：catalog ≥ 20 code；CLI/GUI 失败路径无「仅 str(exc)」裸输出（grep 门禁或 lint 测试）
- [ ] README、user-manual（含「常见错误与修复」）、roadmap、docs/README 状态更新
- [ ] 不修改 `.gitignore` 不变量
- [ ] GUI 新功能 headless 可测部分有测试（ErrorDialog 逻辑可抽纯函数测）

---

## 已定决策（原开放问题）

| ID | 决策 |
|----|------|
| Q1 | F10 `projects scan`：**opt-in**，修订 0.3「不自动扫描」 |
| Q2 | F1 模板 id 冲突：**用户模板优先** |
| Q5 | F5 `--register` alias 冲突：**报错**，提示 `--alias` |
| Q7 | F7 pin SHA：cache **允许 detached HEAD** |
| Q8 | F8 post-merge doctor 失败：**不阻断** git，仅 stderr |
| Q9 | F8 hook 已存在：**拒绝覆盖**，提示 manual merge |
| Q10 | 0.5.0 发布：**Phase 1（F1–F6 + F13）先发**，Phase 2 后续版本 |
| Q11 | GUI 一键修复：**apply 类无确认**；delete/reset **须确认** |
| Q12 | Git 原生错误：**包装为 `GIT_COMMAND_FAILED`** + 网络/凭据排查步骤 |

---

## 实现计划 · 0.5.0

### 目标

交付 Phase 0 + Phase 1：Vendor 增强（F1–F3）、多项目增强（F4–F6）、横切错误引导（F13-a–e）。

### 不交付（留 Phase 2）

F7–F12（pin、hooks、profile、scan、update、vendor check-updates exit code）。

### 风险

| 风险 | 缓解 |
|------|------|
| F13 与功能并行改动面大 | 先 F13-a/b 再功能 PR；CLI 统一 `raise_gitmove_error` |
| GUI ErrorDialog 阻塞主线程 | 修复动作走 `_run_background` |
| F2 include_paths 与整仓 link 回归 | 无字段时全量回归测试 |

### 步骤（纵向切片）

1. **errors 基础（F13-a/b）** — `src/gitmove/errors.py`：`GitMoveError`、`RemediationStep`、`catalog`、Rich 渲染；`doctor.py` 扩展 `DoctorIssue`；CLI 全局异常 handler；测试 ≥20 code
2. **GUI 错误 UX（F13-c/d）** — `gui/error_dialog.py`；概览修复按钮；批量结果表格；替换业务 `messagebox.showerror`
3. **Vendor shallow（F3）** — `VendorEntry.shallow`、clone 参数、TOML 往返、doctor warn
4. **Vendor template（F1）** — `templates.toml` 加载、`vendor template list`、`--template`；内置 `cursor-spec`
5. **Vendor include_paths（F2）** — 单元素子目录 link；add/doctor/apply/sync 回归
6. **projects repair（F4）** — CLI 交互 + `--dry-run` + 可选 `--auto`；联动 F13 `PROJECT_PATH_MISSING`
7. **config import --register（F5）** — CLI 选项；alias 冲突报错
8. **GUI batch sync（F6）** — 向导复用 `projects.sync_pull_batch` + ErrorDialog
9. **收尾（F13-e + docs）** — 新功能错误码；`user-manual`「常见错误与修复」；roadmap/README；版本号 0.5.0

### 验证

```bash
pip install -e ".[dev]"
pytest --cov=gitmove --cov-report=term-missing   # ≥ 80%
# 手工：故意 vendor sync 失败 → CLI 分步提示 + GUI ErrorDialog 一键 apply
```

### 模块 touch 清单

| 模块 | 变更 |
|------|------|
| `errors.py` | 新建 |
| `doctor.py` | issue remediation |
| `cli.py` | 异常渲染、新子命令 |
| `vendor.py` | shallow、template、include_paths |
| `registry.py` / `projects.py` | repair |
| `config_io.py` | `--register` |
| `gui/app.py` + `gui/error_dialog.py` | ErrorDialog、sync 向导、批量结果 |

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-29 | 草案：Scope Check + 12 项高契合需求（轮次 1–2） |
| 2026-06-29 | 轮次 3：新增 Epic D / F13 错误可视化与可行动修复引导 |
| 2026-06-29 | **定稿**：用户采纳 Q1–Q12；附 0.5.0 实现计划 |
