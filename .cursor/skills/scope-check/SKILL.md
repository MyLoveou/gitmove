---
name: scope-check
description: >-
  新功能、大改 API、易越界能力前核对 capability 与路线图。
---

# 范围核对（Scope Check）

> 实现前**必读**；输出 IN SCOPE / OUT OF SCOPE / PLACEHOLDER。

## 何时读

- 新功能、新 API
- 用户描述可能超出当前版本
- `plan-workflow`、`implement-feature` 之前
- `scope-check` 为 IN SCOPE 后 → **下一必经** `requirements-refinement`（新能力）

## 检查清单

1. 读 `{CAPABILITY_DOC}` — 能力 IN / OUT / CONSTRAINTS
2. 读 `{ROADMAP_DOC}` — 当前 Phase 是否包含
3. 读 `{BLOCKERS_DOC}`（若有）— OPEN 项是否阻塞
4. 对照 `{API_DESIGN_DOC}` — 是否已有契约或需 ADR

## 输出格式

```markdown
## Scope Check · <功能>
- 结论：IN SCOPE / OUT OF SCOPE / PLACEHOLDER
- Phase/版本：…
- 若 OUT OF SCOPE：建议占位文案 / 不实现
- 若 IN SCOPE：依赖文档章节 …
```

OUT OF SCOPE → **不编码**，向用户说明边界。

IN SCOPE（新能力）→ 进入 `requirements-refinement`，**不要**直接进入 `implement-feature`。

PLACEHOLDER → UI/API 返回 501 或明确占位，禁止静默失败。

## 项目定制

复制本 Skill 到目标项目 `.cursor/skills/scope-check/`，在 `{CAPABILITY_DOC}` 填写能力边界；若项目内改用其他 Skill 名，须同步 `workflow-triggers`。
