"""GitMove error dialog with remediation actions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from gitmove.errors import GitMoveError, RemediationStep
from gitmove.gui import theme as theme_mod
from gitmove.gui.widgets import primary_button, secondary_button


def format_error_detail(err: GitMoveError) -> str:
    lines = [f"code: {err.code}"]
    if err.context:
        for key, value in err.context.items():
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class ErrorDialog(ctk.CTkToplevel):
    _BASE_HEIGHT = 400
    _DETAIL_EXTRA = 120

    def __init__(
        self,
        master: tk.Misc,
        err: GitMoveError,
        *,
        on_action: Callable[[str, GitMoveError], None] | None = None,
    ) -> None:
        super().__init__(master)
        palette = theme_mod.resolve_theme()
        self.title("gitmove 错误")
        self.geometry("540x400")
        self.minsize(480, 280)
        self.grab_set()
        self.focus_force()

        self._detail_visible = False
        self._detail_box = ctk.CTkTextbox(self, height=100, wrap="word", **theme_mod.textbox_kwargs())
        self._detail_box.insert("end", format_error_detail(err))
        self._detail_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=(0, 16))

        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", pady=(8, 0))

        primary = _primary_action(err.steps)
        if primary and on_action:
            primary_button(
                btn_row,
                text=_action_label(primary),
                command=lambda: self._run_action(primary, err, on_action),
            ).pack(side="left", padx=(0, 8))

        if err.steps and err.steps[0].command:
            secondary_button(
                btn_row,
                text="复制命令",
                command=lambda: self._copy_command(err.steps[0].command or ""),
            ).pack(side="left", padx=(0, 8))

        secondary_button(btn_row, text="关闭", command=self.destroy).pack(side="right")

        self._toggle_btn = secondary_button(
            footer,
            text="▼ 技术详情",
            command=self._toggle_detail,
            anchor="w",
            height=28,
        )
        self._toggle_btn.pack(side="bottom", anchor="w", pady=(4, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True, padx=16, pady=(16, 8))

        ctk.CTkLabel(
            body,
            text=f"✗ {err.message}",
            font=theme_mod.font_section(),
            text_color=palette.error,
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        if err.cause:
            ctk.CTkLabel(body, text="原因", font=theme_mod.font_body()).pack(anchor="w")
            ctk.CTkLabel(
                body,
                text=err.cause,
                font=theme_mod.font_caption(),
                text_color=palette.text_primary,
                wraplength=500,
                justify="left",
            ).pack(anchor="w", pady=(0, 8))

        if err.steps:
            ctk.CTkLabel(body, text="建议操作", font=theme_mod.font_body()).pack(anchor="w")
            steps_box = ctk.CTkTextbox(body, height=120, wrap="word", **theme_mod.textbox_kwargs())
            steps_box.pack(fill="x", pady=(4, 0))
            for index, step in enumerate(err.steps, start=1):
                steps_box.insert("end", f"{index}. {step.title}\n")
                if step.detail:
                    steps_box.insert("end", f"   {step.detail}\n")
                if step.command:
                    steps_box.insert("end", f"   {step.command}\n")
            steps_box.configure(state="disabled")

    def _toggle_detail(self) -> None:
        if self._detail_visible:
            self._detail_box.pack_forget()
            self._toggle_btn.configure(text="▼ 技术详情")
            self._resize_to_content(self._BASE_HEIGHT)
        else:
            self._detail_box.pack(
                in_=self._toggle_btn.master,
                side="bottom",
                fill="both",
                expand=False,
                pady=(0, 4),
                before=self._toggle_btn,
            )
            self._toggle_btn.configure(text="▲ 技术详情")
            self._resize_to_content(self._BASE_HEIGHT + self._DETAIL_EXTRA)
        self._detail_visible = not self._detail_visible

    def _resize_to_content(self, min_height: int) -> None:
        self.update_idletasks()
        height = max(min_height, self.winfo_reqheight())
        width = max(540, self.winfo_width())
        self.geometry(f"{width}x{height}")

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
