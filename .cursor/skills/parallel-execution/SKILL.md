---
name: parallel-execution
description: >-
  并行 lane、批量只读、worktree 隔离、加快多任务。触发：并行、加快、同时、多 agent、worktree、lane。
origin: ECC parallel-execution-optimizer（通用精简版）
---

# 并行执行（Parallel Execution）

> 用 **依赖图** 换速度：只读并行，写入隔离，合并前验证。

## 何时触发

- 用户要求「并行」「加快」「多 agent 同时」
- 大任务：多目录探索、前后端可拆分、多仓 build
- 规划输出需标 lane 时（配合 `plan-workflow`）

## 何时不并行

- 未 `scope-check` 的任务
- 两 lane 写同一文件 / 同一 migration
- 破坏性 git、未确认的 migration、生产 deploy
- 用户未要求时的后台长驻进程

## 核心流程

1. **定义目标与 done 信号**（与 eval 一致）
2. **拆 lane**，标 parallel / sequential / gated
3. **只读 lane 一起跑**（Grep、Read、git status、SemanticSearch）
4. **写 lane 隔离**（文件、目录、worktree、分支、仓）
5. **合并前验证** lane 兼容（build、冲突检查）
6. **输出验证表**，禁止空泛「已加速」

## Lane Matrix（规划时填写）

```text
Lane | 并行? | 写表面 | 风险 | 验证
仓库扫描 | yes | 无 | low | rg / git status
读 API 文档 + 读前端 api 层 | yes | 无 | low | 路径存在
migration | seq | backend/sql | high | Flyway + 启动
后端 service | gated | backend/** | med | mvn test
前端 types+api | gated | frontend/api | med | 契约 mock 或 API 已就绪
前端 UI | seq | frontend/pages | med | npm build
java-reviewer + react-reviewer | yes | 无 | low | 审查报告
```

**gated**：依赖上游 lane PASS 后才能开始。

## 全栈常见拓扑

### 探索阶段（推荐并行）

```
[explore backend] + [explore frontend] + [读 design 文档]  → 汇总 → plan-workflow
```

### 实现阶段（默认串行）

```
migration → backend → 前端 types/api → UI
```

### 契约已锁定时可并行

```
[@backend-dev 实现 API]  ||  [@frontend-dev types+api+UI with mock]
→ API 就绪后前端切真实 client → 联调
```

条件：API path/DTO 已在 `{API_DESIGN_DOC}`；migration 不阻塞 mock；**禁止**两 lane 改同一 DTO/契约文件。

### 构建失败双栈

`build-fix`：**先后端再前端**（前端常依赖后端 DTO 形状）。仅当错误明确隔离在一侧时可只跑一侧。

## 执行规则

- 批量只读工具调用（同一轮多条 Read/Grep）
- 大改无关功能 → 考虑 worktree / 分支隔离
- lane 发现 blocker → 暂停依赖 lane，更新 Matrix
- 合并后：`code-review-gate` → `verification-gate`

## 输出模板

```markdown
## 并行执行结果
- Lane 数：N
- 完成：M / 阻塞：…
- 快路径：…
- 验证：lint / build / 冒烟 → PASS/FAIL
```

## 与 workflow-triggers 关系

| 之前 | 之后 |
|------|------|
| `plan-workflow`（大任务） | 可选先本 Skill 画 Matrix |
| `implement-feature` | 按 Matrix 执行 lane |
| 交付 | `verification-gate` |

## 反模式

- 并行写同一文件
- 用并行跳过 scope-check 或 eval
- 未 poll 后台 build/test 就声称完成
- 在「已加速」摘要里隐藏失败 lane

## 详版

用户机全局：`~/.cursor/skills/parallel-execution-optimizer/SKILL.md`（英文全量）。
