---
name: split-prs
description: >-
  大改拆成多个可审 PR。触发：拆 PR、分仓提交、split PR、别一次提交太多。
origin: ECC split-to-prs（通用版）
---

# 拆 PR 工作流

> 适配 **monorepo** 或 **多 Git 仓**；在 `constraints.md` 写明仓库布局。

## 何时触发

- 单次改动跨 backend + frontend + docs
- 用户要求「拆 PR」
- 改动过大，审查困难

## 硬规则

- **用户未要求不 commit/push**
- 拆 PR 计划须用户确认
- 禁止 `git add .`；按 slice 精确 staging
- 禁止 destructive git 除非用户明确要求

## 典型切片顺序

```
1. docs（契约先行，若 API 已敲定）
   或 backend migration + API
2. backend
3. frontend（types + api + UI）
4. docs 补漏
```

多仓时在对应目录分别 git：

| 仓 | 路径 | 典型内容 |
|----|------|----------|
| backend | `{BACKEND_DIR}/` | Java、migration |
| frontend | `{FRONTEND_DIR}/` | TS/TSX |
| docs | `docs/` | API、数据模型 |

## 流程

### 1. 盘点

各仓 `git status` / `git diff --stat`；列出 slice 与依赖。

### 2. 计划（给用户）

| # | 仓 | 范围 | 依赖 |
|---|-----|------|------|

### 3. 每 slice 门禁

`code-review-gate`（相关部分）→ `verification-gate`（至少该仓 build）

### 4. 执行

用户确认后按 slice commit；用户要求时再 push / `gh pr create`。

## 反模式

- backend 未验证就 claim 前端可联调
- docs 与 DTO 不一致跨 PR 合并
