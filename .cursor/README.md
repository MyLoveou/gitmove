# Cursor 配置 · 可直接复制的运行时整包

> **业务项目只复制本目录**。结构说明：[STRUCTURE.md](./STRUCTURE.md)  
> Bootstrap：[BOOTSTRAP.md](../BOOTSTRAP.md) · 模板在仓库根 `templates/`（不在 `.cursor/` 内）

---

## Cursor 自动加载（官方）

| 目录 | 说明 |
|------|------|
| `rules/*.mdc` | 须含 `description` + `globs` 或 `alwaysApply` |
| `skills/*/SKILL.md` | Agent Skills |
| `agents/*.md` | 子代理 `@name` |
| `hooks/hooks.json` | Hook 配置 |

## 扩展（Skill 引用，非 Settings 自动项）

| 目录 | 说明 |
|------|------|
| `workflows/` | 四条主工作流剧本 |
| `evals/` | EDD 示例 |

---

## 维护

- 新增 Skill → `skills/workflow-triggers/SKILL.md`
- 修复 ECC Rule frontmatter → `scripts/fix-cursor-rule-frontmatter.ps1`
- 刷新 ECC → `scripts/sync-ecc-bundle.ps1`
