---
name: plan-workflow
description: >-
  规划、计划、蓝图、怎么拆、实现方案、多 PR 步骤。触发：规划、计划、plan、先别写代码。
origin: ECC /plan（通用版）
---

# 规划工作流（Plan）

> **需求文档已定稿 → 出实现方案 → 用户确认 → 再写代码**（除非用户明确「直接做」）。

## 前置门禁

- `requirements-refinement` 已完成，且 `docs/requirements/features/<id>.md` 状态为 **已定稿**
- 或：用户明确「直接做」且已记录文档滞后风险
- 未定稿 → **STOP**，回到 `requirements-refinement`

## 何时触发

- 「规划」「计划」「怎么拆」「蓝图」
- 新能力、多文件/多模块联动
- 任务明显 >1 PR 或 >3 步
- **未**说「直接做」「just do it」

## 流程

### 1. 范围与需求（必做）

读 `scope-check` → 读已定稿需求 `docs/requirements/features/<id>.md` → 输出 IN SCOPE / OUT OF SCOPE 与计划对齐检查。

### 2. 现状（只读）

- Task `explore` 或 `@code-explorer`
- 读 `{API_DESIGN_DOC}`、`{DATA_MODEL_DOC}` 相关章节

### 3. 方案输出

```markdown
## 实现计划 · <功能名>

### 目标 / 不交付
### 风险
### 步骤（纵向切片）
1. migration + entity …
2. service + controller …
3. frontend types + api …
4. 页面 …
5. docs …

### 验证
- eval：`.cursor/evals/<feature>.md`（可选）
- 交付：`verification-gate`

### 并行 Lane（大任务可选）
- 读 `parallel-execution`，在计划中附 Lane Matrix
- 探索阶段：backend / frontend / 文档 **只读可并行**
- 实现阶段：默认串行；契约已锁定且无写冲突时可标 gated 并行
```

### 4. 确认门禁

**默认等待用户确认**后再编码。

### 5. 大任务

跨会话 → `dynamic-workflow-mode` + handoff 文件。

明显多 lane（>3 独立步骤）→ 计划中要求 `parallel-execution` Lane Matrix。

## 委派

| 需要 | 使用 |
|------|------|
| 文件级蓝图 | `@code-architect` |
| 架构 | `@architect` |
| 产品边界 | `@product-manager` |

## 反模式

- 需求未定稿就列实现步骤
- 未 scope-check 就列步骤
- 发明未登记 API path
- 计划含 OUT OF SCOPE 能力
