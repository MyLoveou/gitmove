"""Vendor add/remove dialogs for the GUI."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from gitmove.gui import theme as theme_mod
from gitmove.gui.error_dialog import show_gitmove_error
from gitmove.gui.vendor_forms import (
    VendorAddForm,
    cursor_preset,
    existing_vendor_names,
    format_cli_preview,
    submit_vendor_add,
    validate_vendor_form,
)
from gitmove.gui.widgets import destructive_button, primary_button, secondary_button


class VendorAddDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: tk.Misc,
        root: Path,
        *,
        on_success: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._repo_root = root
        self._on_success = on_success
        self.title("添加 Vendor")
        self.geometry("560x580")
        self.minsize(520, 480)
        self.grab_set()
        self.transient(master)

        palette = theme_mod.resolve_theme()
        self._form = cursor_preset()

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        preset_row = ctk.CTkFrame(body, fg_color="transparent")
        preset_row.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        secondary_button(
            preset_row,
            text="预设：个人 .cursor",
            command=self._apply_cursor_preset,
        ).pack(side="left")

        self._fields: dict[str, tk.Variable] = {}
        self._add_field(body, "挂载路径 *", "repo_path", self._form.repo_path)
        self._add_field(body, "Vendor 名称 *", "name", self._form.name)
        self._add_field(body, "上游 URL *", "source_url", self._form.source_url)
        self._add_field(body, "分支 / Tag *", "source_ref", self._form.source_ref)
        self._add_field(body, "Pin（可选）", "source_pin", self._form.source_pin)

        opts = ctk.CTkFrame(body, fg_color="transparent")
        opts.pack(fill="x", pady=theme_mod.SPACING["sm"])
        self._migrate_var = tk.BooleanVar(value=self._form.migrate)
        ctk.CTkCheckBox(
            opts,
            text="迁移已有目录 (--migrate)",
            variable=self._migrate_var,
            **theme_mod.checkbox_kwargs(),
        ).pack(anchor="w", pady=2)
        self._auto_skip_var = tk.BooleanVar(value=self._form.auto_skip_tracked)
        ctk.CTkCheckBox(
            opts,
            text="自动 skip 已追踪文件",
            variable=self._auto_skip_var,
            **theme_mod.checkbox_kwargs(),
        ).pack(anchor="w", pady=2)
        self._shallow_var = tk.BooleanVar(value=self._form.shallow)
        ctk.CTkCheckBox(
            opts,
            text="浅克隆",
            variable=self._shallow_var,
            **theme_mod.checkbox_kwargs(),
        ).pack(anchor="w", pady=2)

        ctk.CTkLabel(body, text="高级", font=theme_mod.font_body()).pack(anchor="w", pady=(8, 4))
        self._add_field(body, "Cache 路径", "cache_path", "")
        self._add_field(body, "Include 子路径", "include_path", "")

        self._preview = ctk.CTkLabel(
            body,
            text=format_cli_preview(self._form),
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
            wraplength=500,
            justify="left",
            anchor="w",
        )
        self._preview.pack(fill="x", pady=(8, 0))

        self._error_label = ctk.CTkLabel(body, text="", text_color=palette.error, anchor="w")
        self._error_label.pack(fill="x", pady=(8, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 16))
        secondary_button(footer, text="取消", command=self.destroy).pack(side="right", padx=(8, 0))
        primary_button(footer, text="添加", command=self._submit).pack(side="right")

    def _add_field(self, parent, label: str, key: str, initial: str) -> None:
        ctk.CTkLabel(parent, text=label, font=theme_mod.font_caption(), anchor="w").pack(
            anchor="w", pady=(6, 2)
        )
        var = tk.StringVar(value=initial)
        entry = ctk.CTkEntry(parent, textvariable=var, **theme_mod.entry_kwargs())
        entry.pack(fill="x")
        entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        self._fields[key] = var

    def _apply_cursor_preset(self) -> None:
        self._form = cursor_preset()
        for key, var in self._fields.items():
            var.set(getattr(self._form, key, ""))
        self._migrate_var.set(self._form.migrate)
        self._auto_skip_var.set(self._form.auto_skip_tracked)
        self._shallow_var.set(self._form.shallow)
        self._refresh_preview()

    def _collect_form(self) -> VendorAddForm:
        data = {key: var.get() for key, var in self._fields.items()}
        return VendorAddForm(
            repo_path=data.get("repo_path", ""),
            name=data.get("name", ""),
            source_url=data.get("source_url", ""),
            source_ref=data.get("source_ref", "main"),
            source_pin=data.get("source_pin", ""),
            migrate=bool(self._migrate_var.get()),
            auto_skip_tracked=bool(self._auto_skip_var.get()),
            shallow=bool(self._shallow_var.get()),
            cache_path=data.get("cache_path", ""),
            include_path=data.get("include_path", ""),
        )

    def _refresh_preview(self) -> None:
        self._preview.configure(text=format_cli_preview(self._collect_form()))

    def _submit(self) -> None:
        form = self._collect_form()
        names = existing_vendor_names(self._repo_root)
        errors = validate_vendor_form(form, existing_names=names)
        if errors:
            self._error_label.configure(text=errors[0])
            return
        self._error_label.configure(text="")
        try:
            submit_vendor_add(self._repo_root, form)
        except Exception as exc:  # noqa: BLE001 — show in error dialog
            from gitmove.errors import wrap_exception

            show_gitmove_error(self, wrap_exception(exc))
            return
        messagebox.showinfo("完成", f"已添加 Vendor: {form.name.strip()}", parent=self)
        self.destroy()
        self._on_success()


class VendorRemoveDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: tk.Misc,
        root: Path,
        vendor_name: str,
        *,
        on_success: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._repo_root = root
        self._vendor_name = vendor_name
        self._on_success = on_success
        self.title(f"移除 Vendor: {vendor_name}")
        self.geometry("480x280")
        self.grab_set()
        self.transient(master)

        palette = theme_mod.resolve_theme()
        ctk.CTkLabel(
            self,
            text=f"将拆除 Vendor「{vendor_name}」的 link，并从配置中删除。",
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        self._keep_skip_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self,
            text="保留 skip-worktree（推荐）",
            variable=self._keep_skip_var,
            **theme_mod.checkbox_kwargs(),
        ).pack(anchor="w", padx=16, pady=4)
        self._purge_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="同时删除本地 cache（不可恢复）",
            variable=self._purge_var,
            **theme_mod.checkbox_kwargs(),
        ).pack(anchor="w", padx=16, pady=4)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=16)
        secondary_button(footer, text="取消", command=self.destroy).pack(side="right", padx=(8, 0))
        destructive_button(footer, text="确认移除", command=self._submit).pack(side="right")

    def _submit(self) -> None:
        from gitmove import vendor as vendor_mod

        if self._purge_var.get():
            if not messagebox.askyesno(
                "确认",
                "将永久删除 cache 目录，是否继续？",
                parent=self,
            ):
                return
        try:
            vendor_mod.remove_vendor(
                self._repo_root,
                self._vendor_name,
                purge_cache=bool(self._purge_var.get()),
                keep_skip=bool(self._keep_skip_var.get()),
            )
        except Exception as exc:  # noqa: BLE001
            from gitmove.errors import wrap_exception

            show_gitmove_error(self, wrap_exception(exc))
            return
        messagebox.showinfo("完成", f"已移除 Vendor: {self._vendor_name}", parent=self)
        self.destroy()
        self._on_success()


def open_vendor_add_dialog(master: tk.Misc, root: Path, *, on_success: Callable[[], None]) -> None:
    VendorAddDialog(master, root, on_success=on_success)


def open_vendor_remove_dialog(
    master: tk.Misc,
    root: Path,
    vendor_name: str,
    *,
    on_success: Callable[[], None],
) -> None:
    VendorRemoveDialog(master, root, vendor_name, on_success=on_success)
