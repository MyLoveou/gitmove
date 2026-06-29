# .cursor 目录结构（Cursor 官方 vs 扩展）

> 本仓库**仅**维护 `.cursor/` 运行时包；Bootstrap 模板在仓库根 `templates/`。

---

## Cursor 自动加载

| 路径 | 说明 |
|------|------|
| `.cursor/rules/*.mdc` | `description` + `globs` 或 `alwaysApply` |
| `.cursor/skills/*/SKILL.md` | Skills |
| `.cursor/agents/*.md` | 子代理 |
| `.cursor/hooks/hooks.json` | Hooks |
| `AGENTS.md` | 项目根（Bootstrap 生成） |

栈 Rule 须用 `globs:`，勿用 ECC 旧字段 `paths:`。修复：`scripts/fix-cursor-rule-frontmatter.ps1`。

---

## 扩展（Skill 引用，非 Settings 自动项）

| 路径 | 用途 |
|------|------|
| `.cursor/workflows/` | 需求/设计/开发/交付剧本 |
| `.cursor/evals/` | EDD eval 示例 |
| `.cursor/constraints.md.template` | → 复制为 `constraints.md` |

---

## 业务项目复制后

```
YourApp/.cursor/
├── rules/ skills/ agents/ hooks/ workflows/
└── constraints.md
```

仅新增 **一个** `.cursor/`，无额外规范目录。
