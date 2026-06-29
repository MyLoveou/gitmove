---
name: implement-feature
description: >-
  按纵向切片实现功能（后端+前端+迁移+文档）。
---

# 功能纵向切片（Implement Feature）

> 标准顺序：**migration → 后端 → 前端 types/api → UI → docs**  
> **硬门禁**：新能力须 `requirements-refinement` 已定稿（或用户显式承担文档滞后风险）。

## 何时读

- 需求文档 **已定稿** + `plan-workflow` 已确认（或用户「直接做」且已说明风险）
- `scope-check` 为 IN SCOPE 后，且非可跳过沉淀的新能力
- 修 bug / 小改 UI（可跳过 plan 与 requirements-refinement，仍建议 scope-check）

## 硬门禁（新能力）

开始写业务代码前确认：

- [ ] `docs/requirements/features/<id>.md` 状态 = **已定稿**
- [ ] 验收标准已写入需求文档 §4
- [ ] API/数据变更已在 design 文档登记（若适用）

未满足 → **STOP**，执行 `requirements-refinement`，不得新建 Controller / 页面 / migration。

## 流程

### 1. 读契约

- `{API_DESIGN_DOC}` 相关 §
- `{DATA_MODEL_DOC}` 若动实体

### 2. 后端（若有）

```
Flyway V{n}__*.sql → entity → repository → service → dto → controller
```

- `@Valid` DTO；`GlobalExceptionHandler`
- `{BACKEND_BUILD_CMD}` → 失败则 `build-fix`
- 改 backend → 计划内包含重启+冒烟

### 3. 前端（若有）

```
types → api/*.ts → pages/components
```

- 前端目录：`.cursor/rules/frontend-react.mdc` 或 `frontend-vue.mdc`
- `{FRONTEND_BUILD_CMD}`

### 4. 文档

- 同步 `{API_DESIGN_DOC}` / `{DATA_MODEL_DOC}`

### 5. 收尾

- `@java-reviewer` / `@react-reviewer`（建议）
- `verification-gate`

## 并行决策

默认 **串行** 执行 §2–§4。读 `parallel-execution` 后再并行：

| 条件 | 允许 |
|------|------|
| 仅仓库探索 / 读契约 | ✅ 批量只读并行 |
| migration 未完成且前端依赖该表 | ❌ 先 migration + 后端 |
| 契约已在 design 文档锁定 | ⚠️ 后端与前端（mock）可 gated 并行 |
| 两 lane 改同一文件 | ❌ 单 ownership |

`plan-workflow` 已附 Lane Matrix 时，按 Matrix 执行；否则不擅自并行写。

## 原则

- 最小 diff；匹配现有分层与命名
- 不发明未登记 API path
- 未实现 Phase → 501 或占位 UI

## 项目定制

复杂领域（多 API 域、特殊 Flyway 编号等）在项目内扩展本 Skill 或增加并列 Skill，并更新 `workflow-triggers`。
