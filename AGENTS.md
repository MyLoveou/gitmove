# 工作约定（gitmove v2）

## 1. 阶段

- **M0 已完成**（需求/架构/ADR 已确认）。自 M1 起开始写实现代码。
- M1 范围：Electron 壳 + Vue 骨架 + 调现有 Python CLI（只读）。M1 不碰写路径。

## 2. 代码结构

```
src/main/       Electron 主进程（窗口 / IPC / sidecar）
src/preload/    contextBridge（只暴露 gitmove.invoke）
src/renderer/   Vue 3（页面 / 组件 / Pinia）
src/shared/     跨进程协议类型
```

规则：

- 渲染层禁止 `nodeIntegration`；一切能力经 preload 暴露
- 主进程不直接做业务：调用 sidecar（M1=Python CLI，M2+=Rust daemon）
- 协议类型只写在 `src/shared/`，两侧共用

## 3. 文档纪律

- 需求变更：先改 [产品需求](docs/requirements/product-requirements.md)，标注版本与日期，再动代码。
- 架构变更：新增 ADR，不直接改写旧条目。
- 验收：每条 FR 必须有可判定的验收项（Given/When/Then 或基准数字）。

## 4. 技术约束

| 约束 | 内容 |
|---|---|
| 前端 | Electron + Vue 3 + Vite + Pinia；渲染层禁用 node 集成，仅走 contextBridge |
| 核心 | Rust；`core` crate 不依赖 cli/daemon/mcp |
| git | 写操作与语义敏感读操作调 `git` CLI；`gix` 仅只读加速 |
| 资产 | restic CLI 编排，不捆绑、不自研去重/加密 |
| 工作区 | 多仓组合（Member）；Revision 必须记录每个成员 commit（ADR-0009） |
| Revision | SQLite 索引 + git trailer 双写（ADR-0005） |
| 备份 | 多目标（两块本地盘）互不阻塞；部分失败退出码 2（ADR-0011） |
| 分支 | 以 git 为准；工作区分支=成员分支映射（ADR-0012） |
| 资产合并 | 三路文件级分析；冲突必须显式解决（ADR-0013/0015） |
| 索引 | 可删除重建；git/restic 是事实源 |

## 5. 不做

- 自研 git（对象库/历史/diff/merge）
- 自研存储引擎（去重/压缩/加密）
- LFS/annex 式素材入 git
- 云同步/团队后端
- 通用全盘备份
- 在 gitmove 内渲染 AI 规范（spec 职责）

## 6. 迁移

- Python 版只修 bug，不加新功能
- Rust 与 Python 的等价性用"金样测试"验证：同参数跑两边，diff JSON
- 命令名沿用 1.x；废弃项标 deprecated 一个版本
