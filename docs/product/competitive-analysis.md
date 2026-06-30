# gitmove 竞品对比分析

> 调研日期：2026-06。基于公开资料与 gitmove 已定稿能力（含规划中 0.3 多项目、0.4 Vendor）整理。

## 结论摘要

**目前没有单一产品与 gitmove 目标完全重合。** 市面方案多为某一能力子集，或解决相邻问题（dotfiles 多仓、AI worktree 工作站、overlay 配置包）。gitmove 的差异化在于：**不改 `.gitignore`、配置在 `.git/`、skip + link + worktree + sync 一体化**，并规划 **Vendor（外仓整仓 link + 已追踪路径 skip）** 与 **多业务仓编排**。

---

## 1. 竞品地图（按问题域）

```
                    不改 .gitignore
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
 单仓库本地策略      多仓库编排           从外仓取内容
    │                    │                    │
 skip/link/wt      vcsh+mr / dew        submodule / shimmer
 gitmove ★         projects(规划)        repoverlay / vendor(规划)
    │                    │                    │
 Git 原生+别名      worktree GUI 群        gitnook
 Tower/Sourcetree
```

---

## 2. 总览对比表

| 产品/方案 | 类型 | skip 已追踪文件 | 盘外 link | worktree | 外仓整仓取用 | 多项目 | 配置位置 | GUI | 与 gitmove 关系 |
|-----------|------|-----------------|-----------|----------|--------------|--------|----------|-----|-----------------|
| **gitmove** | 专用 CLI+GUI | ✅ | ✅ | ✅ | 规划 Vendor | 规划 | `.git/gitmove.toml` | ✅ | — |
| **Git 原生**（skip-worktree + exclude） | 内置 | ✅ 手动 | ❌ | ✅ 手动 | submodule/subtree | ❌ | 无统一配置 | 弱 | 能力子集 |
| **repoverlay** | CLI overlay | ❌（用 exclude） | ✅ symlink | ❌ | ✅ overlay 包 | ❌ | 自有配置 | ❌ | **Vendor+link 邻近** |
| **shimmer** | CLI overlay | ❌ | ✅ symlink | ❌ | ✅ 独立 overlay 仓 | ❌ | `~/.shimmer/` | ❌ | Vendor 邻近 |
| **gitnook** | CLI 本地仓 | ❌（独立隐藏 Git） | ❌ | ❌ | ❌ | ❌ | `.gitnook/` | ❌ | 私有版本化，非 skip |
| **dew** | 本地上下文/密钥 | ❌ | ❌ | ❌ | ❌ 加密镜像 | 单仓 | `.dew/` + `~/.dew/` | ❌ | 偏密钥与本地文件清单 |
| **vcsh + myrepos** | dotfiles 多仓 | ❌ | 概念类似 | ❌ | 多 Git 仓 | ✅ `$HOME` | `~/.config/vcsh` | ❌ | **场景不同**（家目录） |
| **Grove / Worktree Manager 等** | worktree GUI | ❌ | 智能 symlink* | ✅ 强 | ❌ | 部分多仓 | 各自配置 | ✅ 强 | **只做 worktree** |
| **Tower / SourceTree** | 通用 Git GUI | 弱† | ❌ | 部分 | ❌ | ❌ | 无 | ✅ | 通用客户端 |
| **git submodule / subtree** | Git 内置 | ❌ | ❌ | ❌ | ✅ 进业务仓历史 | ❌ | `.gitmodules` | 各 GUI | **团队可见**，违背 gitmove 原则 |

\* Worktree Manager 等会对 `node_modules` 等做 worktree 间 symlink，不是「个人目录出仓」。

† Tower 主推 `assume-unchanged`（不稳定）；SourceTree 需自定义 Action 才支持 skip-worktree。

---

## 3. 能力逐项对比

### 3.1 已追踪文件的本地冻结（skip-worktree）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **gitmove** | 配置持久化 + `apply` + `doctor` + `sync pull` 交互 | 可恢复、可巡检、远程冲突有流程 | 需安装工具 |
| **Git 命令/别名** | `update-index --skip-worktree` | 零依赖 | 易丢、无 doctor、pull 要自己处理 |
| **Tower** | `assume-unchanged` | GUI 一点 | 非 skip，易被 reset 清掉 |
| **SourceTree** | 自定义 Action 调 git | 有 GUI 入口 | 非一等能力，无配置持久化 |
| **repoverlay / shimmer** | 用 `.git/info/exclude` 管**未追踪** overlay | 不改已追踪策略 | **解决不了已追踪 config** |

**结论**：专门把 skip-worktree 做成「可运维」产品的很少，gitmove 在这一点较突出；通用 GUI 普遍薄弱。

### 3.2 目录放到仓库外（link）

| 方案 | 做法 | 与 gitmove 差异 |
|------|------|-----------------|
| **gitmove link** | junction/symlink + `external_base` | 配置在 `.git/`，`doctor` 校验 |
| **repoverlay** | symlink/copy + **自动写 exclude** | 不写入 `.git/gitmove.toml` 式统一模型；偏 Copilot/Claude 插件 overlay |
| **shimmer** | 独立 overlay 仓 + symlink | 偏团队共享 dotfile/配置 overlay，不是 per-repo `.git` 配置 |
| **手动 junction** | 自己 mklink | 无 apply/doctor |

**结论**：link 层 repoverlay/shimmer 最接近，但 gitmove 强调 **与 skip/worktree 同一套配置与巡检**，且配置在 `.git/` 内。

### 3.3 从其他 Git 仓库取内容（Vendor 场景）

| 方案 | 做法 | 是否改 .gitignore | 已追踪路径（如 `.cursor`） |
|------|------|-------------------|---------------------------|
| **gitmove Vendor（规划）** | cache clone + 整仓 link + 批量 skip | 否 | **支持挂原路径** |
| **git submodule** | 提交子模块指针 | 常配合 ignore 规则 | 团队都看到子模块 |
| **git subtree** | 合并进历史 | 否但历史污染 | 内容进业务仓 |
| **shimmer** | overlay 仓 symlink 进项目 | 否 | 冲突时 stash，非 skip 模型 |
| **repoverlay** | overlay 定义 + apply | 用 exclude | 未强调已追踪目录 |
| **手动 clone + mklink** | 自己维护 | 否 | 全手动 |

**结论**：Vendor 规划在「**外仓 + 不改 ignore + 已追踪挂载点**」组合上较独特；submodule/subtree 偏团队协作，shimmer/repoverlay 偏 overlay/未追踪或另套模型。

### 3.4 多项目管理

| 方案 | 做法 | 场景 |
|------|------|------|
| **gitmove projects（规划）** | `~/.gitmove/projects.toml` + 批量 doctor/sync | **多个业务 Git 仓库** |
| **myrepos (mr)** | `mr update` 拉多仓 | 主要是 **$HOME dotfiles** 多仓 |
| **Worktree Manager** | Workspace 多 repo + 多 worktree | 并行分支/AI，不是 skip 策略 |
| **Canopy / Grove 等** | 多 worktree 工作站 | AI 并行开发 |

**结论**：「多业务项目 + 每仓 gitmove 策略」的专用工具少见；mr 是 dotfiles 领域，worktree 工具是另一赛道。

### 3.5 Worktree

| 方案 | 定位 |
|------|------|
| **gitmove** | 个人 worktree 登记 + apply，偏轻量 |
| **Grove / Worktree Manager / Canopy / Swarm** | 重度 worktree 生命周期、终端、AI Agent、hooks |
| **Cursor / Windsurf 内置** | IDE 内建 worktree |

**结论**：gitmove **不适合**和 Grove 等比「AI 并行工作站」；gitmove 的 worktree 是本地策略一环，不是主战场。

---

## 4. 邻近产品简评

### repoverlay

- **仓库**：[tylerbutler/repoverlay](https://github.com/tylerbutler/repoverlay)
- **像什么**：overlay 包 + symlink + `.git/info/exclude` + marketplace 插件（Copilot/Claude）
- **强项**：脚本化、switch overlay、与 AI 工具链集成
- **弱于 gitmove**：无 skip-worktree 体系、无 `doctor`/业务仓 `sync pull`、配置模型不同

### shimmer

- **仓库**：[sammcvicker/shimmer](https://github.com/sammcvicker/shimmer)
- **像什么**：独立 Git overlay 仓 + `shimmer link` symlink
- **强项**：团队用分支/PR 协作 overlay 配置
- **弱于 gitmove**：不解决已追踪文件；多项目指 overlay 仓而非多业务仓策略

### gitnook

- **仓库**：[deadsoftie/gitnook](https://github.com/deadsoftie/gitnook)
- **像什么**：业务仓内嵌**隐藏本地 Git**，私有版本化
- **强项**：`.cursor` 等可本地 commit 历史且不 push
- **弱于 gitmove**：不是 skip/link；多一套 `.gitnook/` 语义

### dew

- **仓库**：[vedanta/dew](https://github.com/vedanta/dew)
- **像什么**：允许列表内的本地文件加密打包、可同步镜像
- **强项**：`.env.local`、证书、docker override
- **弱于 gitmove**：不管 skip/link/worktree；偏密钥与 hydrate

### Worktree 工具群（Grove、Worktree Manager、Canopy 等）

- **像什么**：2025–2026 AI 编码下的 worktree 仪表盘
- **强项**：并行 Agent、终端、多分支
- **与 gitmove**：互补而非替代；可共存（gitmove 管策略，Grove 管 worktree 体验）

### vcsh + myrepos

- **像什么**：家目录 dotfiles 用多个 Git 仓管理，`mr` 批量更新
- **与 gitmove**：多仓编排概念相近，但场景是 `$HOME` 配置，不是业务仓库本地策略

---

## 5. gitmove 定位（差异化）

```
gitmove = 「不改 .gitignore 的 per-repo 本地 Git 策略套件」

  skip-worktree  ─┐
  external link  ─┼─ 统一 .git/gitmove.toml + doctor + apply
  worktree       ─┤
  config import  ─┤
  sync pull      ─┘
  vendor (规划)  ─── 外仓整仓 link + 已追踪路径 skip
  projects (规划) ─── 多业务仓编排
```

**独特组合**（市面少见打包在一起）：

1. 配置只在 `.git/`，团队无感知
2. skip + link + worktree **同一 doctor**
3. skip 与**业务仓远程**的 `sync pull` 交互流程
4. 规划中的 **Vendor**（外仓 + 整仓 link + 已追踪路径）
5. 轻量跨平台 GUI（非 AI worktree 工作站）

**短板**（相对竞品）：

| 维度 | gitmove | 更强竞品 |
|------|---------|----------|
| Worktree 体验 | 基础 | Grove、Worktree Manager |
| Overlay 团队协作 | 无 | shimmer、repoverlay |
| 本地文件加密同步 | 无 | dew |
| 私有文件版本历史 | 无 | gitnook |
| 品牌/生态 | 新项目 | Tower、SourceTree、Git 内置 |
| AI Agent 集成 | 无 | Canopy、Conductor、repoctx |

---

## 6. 场景选型建议

| 你的需求 | 更合适的方案 |
|----------|--------------|
| 已追踪 `config.local.json` 本地改不提交 | **gitmove skip** 或 Git skip-worktree |
| 个人目录出仓、自己管文件 | **gitmove link** |
| 从 **cursor-project-spec** 整仓挂到 `.cursor` 且已追踪 | **gitmove Vendor（规划）**；次选 shimmer/repoverlay + 手动 skip |
| 团队也要用同一套规范 | **submodule** 或 shimmer 团队 overlay 仓 |
| 多机同步本地密钥/.env | **dew** |
| `.cursor` 私人改版要有 commit 历史 | **gitnook** |
| 10 个业务仓批量 doctor/sync | **gitmove projects（规划）** |
| 5 个 Agent 并行改不同分支 | **Grove / Worktree Manager**，不是 gitmove |
| 家目录 dotfiles 多仓 | **vcsh + myrepos** |

---

## 7. 对产品路线的启示

1. **Vendor** 与 repoverlay/shimmer 的差异要在文档与对外叙事中写清：已追踪路径 + skip + `vendor sync` FF-only，不是 exclude overlay。
2. **不要**和 Canopy/Grove 卷 AI worktree 工作站；保持「策略层工具」定位。
3. **可考虑**与 repoverlay 类似的「模板/marketplace」在 0.5+（如 `cursor-spec` 一键 vendor，见 [roadmap](roadmap.md)）。
4. **多项目**与 mr 区分叙事：mr = `$HOME` dotfiles；gitmove = 业务仓库 + `.git/gitmove.toml`。

---

## 8. 参考链接

| 产品 | 链接 |
|------|------|
| repoverlay | https://github.com/tylerbutler/repoverlay |
| shimmer | https://github.com/sammcvicker/shimmer |
| gitnook | https://github.com/deadsoftie/gitnook |
| dew | https://github.com/vedanta/dew |
| vcsh | https://github.com/RichiH/vcsh |
| myrepos | https://myrepos.branchable.com/ |
| Git skip-worktree | https://git-scm.com/docs/git-update-index#Documentation/git-update-index.txt---skip-worktree |
