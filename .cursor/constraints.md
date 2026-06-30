# gitmove · 硬约束

> 通用 DoD：`verification-gate` Skill · `.cursor/constraints.md`

---

## 1. 仓库结构

| 目录 | 技术栈 | 职责 |
|------|--------|------|
| `src/gitmove/` | Python 3.10+ | CLI、GUI、skip/link/worktree 模块 |
| `docs/` | Markdown | 需求、设计、规范 |

---

## 2. 版本 / 范围边界

- **权威能力文档**：`README.md` + `docs/requirements/features/`
- **架构与路线图**：`docs/design/overview.md`、`docs/product/roadmap.md`
- **禁止提前实现**：修改团队 `.gitignore`、强制 push、未经请求 commit/push

---

## 3. 架构不变量（违反即 bug）

1. 配置仅写入 `.git/gitmove.toml`，不修改 `.gitignore`
2. CLI 与 GUI 共用 `doctor.py` / 各业务模块，不重复实现 Git 逻辑
3. 跨平台链接：Windows 默认 junction，macOS/Linux 默认 symlink

---

## 4. 开发习惯

- 最小 diff；匹配现有命名与分层
- 未要求不 commit/push；不提交密钥、`.env`、`config.local.json`
- 完成前：`pip install -e .` 且 `gitmove doctor` 通过
- **新能力**：对应 `docs/requirements/features/<id>.md` 状态为 **已定稿** 后方可编码
  - `gitmove-core.md` · `gitmove-config-sync.md` · `gitmove-multi-project.md` · `gitmove-vendor.md` · `gitmove-0.5-enhancements.md`

---

## 5. 常见陷阱

| 陷阱 | 正确做法 |
|------|----------|
| 在 Windows 硬编码 junction | 使用 `platform_util.resolve_link_type()` |
| GUI 阻塞主线程执行 git | 长操作应异步或明确文档化限制 |
| skip 文件 pull 冲突 | 文档化：先 remove skip → stash → pull → pop → re-add |

---

## 6. 完成定义（DoD）

- [ ] 范围符合 capability（`scope-check`）
- [ ] `verification-gate` 已执行
- [ ] `pip install -e .` 成功，`gitmove` / `gitmove-gui` 可运行
- [ ] `gitmove doctor` 通过（在测试仓库内）
- [ ] 未提交密钥与本地配置文件
