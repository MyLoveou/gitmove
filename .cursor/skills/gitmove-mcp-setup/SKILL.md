---
name: gitmove-mcp-setup
description: >-
  配置 gitmove MCP 服务器（Cursor mcp.json、Claude Desktop、stdio）。
  触发：gitmove MCP、配置 mcp、gitmove-mcp 连不上、MCP tool 不可用。
---

# gitmove MCP 安装与调试

> 设计：`docs/design/ai-integration.md`  
> 示例配置：`examples/mcp/cursor-mcp.json`

## 前置

- Python 3.10+
- 系统 `git` 在 PATH
- gitmove 已安装且含 MCP 可选依赖（**0.6.0 实现后**）：

```bash
cd /path/to/gitmove
pip install -e ".[mcp]"
gitmove-mcp --help   # 或 --version
```

## Cursor 配置

编辑用户级 MCP 配置（路径因版本而异，常见 `~/.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "gitmove": {
      "command": "gitmove-mcp",
      "args": [],
      "env": {
        "GITMOVE_MCP_ALLOW_WRITE": "0",
        "GITMOVE_REPO": ""
      }
    }
  }
}
```

若 `gitmove-mcp` 不在 PATH，改用 venv 绝对路径：

```json
"command": "E:/path/to/venv/Scripts/gitmove-mcp.exe"
```

保存后 **重启 Cursor** 或重载 MCP。

## 环境变量

| 变量 | 说明 |
|------|------|
| `GITMOVE_MCP_ALLOW_WRITE` | `0` 只读（默认）；`1` 允许 confirm 写工具 |
| `GITMOVE_REPO` | 默认仓库路径或 projects 别名 |
| `GITMOVE_HOME` | 覆盖 `~/.gitmove/` |
| `GITMOVE_VENDOR_HOME` | 覆盖 vendor 缓存目录 |

## 验证

1. Cursor MCP 面板应显示 `gitmove` 服务器在线
2. 调用 read tool：`gitmove_doctor`（空参数时用 cwd 或 `GITMOVE_REPO`）
3. 期望 JSON：`{"ok": true, "tool": "gitmove_doctor", ...}`

## 故障排查

| 现象 | 处理 |
|------|------|
| command not found | 用 venv 绝对路径或 `pip install -e ".[mcp]"` |
| 服务器立即退出 | 终端手动跑 `gitmove-mcp` 看 stderr |
| tool 返回 `CONFIRM_REQUIRED` | 写操作需 `confirm: true` + `ALLOW_WRITE=1` |
| 非 Git 目录 | 设置 `GITMOVE_REPO` 或 `-C` 等价 env |

## 无 MCP 降级

Agent 使用 CLI + `--json`（0.6.0+）：

```bash
gitmove doctor --json
```

并阅读 Skill：`gitmove-ops`
