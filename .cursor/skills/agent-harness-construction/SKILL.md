---
name: agent-harness-construction
description: 设计 Agent 驾驭层（Rules/Skills/Agents/Hooks）。改 .cursor/ 配置时使用。
origin: ECC agent-harness-construction（通用版）
---

# Agent Harness 构建

> 改进 Agent 规划、工具调用、错误恢复与完成率。

## 何时使用

- 新增/调整 `.cursor/rules/`、`.cursor/skills/`、`.cursor/agents/`、`.cursor/hooks/`
- Agent 频繁 retry、误判、漏交付步骤
- 多 Agent 编排策略

## Harness 分层

| 层 | 路径 | 职责 |
|----|------|------|
| 硬约束 | `.cursor/constraints.md` | 不变量、DoD（精简） |
| Rules | `.cursor/rules/*.mdc` | glob / alwaysApply |
| Skills | `.cursor/skills/*/SKILL.md` | 按需读的流程 |
| Agents | `.cursor/agents/*.md` | `@` 角色 |
| Hooks | `.cursor/hooks/hooks.json` | stop 等提醒 |
| 选型 | `.cursor/ecc-manifest.md` | DAILY vs LIBRARY |

**原则**：alwaysApply Rule 保持精简；长指引放 Skill。

## 四维质量

1. **Action space** — 工具/子代理语义不重叠
2. **Observation** — 构建/冒烟输出可行动
3. **Recovery** — 403/编译失败有恢复路径
4. **Context budget** — 引用路径，不内联长文档

## 稳定入口（示例）

| 场景 | 首选 |
|------|------|
| 探索 | `explore` / `@code-explorer` |
| Java 构建 | `@java-build-resolver` |
| 前端构建 | `@react-build-resolver` |
| 审查 | `@java-reviewer` / `@react-reviewer` |
| 范围 | `scope-check` |
| 新需求沉淀 | `requirements-refinement` |
| 交付 | `verification-gate` |
| 并行 / 多 lane | `parallel-execution` |

## 错误恢复

| 症状 | 处理 |
|------|------|
| GET 200 / PUT 403 | 重启后端 → 仍失败则 `@code-explorer` |
| Flyway 失败 | 查日志；勿改已执行 V{n} |
| npm build 类型错 | `@react-build-resolver`；核对 API 契约 |

## 反模式

- 多 Agent 重叠做同一件事
- 不 scope-check 直接写代码
- 需求未定稿就 implement-feature（新能力）
- 改 backend 不重启
- Rule 复制 design 文档全文

## 维护

- 通用改进同步到规范库 `.cursor/`（本仓库根目录）
- 新增 DAILY → 更新 `ecc-manifest.md`、**仅** `skills/workflow-triggers/SKILL.md`
