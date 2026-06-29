# gitmove 核心能力

**状态**：已定稿  
**版本**：0.2.0

## 目标

在不修改团队 `.gitignore` 的前提下，提供本地 Git 排除管理能力：

- skip-worktree（已追踪文件本地冻结）
- 外部目录链接（Junction / Symlink）
- 个人 worktree 管理
- CLI + 跨平台 GUI

## 不交付

- 修改远程 `.gitignore`
- 替代 Git 本身（仍依赖系统 `git` 命令）
- 团队配置同步（配置仅本地 `.git/gitmove.toml`）

## 验收标准

- [x] 配置写入 `.git/gitmove.toml`
- [x] 路径必须限制在仓库内（防目录穿越）
- [x] CLI 与 GUI 共用 `doctor.py` 等业务模块
- [x] Windows 默认 junction，Unix 默认 symlink
- [x] GUI 长操作不阻塞主线程
- [x] 单元测试覆盖率 ≥ 80%（核心模块）
- [x] `gitmove doctor` 可检测配置与状态不一致

## 验证

```bash
pip install -e ".[dev]"
pytest --cov=gitmove --cov-report=term-missing
gitmove doctor
```
