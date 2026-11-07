---
name: build-fix
description: >-
  Maven/Vite/TypeScript/Java 编译或构建失败时使用。
  触发词：构建失败、compile error、build failed、npm run build 失败、找不到符号、TS error。
origin: ECC /build-fix（通用版）
---

# 构建修复工作流（Build Fix）

> 最小 diff 修到绿，不扩 scope。

## 何时触发

- `{FRONTEND_BUILD_CMD}` / `{BACKEND_BUILD_CMD}` 失败
- 用户粘贴编译/类型错误
- Agent 自行跑构建失败后

## 流程

### 1. 定位栈

| 错误来源 | 委派 |
|----------|------|
| `{BACKEND_DIR}/**` | `@java-build-resolver` |
| `{FRONTEND_DIR}/**` | `@react-build-resolver` |
| 两者都有 | **先后端再前端** |

### 2. 常见根因

| 现象 | 处理 |
|------|------|
| compile 过但 API 403 | `local-dev` 重启后端，非 build-fix |
| DTO 与前端 types 不一致 | 对齐 types 与后端 DTO |
| migration 启动失败 | `@database-reviewer`；勿改已执行 V{n} |
| 路由参数名不一致 | 查 `constraints.md` 与 `App.tsx` |

### 3. 修复原则

- **最小 diff**；不顺手重构
- 不引入 capability 外依赖
- 修完**重跑**失败命令直到 PASS

### 4. 退出

```markdown
构建修复 · 结果
- 命令：…
- 状态：PASS / FAIL
- 改动文件：…
```

FAIL 时不得声称可交付。

### 5. 后续

若还改了业务代码 → `code-review-gate` → `verification-gate`
