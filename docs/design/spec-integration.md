# 规范库接入（agent-runtime-spec）

> 本项目（gitmove-v2）使用 AI 规范库作为开发规范源；本文件记录接入方式与刷新流程。

## 源仓库

- 路径：`D:/Project/agent-runtime-spec`（gitmove 项目别名 `spec`）
- 装配单：`projects/gitmove-v2/assembly.json`
- 导出工具：`.cursor/skills/project-assembly/scripts/assemble.ps1`

## 已导入

| 目录 | 内容 |
|------|------|
| `.cursor/rules/` | 29 条规则（common / typescript / vue / frontend-vue + 入口规则） |
| `.cursor/agents/` | 6 个 agent |
| `.cursor/skills/` | 24 个 skill（含 scripts 与 templates）。2026-11-07 增补界面工艺：`baseline-ui`、`better-ui`、`better-layout`、`better-typography`、`fixing-accessibility`、`fixing-motion-performance`、`improve-ui`、`component-canvas`、`create-canvas`、`oil-ui` |
| `.dsh/skills/` | 与 `.cursor/skills/` 同一份清单（DSH 只消费 skills） |

`AGENTS.md` 与 `docs/` 保留项目自有内容，装配单 `entry` 为空，不从规范库覆盖。

## 拉取后自动刷新

`gitmove sync pull` 成功后会跑工作区钩子 `post-pull`（`.gitmove/hooks.toml`）。它执行 `scripts/refresh-runtime.ps1`：用成员 `spec` 里的装配单导出到本仓，**不加 `-Force`**。内容相同则跳过，内容不同则留下并在输出里提示。

这个事件不是 Git 钩子文件。直接 `git pull` 不会刷新。规范库成员还没检出时脚本退出 0，不挡住已经完成的拉取。钩子用的是 `spec` 的当前检出，不会再去拉一遍规范库。

## 刷新（单向导出）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  D:\Project\agent-runtime-spec\.cursor\skills\project-assembly\scripts\assemble.ps1 `
  -Project gitmove-v2 -Target D:\Project\GitMove\gitmove-v2 `
  -Root D:\Project\agent-runtime-spec -DryRun
```

确认计划后去掉 `-DryRun`；默认跳过内容不同的文件，`-Force` 才覆盖。

## 注意

- 导出是单向的：本仓修改不会回写规范库。
- `.encodingignore` 豁免 `**/encoding-guard/**`，因为该 skill 的文档故意包含坏编码示例。
- `constraints.md` 占位符：本仓未导出该文件，无需处理；未启用 OpenCode。