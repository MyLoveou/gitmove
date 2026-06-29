---
name: verification-gate
description: >-
  交付前验证门禁。触发：验收、DoD、交付、提 PR、完成、build 通过后声称结束、stop hook。
origin: ECC verification-loop（通用版）
---

# 验证门禁（Verification Gate）

> 权威 DoD：`.cursor/constraints.md` · 本 Skill 正文

## 何时使用

- 功能或显著改动完成后
- 用户要求「验收」「DoD」「交付前检查」
- 创建 PR 前
- 改 backend 或 API 契约后

## 阶段 0：范围合规

读 `scope-check` Skill（新功能 / 大改 API 时）。

## 阶段 1：前端构建

```powershell
{FRONTEND_BUILD_CMD}
```

失败 → **STOP**。

## 阶段 2：后端构建

```powershell
{BACKEND_BUILD_CMD}
```

可选：`{BACKEND_TEST_CMD}`。失败 → **STOP**。

## 阶段 3：后端重启（若改了 backend/**）

1. 停旧进程（端口 `{BACKEND_PORT}`）
2. `{BACKEND_RUN_CMD}`
3. migration 日志无失败
4. HTTP 冒烟改动接口（见 `{DEV_ACCOUNTS_DOC}`）

仅改 frontend/docs → 跳过。

## 阶段 4：契约与文档

若改 API/实体：更新 `{API_DESIGN_DOC}`、`{DATA_MODEL_DOC}`。

## 阶段 5：仓库卫生

- [ ] 未提交密钥、`.env`、本地库
- [ ] 用户未要求时不 commit/push

## 输出格式

```markdown
验证门禁 · {PROJECT}
- 范围：通过 / 需说明
- frontend build：通过 / 失败
- backend compile/test：通过 / 跳过
- 后端重启+冒烟：通过 / 跳过 / 未执行
- 文档同步：是 / 否 / N/A
- 结论：可交付 / 阻塞：…
```

**禁止臆造通过**。
