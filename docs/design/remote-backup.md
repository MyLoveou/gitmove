# 远程备份：候选方案与未决问题

> 状态：**未决策**（2026-11-08 记录）。当前资产平面只有本地双盘备份；异地备份方案待后续权衡。
> 本文只记录问题与取舍，不代表已承诺实现。

## 1. 现状

- 资产由 restic 管理：每个 `[[backup.target]]` 是一个独立仓库，独立快照、独立保留策略。
- 已支持本地磁盘目标；`repo` 字符串对 restic 而言是通用的，因此 `s3:` / `sftp:` / `rest:` / `rclone:` 理论上都可直接配置。
- `asset test` 可验证目标可达；`asset backup` 多目标时单盘失败不影响其他（退出码 2）。
- **尚未**用真实远程端点做过验收；`asset copy`、`--limit-upload`、快照年龄告警、调度均未实现。

## 2. 候选方案

| 方案 | 服务端 | 速度 | 防篡改 | 成本 | 运维 |
|---|---|---|---|---|---|
| 对象存储直连（Backblaze B2 / Cloudflare R2 / S3） | 云服务 | 快 | 版本控制 / 对象锁（需配置） | 按量，B2 约 $6/TB/月 | 无 |
| 自建对象存储（MinIO / Garage / SeaweedFS） | 自己的服务器/NAS | 快 | 版本控制 / 对象锁 | 机器 + 磁盘 | 中 |
| rest-server（REST 后端） | 自己的 VPS/NAS | 快 | `--append-only` 一行参数 | 机器 | 低 |
| sftp（任意 SSH 主机） | 只需 sshd | 中（单连接） | 靠权限 | 机器 | 低 |
| rclone + 网盘（OneDrive / Google Drive / 坚果云 WebDAV） | 网盘服务 | 中 | ❌ 无 | 网盘会员 | 低 |
| 网盘客户端同步 restic 仓库目录 | 网盘服务 | 视客户端 | ❌ | 会员 | 极低，但**不推荐** |

## 3. 未决问题（后续思考）

1. **默认推荐哪个？** 目前倾向：主备份本地盘（已有）+ 异地首选对象存储直连；有服务器则 rest-server（append-only）；网盘仅作第三副本。
2. **是否需要"远程"一等公民？** 是加 `kind = "remote" | "rclone"` 并与本地区分展示，还是全部交给 restic 的 repo URL、`kind` 仅用于 UI？
3. **防勒索**：对象存储要配置版本控制/对象锁；rest-server 用 append-only；sftp 用受限用户。三者如何统一表达为 gitmove 的"保护级别"？
4. **凭据管理**：环境变量、Windows 凭据管理器、仓库外密码文件，三者如何取舍？是否引入 keyring 依赖？
5. **首次上传**：38 GB 在 10 Mbps 下约 8–9 小时，是否必须提供"种子传输"（本地盘 → 服务器/对象存储的 `restic copy`）？
6. **rclone 与网盘**：是否值得支持 `rclone:`？个人网盘 API 不稳定且可能违反 ToS，是否只支持 WebDAV（坚果云/群晖）？
7. **调度**：`schedule install/list/uninstall`（Windows 任务计划）与备份策略如何组合（每日本地、每周异地、每月 check）？
8. **告警**：快照年龄、目标不可达、check 失败是否进入 `doctor` 并给出修复建议？
9. **恢复演练**：是否需要 `asset restore --verify`（恢复后校验哈希）？
10. **成本可见性**：是否展示每个目标的存储量/最近备份时间，帮助判断配额？

## 4. 若实现，落地清单

| 优先级 | 项 | 说明 |
|---|---|---|
| P0 | 真实端点验收 | 本地 WebDAV（`rclone serve webdav`）或 MinIO 跑通 init/backup/check/restore |
| P0 | `asset copy <src> <dst>` | 种子迁移，复用已有快照 |
| P1 | `--limit-upload` / 重试 | 夜间限速、弱网重试 |
| P1 | `kind` 与 UI 目标类型下拉 | local / remote / rclone |
| P1 | doctor：rclone 存在性、快照年龄 | 提前告警 |
| P2 | `schedule` 命令 | 真实创建/删除计划任务并验证 |
| P2 | 文档示例 | B2 / R2 / MinIO / rest-server / 坚果云 WebDAV |

## 5. 参考命令（已验证/待验证）

```bash
# 本地 WebDAV 模拟（无需真实网盘）
rclone serve webdav C:\tmp\webdav-store --addr 127.0.0.1:8088

# rest-server（服务器）
rest-server --path /srv/gitmove --append-only --listen :8000

# 目标配置（任选）
# repo = "rest:https://backup.example.com/video/"
# repo = "sftp:backup@nas:/srv/gitmove/video"
# repo = "s3:https://<account>.r2.cloudflarestorage.com/gitmove-video"
# repo = "rclone:webdav-local:gitmove/video"
```
