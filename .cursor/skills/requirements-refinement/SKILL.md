---
name: requirements-refinement
description: >-
  新需求多轮迭代沉淀文档，定稿后再实现。触发：提需求、新需求、需求设计、先写文档、
  需求不完整、补充需求、验收标准、开放问题、定稿。
origin: 项目规范（需求先行门禁）
---

# 需求沉淀（Requirements Refinement）

> **文档定稿 → 再规划 → 再编码**。禁止在需求/契约未沉淀时开始 `implement-feature`。

## 何时触发

- 用户**提出新需求**、新功能、新 API（非明确 bug 修复）
- 需求描述含糊、缺验收标准、缺边界
- 用户说「先写文档」「需求还不完整」「多轮讨论」
- `scope-check` 为 IN SCOPE 后的**下一步**（新能力必经）

## 何时可跳过

| 场景 | 条件 |
|------|------|
| Bug 修复 | 有明确复现；不新增对外 API/表 |
| 极小 UI 文案/样式 | 无契约变更；用户确认 |
| 用户明确「直接做」 | 须注明**接受文档滞后**风险；实现后补文档 |
| PLACEHOLDER | 仅 501/占位 UI，无真实业务 |

跳过须在回复中写明理由。

## 文档落点

```
docs/requirements/features/<feature-id>.md   # 主需求包（本 Skill 维护）
docs/design/03-API设计.md                    # 定稿后同步 API 章节
docs/design/06-总数据模型.md                 # 定稿后同步实体/表
docs/design/adr/                           # 架构抉择时新建
```

模板（规范库维护者参考）：`templates/docs-requirements-feature.md.template`；业务项目按上文「文档落点」结构编写

文首 **状态**：`草案` → `评审中` → `已定稿`（仅 `已定稿` 可进入 `plan-workflow` / `implement-feature`）。

## 多轮迭代流程

每轮结束输出：**本轮变更摘要** + **开放问题清单** + **下一轮建议**；**等待用户确认**后再进入下一轮或定稿。

### 轮次 1 · 问题与边界

委派 `@product-manager` 或主 Agent：

- 背景、目标用户、要解决的问题
- 初步 IN SCOPE / OUT OF SCOPE
- 与 `{CAPABILITY_DOC}` / 路线图对齐结论
- **开放问题**（须用户回答的）

产出：创建/更新 `docs/requirements/features/<id>.md`，状态 `草案`。

### 轮次 2 · 场景与验收

- 用户故事或主流程（Given / When / Then）
- 验收标准 checklist（可测、可判 pass/fail）
- 边界与异常（权限、空数据、并发、错误提示）
- 非功能要求（若有）：性能、审计、兼容

更新开放问题；状态 `评审中`。

### 轮次 3 · 契约草案（按需）

若涉及 API / 数据 / 跨模块：

- 端点草案、请求/响应字段、错误码
- 实体/表变更草案、migration 要点
- 前端页面/路由/状态要点
- 委派 `@architect`（架构）、`@doc-sync`（契约结构）

仍 `评审中`；**不在此轮写业务代码**（仅可更新 design 文档草案段）。

### 轮次 4 · 定稿门禁

**定稿前检查**（全部满足才可标 `已定稿`）：

- [ ] 开放问题已关闭或记入 OUT OF SCOPE / 后续 Phase
- [ ] 验收标准完整、无「待定」阻塞项
- [ ] API/数据变更已写入 design 文档或 ADR（若有）
- [ ] 用户明确确认「可以按此实现」

动作：

1. 需求文档状态 → `已定稿`
2. 同步 `{API_DESIGN_DOC}`、`{DATA_MODEL_DOC}`（`@doc-sync`）
3. 可选：`.cursor/evals/<feature>.md` 从验收标准生成 eval
4. 进入 `plan-workflow`（大任务）或 `implement-feature`（小且清晰）

## 单轮输出模板

```markdown
## 需求沉淀 · 轮次 N · <feature-id>

### 本轮结论
- 状态：草案 / 评审中 / 已定稿
- 文档：`docs/requirements/features/<id>.md`

### 变更摘要
- …

### 开放问题（须用户回复）
1. …

### 下一步
- [ ] 继续轮次 N+1 / [ ] 用户确认定稿 / [ ] 进入 plan-workflow
```

## 与上下游 Skill

```
scope-check (IN SCOPE)
  → requirements-refinement（多轮，仅文档）
  → plan-workflow（已定稿后）
  → eval-harness（可选）
  → implement-feature（硬门禁：需求已定稿）
  → code-review-gate → verification-gate
```

## 跨会话

多轮跨天 → `dynamic-workflow-mode` + `docs/requirements/features/<id>-handoff.md`（示例：`.cursor/evals/_example-requirements-handoff.md`）

## 反模式

- 用户一句需求直接写 Controller / 页面
- 开放问题未关闭却标已定稿
- 只在聊天里讨论、不落 `docs/requirements/`
- 定稿不同步 API/数据模型文档
- 用「先实现再补文档」处理**新能力**（除非用户显式承担风险）

## 委派

| 需要 | 使用 |
|------|------|
| 边界与验收 | `@product-manager` |
| 架构/模块划分 | `@architect` |
| 契约文档结构 | `@doc-sync` |
| 只读现状 | `explore` / `@code-explorer` |
