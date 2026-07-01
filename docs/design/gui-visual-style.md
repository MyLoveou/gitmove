# gitmove GUI 视觉风格

**状态**：Minimalism 定稿（取代 Phase 1 青绿技术风）  
**技术栈**：CustomTkinter · 随 [gui-ux.md](./gui-ux.md) 交互设计  
**设计画布**：[gitmove-minimal-ui.canvas.tsx](/C:/Users/Administrator/.cursor/projects/e-gitmove/canvases/gitmove-minimal-ui.canvas.tsx)  
**关联需求**：[gitmove-gui-ux-redesign.md](../requirements/features/gitmove-gui-ux-redesign.md)

---

## 1. 设计方向

| 维度 | 选择 |
|------|------|
| **家族** | **Minimalism** — 黑白灰、排版层级、发丝线分隔 |
| **用途** | 开发者日常工具：选型 → 配置 → 健康检查 → 修复 |
| **受众** | 熟悉 Git、需长时间扫描配置与健康状态的工程师 |
| **气质** | **安静、清晰、可思考** — 画廊式内容空间，非营销页 |
| **记忆点** | 单一强调色（近黑/近白）+ 序号场景卡片 + 内联健康计数 |
| **约束** | 跨平台 Tk、深浅色跟随系统、无额外 UI 依赖 |

**避免**：彩虹 accent、emoji 装饰、粗阴影、渐变、彩色 pill、左侧色条。

**极简 ≠ 随便删**：通过有意识地删减装饰，把视觉注意力集中在核心元素与内容上。

---

## 2. 色彩令牌

| 令牌 | 浅色 | 深色 | 用途 |
|------|------|------|------|
| `accent` | `#141414` | `#F0F0F0` | 主按钮、选中侧栏 |
| `accent_hover` | `#2A2A2A` | `#D8D8D8` | 主按钮 hover |
| `text_on_accent` | `#FFFFFF` | `#141414` | accent 底上的文字 |
| `surface` | `#FAFAFA` | `#0D0D0D` | 窗口背景 |
| `surface_elevated` | `#FFFFFF` | `#141414` | 侧栏、卡片、输入区 |
| `surface_secondary` | `#F5F5F5` | `#1A1A1A` | 次要按钮、未选中侧栏项 |
| `border` | `#E0E0E0` | `#2E2E2E` | 1px 发丝线 |
| `text_primary` | `#141414` | `#F5F5F5` | 标题、正文 |
| `text_muted` | `#6B6B6B` | `#9A9A9A` | 副标题、说明、tag |
| `error` | `#8B2E2E` | `#C47070` | doctor ERR、destructive |
| `warning` | `#7A5C12` | `#C4A84A` | WARN |
| `success` | `#2D5A3D` | `#6B9E7A` | 0 错误时可选用 |
| `info` | `#4A5568` | `#8A9AAA` | INFO |

实现：`src/gitmove/gui/theme.py` · `ThemePalette` + `resolve_theme()`.

---

## 3. 字体与间距

| 级别 | 规格 | 用途 |
|------|------|------|
| `title` | 系统 UI · 18px bold | 页面标题（开始 Tab） |
| `section` | 15px bold | Tab 内区块标题 |
| `body` | 13px regular | 正文、表格 |
| `caption` | 11px regular · muted | 平台信息、序号、tag |
| `mono` | Consolas / Courier · 12px | CLI 复制区（后续） |

间距基线 **4px**：`xs=4` · `sm=8` · `md=12` · `lg=16` · `xl=24`  
圆角：`radius_sm=4` · `radius_md=6` · `radius_lg=8`

---

## 4. 组件规范

### 4.1 场景卡片（开始 Tab）

```
01
本地改已追踪文件
不想提交…
→ Skip-worktree
```

- 3 列网格，等高；序号 caption muted；标题 body；副标题与 tag muted
- hover：边框从 `border` 变为 `text_primary`（无 accent 色条、无 emoji）
- 实现：`ScenarioCardWidget` · `gui/widgets.py`

### 4.2 健康摘要条（概览 Tab）

```
0 错误    1 警告    2 提示     [重新检查] [一键应用]
```

- 内联 typography；计数为 0 时用 `text_muted`，>0 时用对应语义色
- 无彩色 pill 背景
- 实现：`HealthSummaryBar`

### 4.3 空状态面板

- elevated 面板 + 发丝线边框；纯 typography（标题 · 说明 · 「不适用：…」muted）
- 无左侧色条
- 实现：`EmptyStatePanel`

### 4.4 侧栏与顶栏

- 侧栏：`ElevatedPanel`；选中项 `accent` 实底 + `text_on_accent`
- 未选中：secondary 底 + 1px border
- 底部状态栏：顶部分割线 + caption

### 4.5 Treeview

- 行高 28px；表头 semibold
- 问题行按级别着色：ERR / WARN / INFO（低饱和语义色）
- 背景/前景随 `surface_elevated` / `text_primary`

### 4.6 交互反馈

- 按钮 hover：边框或背景灰度变化，无缩放/阴影爆发
- 链接/可点击卡片：边框或字色微调
- 动画：少且慢（Tk 默认即可）

---

## 5. 场景 metadata

| 场景 | index | tag |
|------|-------|-----|
| S1 skip | 01 | Skip-worktree |
| S2 link | 02 | 外部链接 |
| S3 vendor | 03 | Vendor |
| S4 profile | 04 | Profile |
| S5 sync | 05 | 同步 |
| S6 worktree | 06 | Worktree |

定义于 `gui/scenarios.py` · `ScenarioCard.index` / `tag`.

---

## 6. 模块映射

| 模块 | 职责 |
|------|------|
| `gui/theme.py` | 令牌、字体工厂、`style_treeview`、`configure_tree_tags` |
| `gui/widgets.py` | ElevatedPanel、PageHeader、ScenarioCardWidget、HealthSummaryBar、EmptyStatePanel、按钮工厂 |
| `gui/scenarios.py` | 场景 metadata |
| `gui/app.py` | 组装；不内联颜色 hex |

---

## 7. 参考

- 交互线框：[gui-ux.md](./gui-ux.md) §3  
- 设计画布：[gitmove-minimal-ui.canvas.tsx](/C:/Users/Administrator/.cursor/projects/e-gitmove/canvases/gitmove-minimal-ui.canvas.tsx)  
- 错误对话框：`gui/error_dialog.py`
