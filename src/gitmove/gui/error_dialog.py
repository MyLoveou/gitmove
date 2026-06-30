"""GitMove error dialog with remediation actions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from gitmove.errors import GitMoveError, RemediationStep


class ErrorDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: tk.Misc,
        err: GitMoveError,
        *,
        on_action: Callable[[str, GitMoveError], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("gitmove 错误")
        self.geometry("520x420")
        self.minsize(480, 320)
        self.grab_set()
        self.focus_force()

        ctk.CTkLabel(
            self,
            text=f"✗ {err.message}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e74c3c",
            wraplength=480,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        if err.cause:
            ctk.CTkLabel(self, text="原因", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16)
            ctk.CTkLabel(self, text=err.cause, wraplength=480, justify="left").pack(
                anchor="w", padx=16, pady=(0, 8)
            )

        if err.steps:
            ctk.CTkLabel(self, text="建议操作", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16)
            steps_box = ctk.CTkTextbox(self, height=140, wrap="word")
            steps_box.pack(fill="both", expand=True, padx=16, pady=4)
            for index, step in enumerate(err.steps, start=1):
                steps_box.insert("end", f"{index}. {step.title}\n")
                if step.detail:
                    steps_box.insert("end", f"   {step.detail}\n")
                if step.command:
                    steps_box.insert("end", f"   {step.command}\n")
            steps_box.configure(state="disabled")

        self._detail_visible = False
        self._detail_box = ctk.CTkTextbox(self, height=80, wrap="word")
        detail_text = f"code: {err.code}\n{err.context}\n"
        self._detail_box.insert("end", detail_text)
        self._detail_box.configure(state="disabled")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)

        primary = _primary_action(err.steps)
        if primary and on_action:
            ctk.CTkButton(
                btn_row,
                text=_action_label(primary),
                command=lambda: self._run_action(primary, err, on_action),
            ).pack(side="left", padx=(0, 8))

        if err.steps and err.steps[0].command:
            ctk.CTkButton(
                btn_row,
                text="复制命令",
                command=lambda: self._copy_command(err.steps[0].command or ""),
            ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_row, text="关闭", command=self.destroy).pack(side="right")

        toggle_row = ctk.CTkFrame(self, fg_color="transparent")
        toggle_row.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(
            toggle_row,
            text="▼ 技术详情",
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            command=self._toggle_detail,
        ).pack(anchor="w")

    def _toggle_detail(self) -> None:
        if self._detail_visible:
            self._detail_box.pack_forget()
        else:
            self._detail_box.pack(fill="x", padx=16, pady=(0, 8))
        self._detail_visible = not self._detail_visible

    def _copy_command(self, command: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(command)
        messagebox.showinfo("已复制", command, parent=self)

    def _run_action(self, action: str, err: GitMoveError, on_action: Callable[[str, GitMoveError], None]) -> None:
        on_action(action, err)
        self.destroy()


def _primary_action(steps: list[RemediationStep]) -> str | None:
    for step in steps:
        if step.gui_action:
            return step.gui_action
    return None


def _action_label(action: str) -> str:
    labels = {
        "apply": "一键 apply",
        "init": "初始化",
        "open_cache": "打开 cache",
        "repair": "修复路径",
        "pick_repo": "选择仓库",
    }
    return labels.get(action, action)


def show_gitmove_error(
    master: tk.Misc,
    err: GitMoveError,
    *,
    on_action: Callable[[str, GitMoveError], None] | None = None,
) -> None:
    ErrorDialog(master, err, on_action=on_action)
