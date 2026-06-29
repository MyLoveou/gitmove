---
name: dynamic-workflow-mode
description: 任务级 harness、eval 门禁、跨会话 handoff。多步骤、续作时使用。
origin: ECC dynamic-workflow-mode（通用版）
---

# 动态工作流模式

> 静态 Skill 不够时，为**单任务**设计临时循环与 handoff。

## 何时激活

- 功能跨多个会话（后端 → 前端 → 文档）
- 需要 eval 循环（实现 → 构建 → 冒烟 → 修）
- 用户要求「留 handoff」「按 harness 跑」

## 核心契约

| 项 | 说明 |
|----|------|
| **Objective** | 交付什么；**不交付**什么 |
| **Inputs** | 分支、相关 design 章节 |
| **Outputs** | diff、`.cursor/evals/<feature>.md` |
| **Eval** | 至少一个 pass/fail |
| **Handoff** | 状态、阻塞、续作步骤 |

## 决策树

1. 小改（<3 文件）→ inline，不建 harness
2. 重复流程 → 提取为 Skill（`implement-feature`）
3. 跨会话 → `.cursor/evals/<feature>-handoff.md`
4. 安全敏感 → `@security-reviewer` + 人工 merge

## Harness 模板

```markdown
# Dynamic Workflow · <feature>

Objective: Ship … / Do not ship …

Loop:
1. scope-check
2. @code-architect（若新模块）
3. @backend-dev / @frontend-dev
4. *-reviewer
5. verification-gate
6. @doc-sync

Eval:
- {FRONTEND_BUILD_CMD} → PASS/FAIL
- {BACKEND_BUILD_CMD} → PASS/FAIL
- 若改 backend: 重启+冒烟 → PASS/FAIL

Handoff: status / evidence / next
```

## 提升为共享 Skill

同流程出现 ≥2 次、操作者常跳过门禁、有稳定 eval 命令 → 写入 `.cursor/skills/`。

## 反模式

- 跳过 verification-gate 声称完成
- 多 Agent 无 ownership 改同一文件
