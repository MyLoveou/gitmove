---
name: local-dev
description: >-
  本地启动、联调、401/403、端口占用、清库。模板：复制后填写 {占位符}。
---

# 本地开发联调（模板）

> 复制到 `<项目>/.cursor/skills/local-dev/SKILL.md` 并填写项目路径、端口、账号文档。

## 何时读

- 401 / 403 / 连不上 API
- 端口占用
- 「怎么启动」「清库」
- compile 过但 API 异常（**先重启后端**）

## 启动

```powershell
# 后端
cd {BACKEND_DIR}
{BACKEND_RUN_CMD}    # 例：.\mvnw.cmd spring-boot:run

# 前端
cd {FRONTEND_DIR}
{FRONTEND_DEV_CMD}   # 例：npm run dev
```

| 服务 | 端口 |
|------|------|
| 后端 | `{BACKEND_PORT}` |
| 前端 | `{FRONTEND_PORT}` |

## 测试账号

见 `{DEV_ACCOUNTS_DOC}`。

## 常见问题

| 现象 | 处理 |
|------|------|
| PUT 403 空 body，GET 200 | 停旧 Java 进程，重启后端 |
| 401 | access token 过期；勿用 refresh 当 access |
| 清库后 ID 变 | 重新注册/seed；更新测试 worldId |
| 端口占用 | 结束占用 `{BACKEND_PORT}` 的进程 |

## 构建验证

```powershell
{BACKEND_BUILD_CMD}
{FRONTEND_BUILD_CMD}
```
