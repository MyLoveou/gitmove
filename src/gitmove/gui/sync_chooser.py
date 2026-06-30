"""GUI choosers for batch sync (main thread only — no stdin)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from gitmove.registry import ProjectEntry
from gitmove.sync import SyncCheckReport, SyncDrift, SyncStrategy


def gui_project_chooser(parent, entry: ProjectEntry, report: SyncCheckReport) -> bool:
    count = len(report.attention_items)
    return messagebox.askyesno(
        "批量 sync",
        f"项目: {entry.alias}\n{count} 个 skip 路径需关注。\n\n是否处理此项目？",
        parent=parent,
    )


def _ask_local_modified_strategy(parent, drift: SyncDrift) -> SyncStrategy | None:
    result: list[SyncStrategy | None] = [SyncStrategy.SKIP]

    dlg = tk.Toplevel(parent)
    dlg.title("skip 文件")
    dlg.transient(parent)
    dlg.grab_set()
    local = "是" if drift.local_modified else "否"
    remote = "是" if drift.remote_modified else "否"
    tk.Label(
        dlg,
        text=f"{drift.path}\n本地已改: {local}  远程有更新: {remote}",
        justify=tk.LEFT,
    ).pack(padx=12, pady=8)

    def pick(strategy: SyncStrategy | None) -> None:
        result[0] = strategy
        dlg.destroy()

    frame = tk.Frame(dlg)
    frame.pack(padx=12, pady=(0, 12))
    tk.Button(frame, text="保留本地", command=lambda: pick(SyncStrategy.LOCAL)).pack(
        side=tk.LEFT, padx=4
    )
    tk.Button(frame, text="采用远程", command=lambda: pick(SyncStrategy.REMOTE)).pack(
        side=tk.LEFT, padx=4
    )
    tk.Button(frame, text="合并", command=lambda: pick(SyncStrategy.MERGE)).pack(
        side=tk.LEFT, padx=4
    )
    tk.Button(frame, text="跳过", command=lambda: pick(SyncStrategy.SKIP)).pack(side=tk.LEFT, padx=4)
    dlg.protocol("WM_DELETE_WINDOW", lambda: pick(SyncStrategy.SKIP))
    parent.wait_window(dlg)
    return result[0]


def gui_file_chooser(parent, drift: SyncDrift) -> SyncStrategy | None:
    if drift.local_modified:
        return _ask_local_modified_strategy(parent, drift)
    remote = "是" if drift.remote_modified else "否"
    choice = messagebox.askyesno(
        "skip 文件",
        f"{drift.path}\n远程有更新: {remote}\n\n采用远程？（否 = 跳过）",
        parent=parent,
    )
    return SyncStrategy.REMOTE if choice else SyncStrategy.SKIP
