"""Cross-platform desktop GUI for gitmove."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import customtkinter as ctk

from gitmove import __version__, git
from gitmove.config import config_path_for_repo, resolve_external_base
from gitmove.doctor import apply_all, init_repo, run_doctor
from gitmove.errors import GitMoveError, wrap_exception
from gitmove.gui.async_runner import call_on_main_thread
from gitmove.gui.error_dialog import show_gitmove_error
from gitmove.gui.sync_chooser import gui_file_chooser, gui_project_chooser
from gitmove.platform_util import open_path_in_file_manager
from gitmove import link as link_mod
from gitmove import projects as projects_mod
from gitmove.registry import RegistryError, add_project, list_projects, load_registry, remove_project, touch_last_used
from gitmove.platform_util import default_link_type, platform_label, resolve_link_type
from gitmove import profile as profile_mod
from gitmove import skip as skip_mod
from gitmove import sync as sync_mod
from gitmove import vendor as vendor_mod
from gitmove import worktree as worktree_mod
from gitmove.gui.empty_state import get_empty_state
from gitmove.gui.overview import doctor_counts, doctor_rows_for_tree
from gitmove.gui.profile_panel import profile_list_rows
from gitmove.gui.scenarios import SCENARIO_CARDS, get_scenario
from gitmove.gui import theme as theme_mod
from gitmove.gui.vendor_panel import vendor_tree_rows
from gitmove.gui.vendor_dialogs import open_vendor_add_dialog, open_vendor_remove_dialog
from gitmove.gui.widgets import (
    ElevatedPanel,
    EmptyStatePanel,
    HealthSummaryBar,
    PageHeader,
    build_scenario_grid,
    primary_button,
    secondary_button,
)


class GitMoveApp(ctk.CTk):
    def __init__(self, repo_path: str | None = None) -> None:
        super().__init__()
        self.title(f"gitmove v{__version__}")
        self.geometry("980x640")
        self.minsize(860, 520)

        self.repo_root: Path | None = None
        self._status_var = tk.StringVar(value="请选择 Git 仓库目录")
        self._busy = False
        self._toolbar_buttons: list[ctk.CTkButton] = []
        self._project_buttons: dict[str, ctk.CTkButton] = {}
        self._selected_alias: str | None = None
        self._project_list_frame: ctk.CTkScrollableFrame | None = None
        self._empty_panels: dict[str, EmptyStatePanel] = {}
        self._last_doctor_report = None
        self._initial_tab_pending = False
        self._vendor_sync_by_name: dict[str, vendor_mod.VendorSyncResult] = {}

        self._build_layout()
        self._style_treeviews()

        self._reload_project_sidebar()
        start = repo_path or str(Path.cwd())
        if git.is_git_repo(Path(start)):
            self.set_repo(Path(start))
        elif load_registry().default_project:
            self._select_registered_alias(load_registry().default_project)
        elif list_projects():
            self._select_registered_alias(list_projects()[0].alias)
        else:
            self._update_status("当前目录不是 Git 仓库，请注册或选择项目")

    def _build_layout(self) -> None:
        palette = theme_mod.resolve_theme()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=theme_mod.SPACING["md"], pady=(theme_mod.SPACING["md"], 6))

        sidebar = ElevatedPanel(body, width=228)
        sidebar.pack(side="left", fill="y", padx=(0, theme_mod.SPACING["sm"]))
        sidebar.pack_propagate(False)

        sidebar_inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkLabel(sidebar_inner, text="项目", font=theme_mod.font_section()).pack(
            anchor="w", padx=theme_mod.SPACING["xs"], pady=(theme_mod.SPACING["xs"], theme_mod.SPACING["xs"])
        )

        side_actions = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        side_actions.pack(side="bottom", fill="x", padx=2, pady=(theme_mod.SPACING["xs"], 0))

        for text, command in (
            ("添加项目", self._add_registered_project),
            ("从当前目录添加", self._add_current_repo),
            ("移除项目", self._remove_registered_project),
        ):
            secondary_button(side_actions, text=text, command=command, height=30).pack(
                fill="x", pady=2
            )
        ctk.CTkLabel(
            side_actions,
            text="批量",
            font=theme_mod.font_caption(),
            text_color=palette.text_primary,
            anchor="w",
        ).pack(anchor="w", pady=(theme_mod.SPACING["sm"], 2))
        for text, command in (
            ("全部 doctor", self._batch_doctor),
            ("全部 apply", self._batch_apply),
            ("全部 sync pull", self._batch_sync_pull),
        ):
            secondary_button(side_actions, text=text, command=command, height=30).pack(
                fill="x", pady=2
            )

        self._project_list_frame = ctk.CTkScrollableFrame(
            sidebar_inner,
            fg_color="transparent",
            label_text="",
        )
        self._project_list_frame.pack(fill="both", expand=True, padx=2, pady=(0, theme_mod.SPACING["xs"]))

        main_panel = ctk.CTkFrame(body, fg_color="transparent")
        main_panel.pack(side="left", fill="both", expand=True)

        header = ElevatedPanel(main_panel, corner_radius=theme_mod.RADIUS["sm"])
        header.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        inner_header = ctk.CTkFrame(header, fg_color="transparent")
        inner_header.pack(fill="x", padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])
        ctk.CTkLabel(inner_header, text="Git 仓库", font=theme_mod.font_body()).pack(
            side="left", padx=(0, theme_mod.SPACING["sm"])
        )
        self.repo_entry = ctk.CTkEntry(
            inner_header,
            placeholder_text="仓库根目录",
            **theme_mod.entry_kwargs(),
        )
        self.repo_entry.pack(side="left", fill="x", expand=True, padx=4)
        secondary_button(inner_header, text="选择仓库", width=100, command=self._pick_repo).pack(
            side="left", padx=4
        )
        primary_button(inner_header, text="刷新", width=72, command=self.refresh_all).pack(
            side="left", padx=4
        )

        toolbar = ctk.CTkFrame(main_panel, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        for text, command in (
            ("初始化", self._on_init),
            ("一键应用", self._on_apply),
            ("健康检查", self._on_doctor),
        ):
            btn = primary_button(toolbar, text=text, command=command)
            btn.pack(side="left", padx=4)
            self._toolbar_buttons.append(btn)
        ctk.CTkLabel(
            toolbar,
            text=f"平台: {platform_label()} · 默认链接: {default_link_type()}",
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
        ).pack(side="right", padx=8)

        self.tabs = ctk.CTkTabview(main_panel, **theme_mod.tabview_kwargs())
        self.tabs.pack(fill="both", expand=True, pady=6)

        self.tab_start = self.tabs.add("开始")
        self.tab_overview = self.tabs.add("概览")
        self.tab_skip = self.tabs.add("Skip-worktree")
        self.tab_link = self.tabs.add("外部链接")
        self.tab_vendor = self.tabs.add("Vendor")
        self.tab_profile = self.tabs.add("Profile")
        self.tab_worktree = self.tabs.add("Worktree")
        self.tab_sync = self.tabs.add("同步")

        self._build_start_tab()
        self._build_overview_tab()
        self._build_skip_tab()
        self._build_link_tab()
        self._build_vendor_tab()
        self._build_profile_tab()
        self._build_worktree_tab()
        self._build_sync_tab()

        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=28)
        status_frame.pack(fill="x", padx=theme_mod.SPACING["lg"], pady=(0, theme_mod.SPACING["sm"]))
        ctk.CTkFrame(status_frame, height=1, fg_color=palette.border).pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            status_frame,
            textvariable=self._status_var,
            anchor="w",
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
        ).pack(fill="x")

    def _build_start_tab(self) -> None:
        frame = ctk.CTkScrollableFrame(self.tab_start, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        ctk.CTkLabel(frame, text="你想做什么？", font=theme_mod.font_title()).pack(
            anchor="w", pady=(0, theme_mod.SPACING["md"])
        )
        ctk.CTkLabel(
            frame,
            text="按场景选型，不必先理解 skip / link / vendor 的区别",
            font=theme_mod.font_caption(),
            text_color=theme_mod.resolve_theme().text_muted,
            anchor="w",
        ).pack(anchor="w", pady=(0, theme_mod.SPACING["lg"]))

        build_scenario_grid(frame, SCENARIO_CARDS, on_select=self.navigate_to_scenario)

        secondary_button(
            frame,
            text="打开完整场景手册",
            command=self._open_workflows_doc,
        ).pack(anchor="w", pady=(theme_mod.SPACING["lg"], 0))

    def _build_overview_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_overview, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        PageHeader(frame, "健康检查", subtitle="按优先级查看问题并一键修复").pack(
            fill="x", pady=(0, theme_mod.SPACING["sm"])
        )

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        self.overview_health_bar = HealthSummaryBar(header)
        self.overview_health_bar.pack(side="left", fill="x", expand=True)
        secondary_button(header, text="重新检查", width=90, command=self._on_doctor).pack(
            side="right", padx=4
        )
        self.overview_apply_btn = primary_button(
            header,
            text="一键应用",
            width=90,
            command=self._on_apply,
        )
        self.overview_apply_btn.pack(side="right", padx=4)

        issue_shell = ElevatedPanel(frame)
        issue_shell.pack(fill="both", expand=True, pady=(0, theme_mod.SPACING["sm"]))
        issue_frame = tk.Frame(issue_shell, bg=theme_mod.pick(theme_mod.resolve_theme().surface_elevated))
        issue_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.overview_issue_tree = ttk.Treeview(
            issue_frame,
            columns=("level", "category", "message"),
            show="headings",
            selectmode="browse",
            height=8,
        )
        for col, heading, width in (
            ("level", "级别", 64),
            ("category", "分类", 100),
            ("message", "说明", 420),
        ):
            self.overview_issue_tree.heading(col, text=heading)
            self.overview_issue_tree.column(col, width=width, stretch=col == "message")
        issue_vsb = ttk.Scrollbar(issue_frame, orient="vertical", command=self.overview_issue_tree.yview)
        self.overview_issue_tree.configure(yscrollcommand=issue_vsb.set)
        self.overview_issue_tree.pack(side="left", fill="both", expand=True)
        issue_vsb.pack(side="right", fill="y")
        theme_mod.configure_level_tags(self.overview_issue_tree)

        self.overview_config_label = ctk.CTkLabel(
            frame,
            text="",
            anchor="w",
            font=theme_mod.font_caption(),
            text_color=theme_mod.resolve_theme().text_muted,
        )
        self.overview_config_label.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        ctk.CTkLabel(frame, text="外部目录默认根路径", font=theme_mod.font_body()).pack(anchor="w")
        base_row = ctk.CTkFrame(frame, fg_color="transparent")
        base_row.pack(fill="x", pady=6)
        self.external_base_entry = ctk.CTkEntry(
            base_row,
            placeholder_text="~/gitmove-external/<repo>",
            **theme_mod.entry_kwargs(),
        )
        self.external_base_entry.pack(side="left", fill="x", expand=True, padx=(0, theme_mod.SPACING["sm"]))
        primary_button(base_row, text="保存", width=80, command=self._save_external_base).pack(side="left")

    def _build_skip_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_skip,
            tree_attr="skip_tree",
            columns=("path", "tracked", "skip", "config"),
            headings=("路径", "已追踪", "Skip 生效", "在配置中"),
            add_handler=self._add_skip_dialog,
            remove_handler=self._remove_skip_selection,
            tab_name="Skip-worktree",
        )

    def _build_link_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_link,
            tree_attr="link_tree",
            columns=("repo", "external", "type", "ok"),
            headings=("仓库路径", "外部路径", "类型", "状态"),
            add_handler=self._add_link_dialog,
            remove_handler=self._remove_link_selection,
            tab_name="外部链接",
        )

    def _build_worktree_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_worktree,
            tree_attr="worktree_tree",
            columns=("name", "path", "branch", "registered"),
            headings=("名称", "路径", "分支", "已注册"),
            add_handler=self._add_worktree_dialog,
            remove_handler=self._remove_worktree_selection,
            tab_name="Worktree",
        )

    def _build_vendor_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_vendor, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        PageHeader(
            frame,
            "上游 Vendor",
            subtitle="从其他 Git 仓库挂载目录（如 .cursor）。不改 .gitignore。",
        ).pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        primary_button(btn_row, text="+ 添加 Vendor…", command=self._open_vendor_add_dialog).pack(
            side="left", padx=4
        )
        secondary_button(btn_row, text="检查更新", command=self._on_vendor_check_updates).pack(
            side="left", padx=4
        )
        secondary_button(btn_row, text="全部 Sync", command=self._on_vendor_sync_all).pack(
            side="left", padx=4
        )
        secondary_button(btn_row, text="刷新", width=72, command=self.refresh_all).pack(side="left", padx=4)
        secondary_button(btn_row, text="打开文档", command=self._open_workflows_doc).pack(side="left", padx=4)

        tree_shell = ElevatedPanel(frame)
        tree_shell.pack(fill="both", expand=True)
        tree_frame = tk.Frame(tree_shell, bg=theme_mod.pick(theme_mod.resolve_theme().surface_elevated))
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.vendor_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "repo_path", "source", "pin", "status"),
            show="headings",
            selectmode="browse",
        )
        for col, heading, width in (
            ("name", "名称", 100),
            ("repo_path", "路径", 100),
            ("source", "上游", 200),
            ("pin", "Pin", 80),
            ("status", "状态", 100),
        ):
            self.vendor_tree.heading(col, text=heading)
            self.vendor_tree.column(col, width=width, stretch=col in {"repo_path", "source"})
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.vendor_tree.yview)
        self.vendor_tree.configure(yscrollcommand=vsb.set)
        self.vendor_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        action_row = ctk.CTkFrame(frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(theme_mod.SPACING["sm"], 0))
        secondary_button(action_row, text="Sync 选中", command=self._on_vendor_sync_selected).pack(
            side="left", padx=4
        )
        secondary_button(action_row, text="移除选中…", command=self._on_vendor_remove_selected).pack(
            side="left", padx=4
        )

        panel = EmptyStatePanel(frame)
        self._empty_panels["Vendor"] = panel
        self._vendor_empty_actions = ctk.CTkFrame(frame, fg_color="transparent")
        primary_button(
            self._vendor_empty_actions,
            text="+ 添加 Vendor…",
            command=self._open_vendor_add_dialog,
        ).pack(anchor="w")

    def _build_profile_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_profile, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        PageHeader(
            frame,
            "策略 Profile",
            subtitle="切换后自动 apply（含 .cursor vendor reconcile）",
        ).pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        self.profile_active_var = tk.StringVar(value="当前: —")
        ctk.CTkLabel(
            frame,
            textvariable=self.profile_active_var,
            anchor="w",
            font=theme_mod.font_body(),
        ).pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        action_row = ctk.CTkFrame(frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        ctk.CTkLabel(action_row, text="Profile:", font=theme_mod.font_body()).pack(side="left", padx=(0, 6))
        self.profile_combo = ctk.CTkComboBox(
            action_row,
            values=[],
            width=180,
            state="readonly",
            **theme_mod.combobox_kwargs(),
        )
        self.profile_combo.pack(side="left", padx=4)
        primary_button(action_row, text="切换", width=72, command=self._on_profile_switch).pack(
            side="left", padx=4
        )
        secondary_button(action_row, text="dry-run 预检", width=100, command=self._on_profile_dry_run).pack(
            side="left", padx=4
        )
        secondary_button(action_row, text="保存当前为…", command=self._on_profile_save).pack(side="left", padx=4)

        tree_shell = ElevatedPanel(frame)
        tree_shell.pack(fill="both", expand=True)
        tree_frame = tk.Frame(tree_shell, bg=theme_mod.pick(theme_mod.resolve_theme().surface_elevated))
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.profile_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "status"),
            show="headings",
            selectmode="browse",
        )
        for col, heading, width in (("name", "名称", 180), ("status", "状态", 100)):
            self.profile_tree.heading(col, text=heading)
            self.profile_tree.column(col, width=width, stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.profile_tree.yview)
        self.profile_tree.configure(yscrollcommand=vsb.set)
        self.profile_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        panel = EmptyStatePanel(frame)
        self._empty_panels["Profile"] = panel

    def _build_sync_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_sync, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        PageHeader(
            frame,
            "Skip 同步",
            subtitle="当业务仓 remote 也修改了 skip-worktree 文件时，在此检查并 reconcile。",
        ).pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        primary_button(btn_row, text="检查 drift", command=self._on_sync_check).pack(side="left", padx=4)
        secondary_button(btn_row, text="Sync pull", command=self._on_sync_pull).pack(side="left", padx=4)

        tree_shell = ElevatedPanel(frame)
        tree_shell.pack(fill="both", expand=True)
        tree_frame = tk.Frame(tree_shell, bg=theme_mod.pick(theme_mod.resolve_theme().surface_elevated))
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.sync_tree = ttk.Treeview(
            tree_frame,
            columns=("path", "local", "remote", "attention"),
            show="headings",
            selectmode="browse",
        )
        for col, heading, width in (
            ("path", "路径", 220),
            ("local", "本地修改", 90),
            ("remote", "远程修改", 90),
            ("attention", "需处理", 90),
        ):
            self.sync_tree.heading(col, text=heading)
            self.sync_tree.column(col, width=width, stretch=col == "path")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sync_tree.yview)
        self.sync_tree.configure(yscrollcommand=vsb.set)
        self.sync_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        panel = EmptyStatePanel(frame)
        self._empty_panels["同步"] = panel
        self._update_empty_state("同步", has_data=True)

    def _build_data_tab(
        self,
        *,
        parent: ctk.CTkFrame,
        tree_attr: str,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        add_handler: Callable[[], None],
        remove_handler: Callable[[], None],
        tab_name: str | None = None,
    ) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, theme_mod.SPACING["sm"]))
        primary_button(btn_row, text="添加", width=90, command=add_handler).pack(side="left", padx=4)
        secondary_button(btn_row, text="移除选中", width=100, command=remove_handler).pack(
            side="left", padx=4
        )

        tree_shell = ElevatedPanel(frame)
        tree_shell.pack(fill="both", expand=True)
        tree_frame = tk.Frame(tree_shell, bg=theme_mod.pick(theme_mod.resolve_theme().surface_elevated))
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading in zip(columns, headings, strict=True):
            tree.heading(col, text=heading)
            width = 220 if col in {"path", "repo", "external", "external_path"} else 100
            tree.column(col, width=width, stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        setattr(self, tree_attr, tree)

        if tab_name:
            panel = EmptyStatePanel(frame)
            self._empty_panels[tab_name] = panel

    def navigate_to_scenario(self, scenario_id: str) -> None:
        card = get_scenario(scenario_id)
        if card is None:
            return
        self.tabs.set(card.target_tab)

    def _open_workflows_doc(self) -> None:
        doc = self._workflows_doc_path()
        if doc.exists():
            open_path_in_file_manager(str(doc))
        else:
            messagebox.showwarning("提示", f"未找到文档:\n{doc}", parent=self)

    def _workflows_doc_path(self) -> Path:
        return Path(__file__).resolve().parents[3] / "docs" / "guides" / "workflows.md"

    def _pick_initial_tab(self, root: Path) -> None:
        if config_path_for_repo(root).exists():
            self.tabs.set("概览")
        else:
            self.tabs.set("开始")

    def _update_empty_state(self, tab_name: str, *, has_data: bool) -> None:
        panel = self._empty_panels.get(tab_name)
        if panel is None:
            return
        if has_data:
            panel.hide()
            return
        panel.apply_copy(get_empty_state(tab_name))

    def _style_treeviews(self) -> None:
        theme_mod.style_treeview()

    def _reload_project_sidebar(self) -> None:
        if self._project_list_frame is None:
            return
        for child in self._project_list_frame.winfo_children():
            child.destroy()
        self._project_buttons.clear()
        for entry in list_projects():
            label = entry.alias if not entry.group else f"{entry.alias} ({entry.group})"
            palette = theme_mod.resolve_theme()
            selected = entry.alias == self._selected_alias
            btn = ctk.CTkButton(
                self._project_list_frame,
                text=label,
                anchor="w",
                height=32,
                font=theme_mod.font_body(),
                fg_color=palette.accent if selected else palette.surface_secondary,
                hover_color=palette.accent_hover if selected else palette.surface_elevated,
                border_width=0 if selected else 1,
                border_color=palette.border,
                text_color=palette.text_on_accent if selected else palette.text_primary,
                command=lambda alias=entry.alias: self._select_registered_alias(alias),
            )
            btn.pack(fill="x", pady=2)
            self._project_buttons[entry.alias] = btn

    def _select_registered_alias(self, alias: str) -> None:
        for entry in list_projects():
            if entry.alias != alias:
                continue
            self._selected_alias = alias
            try:
                touch_last_used(alias)
            except RegistryError:
                pass
            self._reload_project_sidebar()
            if entry.path.exists() and git.is_git_repo(entry.path):
                self.set_repo(entry.path)
            else:
                self.repo_root = entry.path.resolve()
                self.repo_entry.delete(0, "end")
                self.repo_entry.insert(0, str(entry.path))
                self._update_status(f"项目路径不可用: {entry.path}")
            return

    def _add_registered_project(self) -> None:
        chosen = filedialog.askdirectory(title="选择要注册的 Git 仓库")
        if not chosen:
            return
        path = Path(chosen)
        if not git.is_git_repo(path):
            messagebox.showerror("错误", "所选目录不是 Git 仓库")
            return
        try:
            entry = add_project(path)
        except RegistryError as exc:
            messagebox.showerror("错误", str(exc))
            return
        self._reload_project_sidebar()
        self._select_registered_alias(entry.alias)

    def _add_current_repo(self) -> None:
        root = self._require_repo()
        if not root:
            messagebox.showwarning("提示", "请先打开有效的 Git 仓库")
            return
        try:
            entry = add_project(root)
        except RegistryError as exc:
            messagebox.showerror("错误", str(exc))
            return
        self._reload_project_sidebar()
        self._select_registered_alias(entry.alias)

    def _remove_registered_project(self) -> None:
        if not self._selected_alias:
            messagebox.showinfo("提示", "请先在左侧选择一个项目")
            return
        alias = self._selected_alias
        try:
            remove_project(alias)
        except RegistryError as exc:
            messagebox.showerror("错误", str(exc))
            return
        self._selected_alias = None
        self._reload_project_sidebar()
        self._update_status(f"已移除项目: {alias}")

    def _batch_doctor(self) -> None:
        entries = list_projects()
        if not entries:
            messagebox.showinfo("提示", "没有已注册的项目")
            return

        def task() -> list[projects_mod.ProjectBatchRow]:
            return projects_mod.batch_doctor(entries)

        def on_success(rows: object) -> None:
            lines = [f"{row.alias}: errors={row.error_count} warns={row.warn_count} ({row.status})" for row in rows]  # type: ignore[union-attr]
            messagebox.showinfo("全部 doctor 完成", "\n".join(lines))

        self._run_background("正在批量检查…", task, on_success=on_success)

    def _batch_apply(self) -> None:
        entries = list_projects()
        if not entries:
            messagebox.showinfo("提示", "没有已注册的项目")
            return

        def task() -> list[projects_mod.ProjectBatchRow]:
            return projects_mod.batch_apply(entries)

        def on_success(rows: object) -> None:
            lines = [f"{row.alias}: errors={row.error_count} warns={row.warn_count}" for row in rows]  # type: ignore[union-attr]
            messagebox.showinfo("全部 apply 完成", "\n".join(lines))
            self.refresh_all()

        self._run_background("正在批量应用…", task, on_success=on_success)

    def set_repo(self, root: Path) -> None:
        self.repo_root = root.resolve()
        self.repo_entry.delete(0, "end")
        self.repo_entry.insert(0, str(self.repo_root))
        matched = False
        for entry in list_projects():
            if entry.path == self.repo_root:
                self._selected_alias = entry.alias
                matched = True
                try:
                    touch_last_used(entry.alias)
                except RegistryError:
                    pass
                break
        if not matched:
            self._selected_alias = None
        self._reload_project_sidebar()
        self._initial_tab_pending = True
        self.refresh_all()

    def _pick_repo(self) -> None:
        chosen = filedialog.askdirectory(title="选择 Git 仓库根目录")
        if not chosen:
            return
        path = Path(chosen)
        if not git.is_git_repo(path):
            messagebox.showerror("错误", "所选目录不是 Git 仓库")
            return
        self.set_repo(path)

    def _require_repo(self) -> Path | None:
        if self.repo_root is not None:
            return self.repo_root
        messagebox.showwarning("提示", "请先选择有效的 Git 仓库")
        return None

    def _update_status(self, text: str) -> None:
        self._status_var.set(text)

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in self._toolbar_buttons:
            btn.configure(state=state)
        if message:
            self._update_status(message)

    def _run_background(
        self,
        message: str,
        task: Callable[[], object],
        *,
        on_success: Callable[[object], None] | None = None,
    ) -> None:
        if self._busy:
            return
        self._set_busy(True, message)
        result_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        def worker() -> None:
            try:
                result_queue.put(("success", task()))
            except BaseException as exc:  # noqa: BLE001 — surface to UI
                result_queue.put(("error", exc))

        def poll() -> None:
            try:
                kind, payload = result_queue.get_nowait()
            except queue.Empty:
                self.after(50, poll)
                return

            self._set_busy(False)
            if kind == "error":
                err = wrap_exception(payload)  # type: ignore[arg-type]
                show_gitmove_error(self, err, on_action=self._handle_error_action)
                return
            if on_success:
                on_success(payload)

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, poll)

    def refresh_all(self) -> None:
        root = self._require_repo()
        if not root:
            return

        def task() -> tuple:
            cfg = skip_mod.load_config(root)
            skip_items = skip_mod.list_status(root)
            link_items = link_mod.list_links(root)
            wt_items = worktree_mod.list_worktrees(root)
            report = run_doctor(
                root,
                skip_items=skip_items,
                link_items=link_items,
                wt_items=wt_items,
            )
            external = cfg.external_base or str(resolve_external_base(cfg, root))
            vendors = vendor_tree_rows(root, sync_by_name=self._vendor_sync_by_name)
            profiles = profile_list_rows(root)
            active = profile_mod.active_profile_name(root)
            return (
                root,
                cfg,
                skip_items,
                link_items,
                wt_items,
                report,
                external,
                vendors,
                profiles,
                active,
            )

        def on_success(payload: object) -> None:
            (
                root,
                _cfg,
                skip_items,
                link_items,
                wt_items,
                report,
                external,
                vendors,
                profiles,
                active,
            ) = payload  # type: ignore[misc]
            self.external_base_entry.delete(0, "end")
            self.external_base_entry.insert(0, external)
            self._render_skip(skip_items)
            self._render_links(link_items)
            self._render_worktrees(wt_items)
            self._render_vendor(vendors)
            self._render_profile(profiles, active)
            self._render_overview(root, report)
            self._last_doctor_report = report
            if self._initial_tab_pending:
                self._pick_initial_tab(root)
                self._initial_tab_pending = False
            self._update_status(f"已加载: {root}")

        self._run_background("正在刷新…", task, on_success=on_success)

    def _render_overview(self, root: Path, report) -> None:
        errors, warns, infos = doctor_counts(report)
        self.overview_health_bar.set_counts(errors, warns, infos)
        cfg_path = config_path_for_repo(root)
        if cfg_path.exists():
            self.overview_config_label.configure(text=f"配置文件: {cfg_path}")
        else:
            self.overview_config_label.configure(text="配置文件: 未初始化")

        tree = self.overview_issue_tree
        tree.delete(*tree.get_children())
        for index, row in enumerate(doctor_rows_for_tree(report)):
            tag = theme_mod.level_tag(row.level)
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(row.level_label, row.category, row.message),
                tags=(tag,),
            )

    def _handle_error_action(self, action: str, err: GitMoveError) -> None:
        if action == "apply":
            self._on_apply()
        elif action == "init":
            self._on_init()
        elif action == "pick_repo":
            self._pick_repo()
        elif action == "open_cache":
            cache = err.context.get("cache")
            if cache:
                open_path_in_file_manager(str(cache))
            else:
                messagebox.showwarning("提示", "未找到 cache 路径", parent=self)
        elif action == "repair":
            messagebox.showinfo("修复路径", "请使用 CLI: gitmove projects repair", parent=self)

    def _batch_sync_pull(self) -> None:
        if self._busy:
            return
        entries = projects_mod.iter_projects()

        def project_chooser(entry, report):
            return call_on_main_thread(
                self, lambda: gui_project_chooser(self, entry, report)
            )

        def file_chooser(drift):
            return call_on_main_thread(self, lambda: gui_file_chooser(self, drift))

        def task():
            return projects_mod.batch_sync_pull(
                entries,
                fetch=True,
                project_chooser=project_chooser,
                file_chooser=file_chooser,
            )

        def on_success(results) -> None:
            lines, had_errors = projects_mod.format_batch_sync_pull_lines(results)
            title = "批量 sync（有错误）" if had_errors else "批量 sync"
            messagebox.showinfo(title, "\n".join(lines) or "完成", parent=self)

        self._run_background("正在批量 sync pull…", task, on_success=on_success)

    def _render_skip(self, items) -> None:
        tree = self.skip_tree
        tree.delete(*tree.get_children())
        for item in items:
            tree.insert(
                "",
                "end",
                iid=item.path,
                values=(
                    item.path,
                    "是" if item.tracked else "否",
                    "是" if item.skip_active else "否",
                    "是" if item.in_config else "否",
                ),
            )
        self._update_empty_state("Skip-worktree", has_data=bool(items))

    def _render_links(self, items) -> None:
        tree = self.link_tree
        tree.delete(*tree.get_children())
        for item in items:
            ok = "正常" if item.is_link and item.link_ok else ("部分" if item.is_link else "否")
            tree.insert(
                "",
                "end",
                iid=item.repo_path,
                values=(item.repo_path, item.external_path, item.link_type, ok),
            )
        self._update_empty_state("外部链接", has_data=bool(items))

    def _render_worktrees(self, items) -> None:
        tree = self.worktree_tree
        tree.delete(*tree.get_children())
        for item in items:
            tree.insert(
                "",
                "end",
                iid=item.name,
                values=(
                    item.name,
                    item.path,
                    item.branch or "—",
                    "是" if item.registered else "否",
                ),
            )
        self._update_empty_state("Worktree", has_data=bool(items))

    def _render_vendor(self, rows) -> None:
        tree = self.vendor_tree
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert(
                "",
                "end",
                iid=row.name,
                values=(row.name, row.repo_path, row.source, row.pin, row.status),
            )
        has_data = bool(rows)
        self._update_empty_state("Vendor", has_data=has_data)
        if has_data:
            self._vendor_empty_actions.pack_forget()
        else:
            self._vendor_empty_actions.pack(fill="x", pady=(theme_mod.SPACING["sm"], 0))

    def _render_profile(self, rows: list[tuple[str, str]], active: str | None) -> None:
        tree = self.profile_tree
        tree.delete(*tree.get_children())
        for name, status in rows:
            tree.insert("", "end", iid=name, values=(name, status))
        names = [name for name, _status in rows]
        self.profile_combo.configure(values=names if names else [""])
        if names:
            current = active if active in names else names[0]
            self.profile_combo.set(current)
        else:
            self.profile_combo.set("")
        self.profile_active_var.set(f"当前: {active or '—'}")
        self._update_empty_state("Profile", has_data=bool(rows))

    def _render_sync_report(self, report: sync_mod.SyncCheckReport) -> None:
        tree = self.sync_tree
        tree.delete(*tree.get_children())
        for item in report.drifts:
            tree.insert(
                "",
                "end",
                iid=item.path,
                values=(
                    item.path,
                    "是" if item.local_modified else "否",
                    "是" if item.remote_modified else "否",
                    "是" if item.needs_attention else "否",
                ),
            )
        self._update_empty_state("同步", has_data=bool(report.drifts))

    def _selected_vendor_name(self) -> str | None:
        selected = self.vendor_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在 Vendor 列表选中一行", parent=self)
            return None
        return selected[0]

    def _open_vendor_add_dialog(self) -> None:
        root = self._require_repo()
        if not root:
            return
        open_vendor_add_dialog(self, root, on_success=self.refresh_all)

    def _on_vendor_check_updates(self) -> None:
        root = self._require_repo()
        if not root:
            return

        def task() -> list[vendor_mod.VendorSyncResult]:
            return vendor_mod.check_vendor_updates(root, fetch=True)

        def on_success(results: object) -> None:
            self._vendor_sync_by_name = {item.name: item for item in results}  # type: ignore[union-attr]
            self.refresh_all()
            behind = sum(1 for item in self._vendor_sync_by_name.values() if item.behind > 0)
            messagebox.showinfo("检查完成", f"已检查 {len(self._vendor_sync_by_name)} 个 Vendor，落后 {behind} 个", parent=self)

        self._run_background("正在检查 Vendor 更新…", task, on_success=on_success)

    def _on_vendor_sync_selected(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self._selected_vendor_name()
        if not name:
            return
        self._sync_vendor_by_name(root, name)

    def _on_vendor_sync_all(self) -> None:
        root = self._require_repo()
        if not root:
            return
        vendors = vendor_mod.list_vendors(root)
        if not vendors:
            messagebox.showinfo("提示", "没有可 Sync 的 Vendor", parent=self)
            return

        def task() -> list[vendor_mod.VendorSyncResult]:
            return vendor_mod.sync_all_vendors(root, fetch=True)

        def on_success(results: object) -> None:
            sync_results = results  # type: ignore[assignment]
            lines = []
            for item in sync_results:
                if item.updated:
                    lines.append(f"{item.name}: 已更新")
                elif item.ok:
                    lines.append(f"{item.name}: 已是最新")
                else:
                    lines.append(f"{item.name}: 失败 — {item.message or '未知错误'}")
            messagebox.showinfo("全部 Sync", "\n".join(lines) or "完成", parent=self)
            self._vendor_sync_by_name = {item.name: item for item in sync_results}
            self.refresh_all()

        self._run_background("正在 Sync 全部 Vendor…", task, on_success=on_success)

    def _sync_vendor_by_name(self, root: Path, name: str) -> None:
        def task() -> vendor_mod.VendorSyncResult:
            return vendor_mod.sync_vendor(root, name, fetch=True)

        def on_success(result: object) -> None:
            sync_result = result  # type: ignore[assignment]
            self._vendor_sync_by_name[name] = sync_result
            if sync_result.updated:
                msg = f"{name} 已更新"
                if sync_result.old_commit and sync_result.new_commit:
                    msg += f"\n{sync_result.old_commit[:7]} → {sync_result.new_commit[:7]}"
            elif sync_result.ok:
                msg = f"{name} 已是最新"
            else:
                msg = sync_result.message or "Sync 失败"
            messagebox.showinfo("Sync", msg, parent=self)
            self.refresh_all()

        self._run_background(f"正在 Sync {name}…", task, on_success=on_success)

    def _on_vendor_remove_selected(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self._selected_vendor_name()
        if not name:
            return
        open_vendor_remove_dialog(self, root, name, on_success=self.refresh_all)

    def _copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._update_status("已复制到剪贴板")

    def _on_profile_switch(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self.profile_combo.get().strip()
        if not name:
            messagebox.showwarning("提示", "请选择 Profile", parent=self)
            return

        def task() -> None:
            profile_mod.use_profile(root, name)

        def on_success(_: object) -> None:
            messagebox.showinfo("完成", f"已切换到 Profile: {name}", parent=self)
            self.refresh_all()

        self._run_background(f"正在切换到 {name}…", task, on_success=on_success)

    def _on_profile_dry_run(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self.profile_combo.get().strip()
        if not name:
            messagebox.showwarning("提示", "请选择 Profile", parent=self)
            return

        def task() -> None:
            profile_mod.use_profile(root, name, dry_run=True)

        def on_success(_: object) -> None:
            messagebox.showinfo("预检通过", f"Profile {name} dry-run 通过", parent=self)

        self._run_background(f"正在预检 {name}…", task, on_success=on_success)

    def _on_profile_save(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self._ask_text("保存 Profile", "Profile 名称（字母数字_-）:")
        if not name:
            return

        def task() -> None:
            profile_mod.save_profile(root, name)

        def on_success(_: object) -> None:
            messagebox.showinfo("完成", f"已保存 Profile: {name}", parent=self)
            self.refresh_all()

        self._run_background("正在保存 Profile…", task, on_success=on_success)

    def _on_sync_check(self) -> None:
        root = self._require_repo()
        if not root:
            return
        self.tabs.set("同步")

        def task() -> sync_mod.SyncCheckReport:
            return sync_mod.check_sync(root, fetch=True)

        def on_success(report: object) -> None:
            sync_report = report  # type: ignore[assignment]
            self._render_sync_report(sync_report)
            attention = len(sync_report.attention_items)
            messagebox.showinfo(
                "Sync 检查",
                f"需关注: {attention} 项",
                parent=self,
            )

        self._run_background("正在检查 sync drift…", task, on_success=on_success)

    def _on_sync_pull(self) -> None:
        root = self._require_repo()
        if not root:
            return

        def file_chooser(drift):
            return call_on_main_thread(
                self,
                lambda: gui_file_chooser(self, drift),
            )

        def task() -> sync_mod.SyncPullReport:
            return sync_mod.sync_pull(root, fetch=True, chooser=file_chooser)

        def on_success(report: object) -> None:
            pull_report = report  # type: ignore[assignment]
            lines = []
            if pull_report.pulled:
                lines.append("已 pull")
            if pull_report.reapplied:
                lines.append(f"重新 apply: {', '.join(pull_report.reapplied)}")
            if pull_report.skipped:
                lines.append(f"跳过: {', '.join(pull_report.skipped)}")
            if pull_report.errors:
                lines.append(f"错误: {', '.join(pull_report.errors)}")
            messagebox.showinfo("Sync pull", "\n".join(lines) or "完成", parent=self)
            self._on_sync_check()

        self._run_background("正在 sync pull…", task, on_success=on_success)

    def _on_init(self) -> None:
        root = self._require_repo()
        if not root:
            return
        base = self.external_base_entry.get().strip() or None

        def task() -> str:
            resolved = init_repo(root, base)
            return str(resolved)

        def on_success(resolved: object) -> None:
            messagebox.showinfo("完成", f"已初始化\n外部目录: {resolved}")
            self.refresh_all()

        self._run_background("正在初始化…", task, on_success=on_success)

    def _on_apply(self) -> None:
        root = self._require_repo()
        if not root:
            return

        def task() -> None:
            apply_all(root)

        def on_success(_: object) -> None:
            messagebox.showinfo("完成", "已应用 skip-worktree、链接、worktree 与 vendor 配置")
            self.refresh_all()

        self._run_background("正在应用配置…", task, on_success=on_success)

    def _on_doctor(self) -> None:
        root = self._require_repo()
        if not root:
            return
        self.tabs.set("概览")

        def task():
            return run_doctor(root)

        def on_success(report: object) -> None:
            self._render_overview(root, report)

        self._run_background("正在检查…", task, on_success=on_success)

    def _save_external_base(self) -> None:
        root = self._require_repo()
        if not root:
            return
        base = self.external_base_entry.get().strip()
        if not base:
            messagebox.showwarning("提示", "请输入外部目录路径")
            return
        resolved = link_mod.set_external_base(root, base)
        messagebox.showinfo("完成", f"外部根目录已保存:\n{resolved}")
        self.refresh_all()

    def _add_skip_dialog(self) -> None:
        root = self._require_repo()
        if not root:
            return
        path = self._ask_text("添加 Skip-worktree", "仓库内相对路径（文件或目录）:")
        if not path:
            return

        def task() -> None:
            skip_mod.add_skip(root, path)

        def on_success(_: object) -> None:
            self.refresh_all()

        self._run_background("正在添加 skip…", task, on_success=on_success)

    def _remove_skip_selection(self) -> None:
        root = self._require_repo()
        if not root:
            return
        path = self._selected_iid(self.skip_tree)
        if not path:
            return

        def task() -> None:
            skip_mod.remove_skip(root, path)

        self._run_background("正在移除 skip…", task, on_success=lambda _: self.refresh_all())

    def _add_link_dialog(self) -> None:
        root = self._require_repo()
        if not root:
            return
        path = self._ask_text("添加外部链接", "仓库内相对目录路径:")
        if not path:
            return
        external = self._ask_text("外部绝对路径（留空则使用默认外部根目录）", "", required=False)
        migrate = messagebox.askyesno("迁移", "若路径已存在，是否迁移内容到外部目录？")
        external_path = external or None
        link_type = resolve_link_type(None)

        def task() -> None:
            link_mod.add_link(
                root,
                path,
                external_path,
                link_type=link_type,
                migrate=migrate,
            )

        self._run_background("正在添加链接…", task, on_success=lambda _: self.refresh_all())

    def _remove_link_selection(self) -> None:
        root = self._require_repo()
        if not root:
            return
        path = self._selected_iid(self.link_tree)
        if not path:
            return
        delete_external = messagebox.askyesno("确认", "是否同时删除外部目录中的数据？")

        def task() -> None:
            link_mod.remove_link(root, path, keep_external=not delete_external)

        self._run_background("正在移除链接…", task, on_success=lambda _: self.refresh_all())

    def _add_worktree_dialog(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self._ask_text("添加 Worktree", "名称（例如 sandbox）:")
        if not name:
            return
        wt_path = filedialog.askdirectory(title="选择 worktree 目录")
        if not wt_path:
            return
        branch = self._ask_text("分支名（留空则使用当前分支）", "", required=False)
        new_branch = messagebox.askyesno("新分支", "是否创建新分支？")
        branch_name = branch or None

        def task() -> None:
            worktree_mod.add_worktree(
                root,
                name,
                wt_path,
                branch=branch_name,
                create_branch=new_branch,
            )

        self._run_background("正在添加 worktree…", task, on_success=lambda _: self.refresh_all())

    def _remove_worktree_selection(self) -> None:
        root = self._require_repo()
        if not root:
            return
        name = self._selected_iid(self.worktree_tree)
        if not name:
            return
        force = messagebox.askyesno("确认", "是否强制移除 worktree？")

        def task() -> None:
            worktree_mod.remove_worktree(root, name, force=force)

        self._run_background("正在移除 worktree…", task, on_success=lambda _: self.refresh_all())

    @staticmethod
    def _selected_iid(tree: ttk.Treeview) -> str | None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中一行")
            return None
        return selected[0]

    def _ask_text(self, title: str, prompt: str, *, required: bool = True) -> str | None:
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        value = dialog.get_input()
        if required and not value:
            return None
        return value.strip() if value else None


def main(repo_path: str | None = None) -> None:
    theme_mod.apply_app_defaults()
    app = GitMoveApp(repo_path=repo_path)
    app.mainloop()


if __name__ == "__main__":
    main()
