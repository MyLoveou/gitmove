---
name: workflow-triggers
description: >-
  工作流路由详表（唯一详表）。触发：规划、构建失败、403、验收、审查、拆 PR、eval、
  改 .cursor、提需求、新 API、需求/设计/开发/交付工作流。
---

# 工作流触发路由（详表）

> **本文件为触发表唯一详表**。机器副本：`.cursor/rules/workflow-triggers.mdc`（极简，指向此处）。

## 使用方式

1. 收到消息或准备改代码前，扫描触发信号
2. 命中 → **先读**对应 `.cursor/skills/<name>/SKILL.md`
3. 多条命中 → 按优先级串联
4. 交付前 → 几乎总是 `verification-gate`

## 工作流剧本（四条主流程）

> **串联 Skill + Agent + Rule 的端到端剧本**：`.cursor/workflows/`  
> 入口 Skill：`workflow-playbooks`

| 口令 | 剧本 | 文件 |
|------|------|------|
| 需求工作流、提需求、需求定稿 | 需求 | `workflows/requirements.md` |
| 设计工作流、UI 设计、设计稿转 Vue | 设计 | `workflows/design.md` |
| 开发工作流、开始实现、修 bug | 开发 | `workflows/development.md` |
| 交付工作流、验收、DoD、准备 PR | 交付 | `workflows/delivery.md` |
| 端到端、从需求到交付 | 顺序执行 | 需求 → 设计（可选）→ 开发 → 交付 |

命中「工作流」类口令 → **先读** `workflow-playbooks` Skill，再打开对应 `workflows/*.md` 按阶段表执行。

## 用户消息 → Skill

| 触发信号 | Skill | 优先级 |
|----------|-------|--------|
| 新功能、新 API、纵向切片 | `scope-check` → `requirements-refinement` → `plan-workflow` → `implement-feature` | P0 |
| 提需求、新需求、需求设计、验收标准 | `requirements-refinement` | P0 |
| 市场调研、竞品、TAM、投资者尽调 | `market-research` | P0 |
| 深度调研、多源检索、带引用报告 | `deep-research` | P1 |
| PRD→能力约束、跨服务能力边界 | `product-capability` | P1 |
| 蓝图、多 PR、多会话施工计划 | `blueprint` | P1 |
| UI 方向、更精致、少模板感 | `frontend-design-direction` | P1 |
| 设计稿转 Vue、批量截图转页面 | `ui-to-vue` | P1 |
| 修 bug、改 UI、实现 | `implement-feature` | P0 |
| 规划、计划、蓝图 | `plan-workflow` | P0 |
| 构建失败、compile、TS error | `build-fix` | P0 |
| 401、403、联调、端口 | `local-dev` | P0 |
| 验收、DoD、交付、PR | `verification-gate` | P0 |
| 审查、review | `code-review-gate` | P1 |
| 拆 PR、分仓 | `split-prs` | P1 |
| 加依赖 | `search-first` | P1 |
| eval、pass/fail | `eval-harness` | P1 |
| handoff、跨会话 | `dynamic-workflow-mode` | P1 |
| 并行、加快、多 agent、worktree、lane | `parallel-execution` | P1 |
| 需求/设计/开发/交付工作流、走流程 | `workflow-playbooks` | P0 |
| 智能体模式、委派、并行、Handoff | `workflow-playbooks` → `workflows/agent-patterns.md` | P1 |
| 改 .cursor | `agent-harness-construction` | P1 |

## 路径触发

| 路径 | Skill |
|------|-------|
| 新建 backend Controller、migration（**新能力**） | `scope-check` → `requirements-refinement`（**已定稿**）→ `implement-feature` |
| 改已有 Controller（bug/小改，无新 API） | `implement-feature` |
| Security/JWT 配置 | `code-review-gate` + `@security-reviewer` |
| 改 API 设计文档 / DTO | `@doc-sync`；新能力须需求已定稿 |
| 改 `docs/requirements/features/**` | `requirements-refinement` |
| 改 `docs/product/**`、能力边界讨论 | `product-capability` 或 `@product-manager` |
| `frontend/**/*.vue` | `frontend-vue-dev`；大 UI 改 + `frontend-design-direction` |
| `{DEPRECATED_API}` 引用 | **STOP** + `scope-check` |
| `.cursor/**` | `agent-harness-construction` |

## 阶段触发

| 阶段 | Skill |
|------|-------|
| 编码开始（新任务） | `scope-check` → `requirements-refinement`；大任务 + `plan-workflow` + `eval-harness`；多 lane + `parallel-execution` |
| 改完 Java（交付前） | `@java-reviewer` |
| 改完 tsx（交付前） | `@react-reviewer` |
| 改完 .vue（交付前） | `@vue-reviewer` |
| 声称完成 / stop hook | `verification-gate` |

## 标准组合

```
【端到端新功能】workflow-playbooks
  → 需求 → 设计（可选）→ 开发 → 交付

【新需求】scope-check → requirements-refinement（多轮定稿）
  → plan-workflow → eval-harness → implement-feature
  → reviewers → verification-gate

【新 API】scope-check → requirements-refinement → plan-workflow → eval-harness → implement-feature
  → reviewers → verification-gate

【仅修构建】build-fix → verification-gate

【403】local-dev → @code-explorer → verification-gate

【拆 PR】split-prs → 各仓 verification-gate → code-review-gate
```

## ECC 对照

| ECC | Skill |
|-----|-------|
| `/plan` | `plan-workflow`（须需求已定稿） |
| 需求沉淀 | `requirements-refinement` |
| `/build-fix` | `build-fix` |
| `/verify` | `verification-gate` + `backend-verify` |
| `/code-review` | `code-review-gate` |
| split-to-prs | `split-prs` |
| parallel lanes | `parallel-execution`（详版 → `parallel-execution-optimizer`） |

## 维护

新增 Skill 时：**只改本文件**。`workflow-triggers.mdc` 保持极简，勿复制整张表。
