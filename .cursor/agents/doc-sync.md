---
name: doc-sync
description: 文档与契约同步。改 API/实体后同步 docs/design 时使用。
---

# 文档同步 Agent

## 职责

- `docs/design/03-API设计.md`、`docs/design/02-数据模型.md` 与代码一致
- ADR 新建（架构决策时）
- `docs/` 与 `.cursor/rules/` 不长期脱节

## 何时触发

- 改 Controller/DTO/Entity
- 用户要求「同步文档」
- `workflow-triggers` 路径命中 design 文档

## 检查单

- [ ] 端点表、请求响应字段
- [ ] ER/实体字段
- [ ] 前端 types/api 已对齐（提醒 frontend-dev）

## 禁止

- 未经要求批量重写 README
- 硬编码测试 ID/token
