# gitmove GUI 体验优化与场景指引

**状态**：评审中  
**目标版本**：0.5.3（GUI）/ 0.6 可拆分  
**依赖**：`gitmove-core.md`、`gitmove-vendor.md`、`gitmove-0.5-enhancements.md` F13、`gitmove-cursor-vendor-profile.md`  
**定稿日期**：—（待用户确认）

## 文档说明

用户反馈：**GUI 功能多但不知所用**——不清楚 skip / link / vendor / profile / sync 的区别与选型。  
本文档沉淀 **信息架构、场景指引、交互优化** 需求；**不**改用 Vue/Web（技术栈仍为 CustomTkinter）。

> **说明**：`ui-to-vue` Skill **不适用**于本项目（无 Vue 前端）。UI 优化在 `src/gitmove/gui/` 内迭代。

---

## Scope Check

| 结论 | 说明 |
|------|------|
| **IN SCOPE** | 场景入口（我要做什么）、能力缺失 Tab（Vendor/Profile/Sync）、空状态与文案、概览页重构、上下文帮助、TDD 可测的展示逻辑 |
| **Phase 1** | 场景面板 + 文案 + Vendor/Profile Tab（只读列表 + 跳转 CLI 提示） |
| **Phase 2** | Vendor/Profile 完整 CRUD、Sync 向导、Profile 切换 UI、修复按钮矩阵 |
| **OUT OF SCOPE** | Vue/React 重写、Web GUI、设计稿批量转代码（ui-to-vue）、改 CLI 语义 |

---

## 背景与问题

### 现状（v0.5.2 GUI）

| 已有 | 缺失 / 薄弱 |
|------|-------------|
| 侧栏多项目、批量 doctor/apply/sync | **Vendor** 无 Tab（CLI 已有） |
| Tab：概览 / Skip / Link / Worktree | **Profile** 无 Tab（CLI 已有 reconcile） |
| 初始化、一键 apply、doctor 文本 | **Sync check/pull** 无单仓入口 |
| ErrorDialog（部分路径） | **场景选型** 无引导（用户不知用 skip 还是 link） |
| | 概览仅文本墙，无分级/无「下一步」 |
| | 空 Tab 无说明（「何时用 skip？」） |

### 目标用户痛点

1. 「本地配置文件不想提交」→ 不知道选 skip 还是 link  
2. 「`.cursor` 来自另一个 Git 仓」→ 不知道 vendor，GUI 无入口  
3. 「公司 / 个人规范切换」→ profile 仅 CLI  
4. 「doctor 报错」→ 看不懂 category，不知点哪修复  

---

## 用户故事

### US-G1 · 场景选型（P0）

- **作为** 新用户  
- **我希望** 打开 GUI 看到「我想做什么」场景卡片  
- **以便** 直接跳到对应 Tab 或向导，而不是读手册

**场景卡片（v1 至少 6 个）**：

| ID | 用户表述 | 推荐能力 | 跳转 |
|----|----------|----------|------|
| S1 | 已追踪文件，本地改不想提交 | skip | Skip Tab + 简短说明 |
| S2 | 整目录放盘外（未追踪） | link | Link Tab |
| S3 | 目录内容来自另一个 Git 仓 | vendor | Vendor Tab |
| S4 | 公司 / 个人 Cursor 规范切换 | profile | Profile Tab |
| S5 | 远程也改了 skip 文件 | sync | Sync 面板 |
| S6 | 同仓多分支实验 | worktree | Worktree Tab |

### US-G2 · 概览页可行动（P0）

- **作为** 用户  
- **我希望** doctor 结果按 **error / warn / info** 分组，每条带 **建议操作**  
- **以便** 知道先修什么

**Given** doctor 有 link error  
**When** 查看概览  
**Then** 显示「修复：重建链接」按钮（调用 apply 或 link 修复）

### US-G3 · Vendor Tab（P1）

- **作为** 用户  
- **我希望** 在 GUI 查看 vendor 列表、cache 状态、sync  
- **以便** 不必记 CLI

**Phase 1**：list + status +「在终端执行…」复制  
**Phase 2**：add 对话框（url、ref、pin、migrate）、sync/remove 按钮

### US-G4 · Profile Tab（P1）

- **作为** 用户  
- **我希望** 下拉切换 company / personal profile  
- **以便** 完成 [cursor-vendor-profile](../features/gitmove-cursor-vendor-profile.md) 工作流

**Given** 已 save `company` / `personal` profile  
**When** 选择 profile 并确认  
**Then** 调用 `profile.use_profile`（含 reconcile），刷新全 Tab

### US-G5 · 空状态教育（P0）

- **作为** 用户  
- **我希望** 空 Tab 显示「适用场景 + 典型路径 + 打开文档」  
- **以便** 减少误用

示例（Skip Tab 空）：

```text
适用：已被 Git 追踪、仅本地修改的小文件（如 appsettings.Development.json）
不适用：未追踪目录（请用「外部链接」）
[添加路径]  [查看文档]
```

### US-G6 · Sync 单仓（P2）

- **作为** 用户  
- **我希望** 当前仓库 sync check / pull（与 CLI 一致）  
- **以便** 不只用侧栏「全部 sync」

---

## 信息架构（目标布局）

```text
┌──────────────┬────────────────────────────────────────────────────┐
│ 项目侧栏      │ [仓库路径] [选择] [刷新]                              │
│ · alias      │ [初始化] [一键应用] [健康检查]                          │
│ · 批量操作    ├────────────────────────────────────────────────────┤
│              │ Tab: 开始 | 概览 | Skip | Link | Vendor | Profile | … │
│              │                                                    │
│              │ 「开始」Tab：场景卡片 S1–S6                           │
│              │ 「概览」：分级 doctor + 修复按钮 + external_base       │
│              │ 各能力 Tab：表格 + 空状态 + 上下文帮助链接               │
└──────────────┴────────────────────────────────────────────────────┘
```

**Tab 顺序建议**：`开始` → `概览` → `Skip` → `外部链接` → `Vendor` → `Profile` → `Worktree` → `同步`

---

## 交互规格

### 场景卡片（开始 Tab）

- 卡片：图标 + 标题 + 一行说明 +「去了解」  
- 点击：切换 Tab + 可选一次性 Tooltip（3 秒内可关）  
- 底部：链接 `docs/guides/workflows.md` 能力选型表（系统浏览器打开）

### 概览页

| 元素 | 规格 |
|------|------|
| 摘要条 | `✓ 通过` / `⚠ N 警告` / `✗ N 错误` |
| 问题列表 | Treeview：级别 · 分类 · 消息 · [修复] |
| 修复按钮 | 映射 `remediation.gui_action`（apply / vendor_sync / open_cache） |
| 外部根路径 | 保留现有 entry + 保存 |

### Vendor Tab（Phase 1）

| 列 | 说明 |
|----|------|
| 名称 | vendor name |
| 挂载路径 | repo_path |
| 上游 | source_url @ ref |
| Pin | source_pin 或 — |
| 状态 | link_ok / behind / pin_drift |
| 操作 | 刷新 · Sync · 复制 CLI |

### Profile Tab（Phase 1）

- 下拉：已保存 profile 列表 + 当前 active 标记  
- 按钮：`切换`（confirm）· `保存当前为…` · `dry-run 预检`  
- 说明文案：company vs personal 区别（链到 cursor-vendor-profile 文档）

### 文案原则

- **按钮**：动词 + 对象（「添加 skip 路径」而非「添加」）  
- **状态栏**：`已加载 · 3 skip · 1 vendor · profile: personal`  
- **禁止**：未解释缩写（SWT、FF）；首次出现给全称  

---

## 验收标准

### Phase 1（场景 + 教育 + 概览）

- [ ] **GUX-1** 存在「开始」Tab，含 ≥6 场景卡片，点击跳转正确 Tab  
- [ ] **GUX-2** Skip/Link/Worktree/Vendor/Profile 空状态含适用说明 + 文档链接  
- [ ] **GUX-3** 概览 doctor 分 error/warn/info 展示，error 有「一键 apply」或分类修复入口  
- [ ] **GUX-4** Vendor Tab 只读列表与 CLI `vendor list/status` 一致  
- [ ] **GUX-5** Profile Tab 显示 active profile + list；切换调用 CLI 同源 API  
- [ ] **GUX-6** GUI 集成测试覆盖：场景跳转、概览渲染、Vendor 列表 refresh（headless）

### Phase 2（完整操作）

- [ ] **GUX-7** Vendor add/sync/remove 对话框  
- [ ] **GUX-8** Sync 单仓 check + pull 向导（复用 sync_chooser）  
- [ ] **GUX-9** 概览每条 doctor issue 的 gui_action 可点击  
- [ ] **GUX-10** 批量操作结果表格（F13-d）

---

## TDD 计划

| ID | 测试 | 类型 | Phase |
|----|------|------|-------|
| T-G1 | `test_scenario_cards_navigate_to_tabs` | GUI integration | 1 |
| T-G2 | `test_empty_skip_tab_shows_guidance_text` | GUI integration | 1 |
| T-G3 | `test_overview_groups_doctor_by_level` | 单元（抽 `_format_overview`） | 1 |
| T-G4 | `test_vendor_tab_lists_entries` | GUI integration | 1 |
| T-G5 | `test_profile_tab_use_switches_active` | GUI integration | 1 |
| T-G6 | `test_profile_use_dry_run_from_gui` | GUI integration | 2 |

**原则**（tdd-workflow）：

1. 先抽 **纯函数**（概览格式化、场景 metadata）→ 单元测 RED/GREEN  
2. GUI 集成测 mock `messagebox` / 后台任务，与 `test_gui_integration.py` 一致  
3. 每 Phase checkpoint commit：`test:` / `fix:`  

---

## 技术约束

- **栈**：CustomTkinter + ttk.Treeview（与现有一致）  
- **逻辑**：GUI 仅调用 `gitmove.*` 业务模块，不重复业务规则  
- **线程**：长操作继续 `_run_background` + `call_on_main_thread`  
- **a11y v1**：键盘 Tab 顺序、按钮最小点击区 44px 高（CTk 默认接近）

---

## 开放问题（须用户确认）

| ID | 问题 | 建议默认 |
|----|------|----------|
| Q1 | 默认 landing Tab：`开始` 还是 `概览`？ | **开始**（新用户）/ 有 config 时 **概览** |
| Q2 | Vendor add 是否在 Phase 1 做简化表单？ | **否**，Phase 1 只读 + 复制 CLI |
| Q3 | 是否内置打开本地 user-manual（浏览器/file）？ | **是**，`webbrowser.open(file://...)` |
| Q4 | 中英文：仅中文还是跟随系统？ | **v1 仅中文**（与现 GUI 一致） |

---

## 下一步

1. 用户确认 Q1–Q4 → 状态改 **已定稿**  
2. `plan-workflow` 拆 Phase 1 纵向切片（见 [gui-ux.md](../design/gui-ux.md)）  
3. TDD：T-G3 纯函数 → T-G1/G2 → Vendor/Profile Tab  
4. `verification-gate`：`pytest tests/test_gui*.py` + 手工走 S1–S6 场景

---

## 相关文档

- [GUI 交互设计](../design/gui-ux.md)
- [用户手册 · GUI](../guides/user-manual.md#5-图形界面gui使用)
- [能力选型表](../guides/workflows.md#7-能力选型简表)
- [0.5 F13 GUI 规格](gitmove-0.5-enhancements.md#gui-展示规格)
