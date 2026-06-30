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
from gitmove import link as link_mod
from gitmove import projects as projects_mod
from gitmove.registry import RegistryError, add_project, list_projects, load_registry, remove_project, touch_last_used
from gitmove.platform_util import default_link_type, platform_label, resolve_link_type
from gitmove import skip as skip_mod
from gitmove import worktree as worktree_mod


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
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        sidebar = ctk.CTkFrame(body, width=220)
        sidebar.pack(side="left", fill="y", padx=(0, 8))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="项目", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self._project_list_frame = ctk.CTkScrollableFrame(sidebar, width=200, height=360)
        self._project_list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        side_actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        side_actions.pack(fill="x", padx=6, pady=(4, 8))
        ctk.CTkButton(side_actions, text="添加项目", command=self._add_registered_project).pack(
            fill="x", pady=2
        )
        ctk.CTkButton(side_actions, text="从当前目录添加", command=self._add_current_repo).pack(
            fill="x", pady=2
        )
        ctk.CTkButton(side_actions, text="移除项目", command=self._remove_registered_project).pack(
            fill="x", pady=2
        )
        ctk.CTkButton(side_actions, text="全部 doctor", command=self._batch_doctor).pack(
            fill="x", pady=2
        )
        ctk.CTkButton(side_actions, text="全部 apply", command=self._batch_apply).pack(
            fill="x", pady=2
        )

        main_panel = ctk.CTkFrame(body, fg_color="transparent")
        main_panel.pack(side="left", fill="both", expand=True)

        header = ctk.CTkFrame(main_panel, corner_radius=0)
        header.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(header, text="Git 仓库", font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=(8, 8)
        )
        self.repo_entry = ctk.CTkEntry(header, width=520, placeholder_text="仓库根目录")
        self.repo_entry.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(header, text="选择仓库", width=100, command=self._pick_repo).pack(
            side="left", padx=4
        )
        ctk.CTkButton(header, text="刷新", width=72, command=self.refresh_all).pack(
            side="left", padx=4
        )

        toolbar = ctk.CTkFrame(main_panel, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(toolbar, text="初始化", command=self._on_init).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="一键应用", command=self._on_apply).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="健康检查", command=self._on_doctor).pack(side="left", padx=4)
        self._toolbar_buttons.extend(
            btn
            for btn in toolbar.winfo_children()
            if isinstance(btn, ctk.CTkButton)
        )
        ctk.CTkLabel(
            toolbar,
            text=f"平台: {platform_label()} · 默认链接: {default_link_type()}",
            text_color="gray60",
        ).pack(side="right", padx=8)

        self.tabs = ctk.CTkTabview(main_panel)
        self.tabs.pack(fill="both", expand=True, pady=6)

        self.tab_overview = self.tabs.add("概览")
        self.tab_skip = self.tabs.add("Skip-worktree")
        self.tab_link = self.tabs.add("外部链接")
        self.tab_worktree = self.tabs.add("Worktree")

        self._build_overview_tab()
        self._build_skip_tab()
        self._build_link_tab()
        self._build_worktree_tab()

        status = ctk.CTkLabel(self, textvariable=self._status_var, anchor="w")
        status.pack(fill="x", padx=16, pady=(0, 10))

    def _build_overview_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_overview, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(frame, text="健康检查结果", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", pady=(0, 8)
        )
        self.overview_text = ctk.CTkTextbox(frame, height=220)
        self.overview_text.pack(fill="x", pady=(0, 12))
        self.overview_text.configure(state="disabled")

        ctk.CTkLabel(frame, text="外部目录默认根路径", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w"
        )
        base_row = ctk.CTkFrame(frame, fg_color="transparent")
        base_row.pack(fill="x", pady=6)
        self.external_base_entry = ctk.CTkEntry(base_row, placeholder_text="~/gitmove-external/<repo>")
        self.external_base_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(base_row, text="保存", width=80, command=self._save_external_base).pack(
            side="left"
        )

    def _build_skip_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_skip,
            tree_attr="skip_tree",
            columns=("path", "tracked", "skip", "config"),
            headings=("路径", "已追踪", "Skip 生效", "在配置中"),
            add_handler=self._add_skip_dialog,
            remove_handler=self._remove_skip_selection,
        )

    def _build_link_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_link,
            tree_attr="link_tree",
            columns=("repo", "external", "type", "ok"),
            headings=("仓库路径", "外部路径", "类型", "状态"),
            add_handler=self._add_link_dialog,
            remove_handler=self._remove_link_selection,
        )

    def _build_worktree_tab(self) -> None:
        self._build_data_tab(
            parent=self.tab_worktree,
            tree_attr="worktree_tree",
            columns=("name", "path", "branch", "registered"),
            headings=("名称", "路径", "分支", "已注册"),
            add_handler=self._add_worktree_dialog,
            remove_handler=self._remove_worktree_selection,
        )

    def _build_data_tab(
        self,
        *,
        parent: ctk.CTkFrame,
        tree_attr: str,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        add_handler: Callable[[], None],
        remove_handler: Callable[[], None],
    ) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(btn_row, text="添加", width=90, command=add_handler).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="移除选中", width=100, command=remove_handler).pack(
            side="left", padx=4
        )

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)

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

    def _style_treeviews(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        bg = "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#f2f2f2"
        fg = "#eeeeee" if ctk.get_appearance_mode() == "Dark" else "#1a1a1a"
        style.configure(
            "Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            rowheight=26,
            borderwidth=0,
        )
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _reload_project_sidebar(self) -> None:
        if self._project_list_frame is None:
            return
        for child in self._project_list_frame.winfo_children():
            child.destroy()
        self._project_buttons.clear()
        for entry in list_projects():
            label = entry.alias if not entry.group else f"{entry.alias} ({entry.group})"
            btn = ctk.CTkButton(
                self._project_list_frame,
                text=label,
                anchor="w",
                fg_color=("gray75", "gray25")
                if entry.alias == self._selected_alias
                else None,
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
                messagebox.showerror("错误", str(payload))
                return
            if on_success:
                on_success(payload)

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, poll)

    def refresh_all(self) -> None:
        root = self._require_repo()
        if not root:
            return

        def task() -> Path:
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
            return (root, cfg, skip_items, link_items, wt_items, report, external)

        def on_success(payload: object) -> None:
            root, cfg, skip_items, link_items, wt_items, report, external = payload  # type: ignore[misc]
            self.external_base_entry.delete(0, "end")
            self.external_base_entry.insert(0, external)
            self._render_skip(skip_items)
            self._render_links(link_items)
            self._render_worktrees(wt_items)
            self._render_overview(root, report)
            self._update_status(f"已加载: {root}")

        self._run_background("正在刷新…", task, on_success=on_success)

    def _render_overview(self, root: Path, report) -> None:
        lines: list[str] = []
        if config_path_for_repo(root).exists():
            lines.append(f"配置文件: {config_path_for_repo(root)}")
        else:
            lines.append("配置文件: 未初始化")
        lines.append(f"错误: {report.error_count}  警告: {report.warn_count}")
        lines.append("")
        for issue in report.issues:
            prefix = {"error": "[错误]", "warn": "[警告]", "info": "[信息]"}.get(issue.level, "")
            lines.append(f"{prefix} ({issue.category}) {issue.message}")
        self._set_text(self.overview_text, "\n".join(lines))

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
            messagebox.showinfo("完成", "已应用 skip-worktree、链接与 worktree 配置")
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

    @staticmethod
    def _set_text(widget: ctk.CTkTextbox, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _ask_text(self, title: str, prompt: str, *, required: bool = True) -> str | None:
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        value = dialog.get_input()
        if required and not value:
            return None
        return value.strip() if value else None


def main(repo_path: str | None = None) -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = GitMoveApp(repo_path=repo_path)
    app.mainloop()


if __name__ == "__main__":
    main()
