# 工作约定（gitmove v2）

## 1. 阶段

- 当前 **M0**：只写文档（需求/架构/ADR），不写实现代码。

## 2. 文档纪律

- 需求变更：先改 [产品需求](docs/requirements/product-requirements.md)，标注版本与日期，再动代码。
- 架构变更：新增 ADR，不直接改写旧条目。
- 验收：每条 FR 必须有可判定的验收项（Given/When/Then 或基准数字）。

## 3. 技术约束

| 约束 | 内容 |
|---|---|
| 前端 | Electron + Vue 3 + Vite + Pinia；渲染层禁用 node 集成，仅走 contextBridge |
| 核心 | Rust；`core` crate 不依赖 cli/daemon/mcp |
| git | 写操作与语义敏感读操作调 `git` CLI；`gix` 仅只读加速 |
| 资产 | restic CLI 编排，不捆绑、不自研去重/加密 |
| Revision | SQLite 索引 + git trailer 双写（ADR-0005） |
| 索引 | 可删除重建；git/restic 是事实源 |

## 4. 不做

- 自研 git（对象库/历史/diff/merge）
- 自研存储引擎（去重/压缩/加密）
- LFS/annex 式素材入 git
- 云同步/团队后端
- 通用全盘备份
- 在 gitmove 内渲染 AI 规范（spec 职责）

## 5. 迁移

- Python 版只修 bug，不加新功能
- Rust 与 Python 的等价性用"金样测试"验证：同参数跑两边，diff JSON
- 命令名沿用 1.x；废弃项标 deprecated 一个版本
