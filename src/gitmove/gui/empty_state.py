"""Empty state copy for GUI tabs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmptyStateCopy:
    title: str
    body: str
    not_for: str


EMPTY_STATES: dict[str, EmptyStateCopy] = {
    "Skip-worktree": EmptyStateCopy(
        title="尚未配置 Skip-worktree",
        body="适用：已被 Git 追踪、仅希望本地修改且不提交的文件（如 appsettings.Development.json）。",
        not_for="未追踪目录请使用「外部链接」；整目录来自上游 Git 仓请使用「Vendor」。",
    ),
    "外部链接": EmptyStateCopy(
        title="尚未配置外部链接",
        body="适用：未追踪目录/文件，内容放在仓库外并通过 junction/symlink 挂载。",
        not_for="已被 Git 追踪的文件请用 Skip；来自其他 Git 仓库请用 Vendor。",
    ),
    "Vendor": EmptyStateCopy(
        title="尚未配置 Vendor",
        body="适用：目录内容来自另一个 Git 仓库（如 .cursor 规范仓），可 vendor sync 更新。",
        not_for="仅本地盘外目录、无上游 Git 时用「外部链接」。",
    ),
    "Profile": EmptyStateCopy(
        title="尚未保存 Profile",
        body="适用：在同一仓库切换公司/个人策略（如 company ↔ personal .cursor Vendor）。",
        not_for="单次操作无需 Profile；请先用 CLI 或本页保存当前配置为 profile。",
    ),
    "Worktree": EmptyStateCopy(
        title="尚未注册 Worktree",
        body="适用：同一仓库在另一路径/分支并行开发。",
        not_for="目录来自其他 Git 仓请用 Vendor。",
    ),
    "同步": EmptyStateCopy(
        title="Skip 文件同步",
        body="当业务仓 remote 也修改了 skip-worktree 文件时，在此检查并 reconcile。",
        not_for="更新 Vendor 上游请用 Vendor Tab 的 Sync；业务仓 pull 请用 Git 后再 sync pull。",
    ),
}


def get_empty_state(tab_name: str) -> EmptyStateCopy | None:
    return EMPTY_STATES.get(tab_name)
