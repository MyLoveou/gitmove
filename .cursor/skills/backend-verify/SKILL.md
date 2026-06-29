---
name: backend-verify
description: >-
  改 backend 后深验：compile、test、migration、重启与冒烟。触发：后端验证、mvnw test、Flyway、端口冒烟。
origin: ECC springboot-verification（通用版）
---

# 后端验证工作流（Backend Verify）

> 改 `{BACKEND_DIR}/**` 交付前与 `verification-gate` 串联。

## 阶段

### 1. Compile

```powershell
{BACKEND_BUILD_CMD}
```

FAIL → `build-fix`，STOP。

### 2. Test（建议：改 Service/Repository 时）

```powershell
{BACKEND_TEST_CMD}
```

### 3. Migration

重启后日志：`Successfully applied` / `Schema is up to date`；无 `Migration failed`。

### 4. 重启

```powershell
{BACKEND_RUN_CMD}
```

### 5. HTTP 冒烟

- Token：见 `{DEV_ACCOUNTS_DOC}`
- 改动端点 GET/PUT 至少一次
- compile 过但 403 → `local-dev`（旧进程）

## 输出

```markdown
后端验证
- compile: PASS/FAIL
- test: PASS/FAIL/SKIP
- migration: PASS/FAIL
- 重启: PASS/FAIL
- 冒烟: PASS/FAIL
```

仅改 frontend 可跳过本 Skill。
