# 智能体模式 × 工作流

> 可执行对照表：将路由、委派、并行、Eval、Handoff 等模式落到四条工作流。

---

## 模式速查（与本库落地）

| 模式 | 含义 | 落地 Skill / Agent / Rule |
|------|------|---------------------------|
| **路由** | 消息/路径/阶段 → Skill 或子代理 | `workflow-triggers`、`workflow-playbooks` |
| **工作流剧本** | 四条端到端串联 | `.cursor/workflows/*.md` |
| **顺序编排** | 固定门禁链，有硬依赖则串行 | 各剧本阶段表 |
| **需求沉淀** | 多轮文档，定稿后再编码 | `requirements-refinement` |
| **委派** | 按改动类型交给 specialist | 各阶段 `@*` Agent、Task |
| **Eval 循环** | Define → Implement → Evaluate → Report | `eval-harness` → `verification-gate` |
| **Handoff** | 跨会话续作 | `dynamic-workflow-mode`、`*-handoff.md` |
| **并行化** | 只读并行；写 lane 隔离 | `parallel-execution` |
| **人类确认门禁** | 定稿/计划/拆 PR 须用户确认 | `requirements-refinement`、`plan-workflow`、`split-prs` |
| **错误恢复** | 403、构建失败固定路径 | `local-dev`、`build-fix`、`*-build-resolver` |
| **模型路由** | 按复杂度选档 / 子代理 | `ai-execution.mdc` §3；`architect` vs `implement-feature` |

**全局反模式**（任何阶段禁止）：

- 多 Agent 无 ownership 改同一文件
- 未 `scope-check` 直接写代码（新能力）
- 需求未定稿就 `implement-feature`（新能力）
- 写 lane 并行导致冲突编辑
- 跳过 `verification-gate` 声称完成

---

## 路由三层（执行时叠加）

```
用户消息 / 路径 / 阶段
  → workflow-triggers / workflow-playbooks（选剧本与 Skill）
  → Skill 内委派表（@子代理 或 Task）
  → Rule globs（backend / frontend / docs 栈规范）
```

| 层 | 文件 |
|----|------|
| 消息 | `workflow-triggers.mdc`（极简） |
| 详表 | `workflow-triggers/SKILL.md` |
| 剧本 | `workflows/*.md` + `workflow-playbooks` |
| 栈 | `backend-spring.mdc`、`frontend-*.mdc`、`java-*`、`react-*`、`vue-*` |

---

## 模式 × 工作流总览

| 模式 | 需求 | 设计 | 开发 | 交付 |
|------|:----:|:----:|:----:|:----:|
| 路由 | ● | ● | ● | ● |
| 顺序编排 | ● | ○ | ● | ● |
| 需求沉淀 | ● | — | — | — |
| 委派 | ● | ● | ● | ● |
| Eval 循环 | ○ | — | ○ | ● |
| Handoff | ● | ○ | ○ | — |
| 并行化 | — | ○ | ● | ○ |
| 人类确认门禁 | ● | — | ○ | ○ |
| 错误恢复 | — | — | ● | — |
| 模型路由 | ● | ● | ● | ● |

● 主用 · ○ 按需 · — 少见

设计可与需求 **并行**（探索期 UI），但开发前须与已定稿需求对齐 → 并行化仅用于只读/探索 lane。

---

## 需求工作流 × 模式

| 阶段 | 主模式 | 次模式 | 说明 |
|------|--------|--------|------|
| 0 范围 | 路由、顺序编排 | 模型路由 | 轻量 `scope-check`；超范围 STOP |
| 1 调研 | 委派 | 路由 | `@marketing-agent`；深度调研可并行只读检索 |
| 2 沉淀 | **需求沉淀** | **人类确认门禁**、Handoff | 多轮；定稿须用户确认 |
| 3 能力约束 | 委派、顺序编排 | 模型路由 | `@architect` 高推理档 |
| 4–5 架构/文档 | 委派 | 顺序编排 | `@doc-sync` 在契约稳定后 |
| 6 计划 | **人类确认门禁** | 委派、并行化（标 Lane） | `plan-workflow` 输出 Lane Matrix |
| 7 Eval 草案 | **Eval 循环** | — | Define 阶段，先于实现 |

---

## 设计工作流 × 模式

| 阶段 | 主模式 | 次模式 | 说明 |
|------|--------|--------|------|
| 0 对齐 | 路由、顺序编排 | — | 新能力无需求 → 回需求流 |
| 1–2 UI 方向/质感 | 委派 | 模型路由 | 主 Agent 可直做；大改版 `@code-architect` |
| 3 无障碍 | 委派 | — | `@a11y-architect` |
| 4 稿转代码 | 委派 | 顺序编排 | `@frontend-vue-dev`；仍须后续 review |
| 5–6 文档/蓝图 | 委派、顺序编排 | 并行化 | 多页联动时 `blueprint` + Lane |

可与需求阶段 **并行** 的 lane：只读竞品 UI 调研、`@code-explorer` 看现有组件（`parallel-execution`）。

---

## 开发工作流 × 模式

| 阶段 | 主模式 | 次模式 | 说明 |
|------|--------|--------|------|
| 0 门禁 | 顺序编排 | 路由 | 未定稿 → 回需求流 |
| 1 依赖 | 委派 | 并行化 | `@code-explorer` 可与只读检索并行 |
| 2 实现 | **顺序编排**、委派 | 并行化 | 默认串行切片；契约已定可前后端 lane |
| 3 并行 | **并行化** | — | 见 `parallel-execution` Lane 表 |
| 4 构建修复 | **错误恢复**、委派 | 模型路由 | `*-build-resolver` |
| 5–6 文档/数据 | 委派 | 顺序编排 | migration 先于依赖它的前端 |
| 7 栈审查 | 委派、**并行化** | — | 双 reviewer（Java + Vue）可并行 |

### 并行 Lane 简表（开发）

| Lane | 可并行？ |
|------|----------|
| 只读 Grep / explore | ✅ |
| `@java-reviewer` + `@vue-reviewer`（不同栈） | ✅ |
| 后端写 + 前端写（同契约、无文件重叠） | ⚠️ 契约已定 |
| 同文件双 Agent 写 | ❌ |
| migration + 依赖该表的前端 | ❌ |

---

## 交付工作流 × 模式

| 阶段 | 主模式 | 次模式 | 说明 |
|------|--------|--------|------|
| 1 DoD | **Eval 循环** | 顺序编排 | `verification-gate` |
| 2 Eval 跑分 | **Eval 循环** | — | Report 更新 |
| 3–4 构建/冒烟 | 顺序编排 | 错误恢复 | 失败 → `build-fix` |
| 5 审查 | 委派、并行化 | — | 多专项 reviewer 可并行 |
| 6 专项 | 委派 | 模型路由 | `@security-reviewer` 高优先级 |
| 7 拆 PR | **人类确认门禁** | 顺序编排 | `split-prs` 须用户确认 |
| 8 文档 | 委派 | — | `@doc-updater` 可选 |

**Eval 闭环**：`Define（需求末）→ Implement（开发）→ Evaluate（交付）→ Report → verification-gate`

---

## 模型与子代理路由（摘要）

| 任务 | 建议 | 典型入口 |
|------|------|----------|
| 分类、窄改 | 主 Agent / 轻量 | `scope-check` 小改 |
| 多文件实现 | 默认实现档 | `implement-feature`、`*-dev` |
| 架构、根因 | 高推理档 | `@architect`、`@code-architect` |
| 只读探索 | explore / `@code-explorer` | 可并行 lane |
| 构建修复 | `*-build-resolver` | 错误恢复路径 |

**Escalation**：低档失败且为推理缺口 → 升一档；禁止为「更快」跳过 scope 或 eval。

---

## 相关文档

- [workflows/README.md](./README.md)
- [workflow-playbooks/SKILL.md](../skills/workflow-playbooks/SKILL.md)
