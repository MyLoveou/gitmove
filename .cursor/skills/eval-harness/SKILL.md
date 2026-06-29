---
name: eval-harness
description: Eval-Driven Development。新功能或大改前定义 pass/fail，与 verification-gate 配合。
origin: ECC eval-harness（通用版）
---

# Eval Harness

> Eval = AI 辅助开发的「单元测试」：先定义成功标准，再实现，再回归。

## 何时激活

- 新功能、大改 API、新 migration
- `requirements-refinement` **已定稿**后，从需求 §4 验收标准生成 eval
- 需要可重复 pass/fail 证据
- 与 `dynamic-workflow-mode` 配合的多会话任务

## 存储

```
.cursor/evals/
  <feature>.md      # 提交 Git
  <feature>.log     # 可选，一般不提交
```

## Eval 类型

### Capability Eval

```markdown
[CAPABILITY EVAL: feature-name]
Task: …
Success Criteria:
  - [ ] scope-check 通过
  - [ ] API 文档已更新（若改 API）
  - [ ] {BACKEND_BUILD_CMD} PASS
  - [ ] {FRONTEND_BUILD_CMD} PASS
  - [ ] 若改 backend：重启+冒烟 PASS
```

### Regression Eval

```markdown
[REGRESSION EVAL: auth-chain]
Tests:
  - login: PASS/FAIL
  - forbidden-non-member: PASS/FAIL
Result: X/Y
```

## Grader 类型

1. **Code** — compile + build（优先）
2. **Rule** — grep 契约与文档一致
3. **Smoke** — HTTP 2xx
4. **Human** — Security / 产品高风险

## 工作流

Define → Implement → Evaluate → Report → `verification-gate`

## 与 verification-gate

| eval-harness | verification-gate |
|--------------|-------------------|
| 功能级标准（写在前） | 交付级通用 DoD（写在后） |

## 反模式

- 只有 happy path
- eval 太慢从不跑
- 用 eval 绕过 scope-check
- 禁止臆造 PASS

## 模板

见 `.cursor/evals/_example-feature.md`
