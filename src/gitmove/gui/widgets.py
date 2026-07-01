"""Reusable styled widgets for the gitmove GUI."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk
from tkinter import ttk

from gitmove.gui.empty_state import EmptyStateCopy
from gitmove.gui.scenarios import ScenarioCard
from gitmove.gui import theme as theme_mod


class ElevatedPanel(ctk.CTkFrame):
    """Raised surface with subtle border — sidebar, cards, inputs."""

    def __init__(self, master, **kwargs) -> None:
        palette = theme_mod.resolve_theme()
        defaults = {
            "fg_color": palette.surface_elevated,
            "corner_radius": theme_mod.RADIUS["md"],
            "border_width": 1,
            "border_color": palette.border,
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class PageHeader(ctk.CTkFrame):
    """Title + optional subtitle for a tab page."""

    def __init__(
        self,
        master,
        title: str,
        *,
        subtitle: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        palette = theme_mod.resolve_theme()
        ctk.CTkLabel(self, text=title, font=theme_mod.font_section(), anchor="w").pack(
            anchor="w"
        )
        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=theme_mod.font_caption(),
                text_color=palette.text_muted,
                anchor="w",
                wraplength=680,
                justify="left",
            ).pack(anchor="w", pady=(theme_mod.SPACING["xs"], 0))


def primary_button(master, **kwargs) -> ctk.CTkButton:
    palette = theme_mod.resolve_theme()
    defaults = {
        "fg_color": palette.accent,
        "hover_color": palette.accent_hover,
        "text_color": palette.text_on_accent,
        "font": theme_mod.font_body(),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(master, **defaults)


def secondary_button(master, **kwargs) -> ctk.CTkButton:
    palette = theme_mod.resolve_theme()
    defaults = {
        "fg_color": palette.surface_secondary,
        "border_width": 1,
        "border_color": palette.border,
        "hover_color": palette.surface_elevated,
        "text_color": palette.text_primary,
        "font": theme_mod.font_body(),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(master, **defaults)


def destructive_button(master, **kwargs) -> ctk.CTkButton:
    palette = theme_mod.resolve_theme()
    defaults = {
        "fg_color": palette.error,
        "hover_color": palette.error,
        "text_color": palette.text_on_accent,
        "font": theme_mod.font_body(),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(master, **defaults)


class ScenarioCardWidget(ctk.CTkFrame):
    """Clickable scenario entry — typography hierarchy, hairline border."""

    def __init__(
        self,
        master,
        card: ScenarioCard,
        *,
        command: Callable[[], None],
        **kwargs,
    ) -> None:
        palette = theme_mod.resolve_theme()
        super().__init__(
            master,
            fg_color=palette.surface_elevated,
            corner_radius=theme_mod.RADIUS["md"],
            border_width=1,
            border_color=palette.border,
            **kwargs,
        )
        self._card = card
        self._command = command
        self._hover_depth = 0

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=theme_mod.SPACING["sm"], pady=theme_mod.SPACING["sm"])

        text_col = ctk.CTkFrame(body, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_col,
            text=card.index,
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_col,
            text=card.title,
            font=theme_mod.font_body(),
            anchor="w",
        ).pack(anchor="w", pady=(theme_mod.SPACING["xs"], 0))

        ctk.CTkLabel(
            text_col,
            text=card.subtitle,
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
            anchor="w",
            justify="left",
            wraplength=200,
        ).pack(anchor="w", pady=(theme_mod.SPACING["xs"], theme_mod.SPACING["xs"]))

        ctk.CTkLabel(
            text_col,
            text=f"→ {card.tag}",
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
            anchor="w",
        ).pack(anchor="w")

        for widget in (self, body, text_col):
            self._bind_interactive_recursive(widget)

    def _bind_interactive_recursive(self, widget) -> None:
        widget.bind("<Button-1>", self._on_click)
        widget.bind("<Enter>", self._on_pointer_enter)
        widget.bind("<Leave>", self._on_pointer_leave)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            self._bind_interactive_recursive(child)

    def _on_click(self, _event=None) -> None:
        self._command()

    def _on_pointer_enter(self, _event=None) -> None:
        self._hover_depth += 1
        if self._hover_depth == 1:
            palette = theme_mod.resolve_theme()
            self.configure(border_color=palette.text_primary)

    def _on_pointer_leave(self, _event=None) -> None:
        self._hover_depth = max(0, self._hover_depth - 1)
        if self._hover_depth == 0:
            palette = theme_mod.resolve_theme()
            self.configure(border_color=palette.border)


class HealthSummaryBar(ctk.CTkFrame):
    """Error / warn / info counts — inline typography, semantic color when non-zero."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._error_var = ctk.StringVar(value="0 错误")
        self._warn_var = ctk.StringVar(value="0 警告")
        self._info_var = ctk.StringVar(value="0 提示")
        self._labels: dict[str, ctk.CTkLabel] = {}
        for key, var in (
            ("error", self._error_var),
            ("warn", self._warn_var),
            ("info", self._info_var),
        ):
            label = ctk.CTkLabel(
                self,
                textvariable=var,
                font=theme_mod.font_body(),
            )
            label.pack(side="left", padx=(0, theme_mod.SPACING["md"]))
            self._labels[key] = label
        self.set_counts(0, 0, 0)

    def set_counts(self, errors: int, warns: int, infos: int) -> None:
        palette = theme_mod.resolve_theme()
        self._error_var.set(f"{errors} 错误")
        self._warn_var.set(f"{warns} 警告")
        self._info_var.set(f"{infos} 提示")
        self._labels["error"].configure(
            text_color=palette.text_muted if errors == 0 else palette.error,
        )
        self._labels["warn"].configure(
            text_color=palette.text_muted if warns == 0 else palette.warning,
        )
        self._labels["info"].configure(
            text_color=palette.text_muted if infos == 0 else palette.info,
        )


class EmptyStatePanel(ElevatedPanel):
    """Structured empty state — title, body, and muted exclusion note."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        palette = theme_mod.resolve_theme()
        text_col = ctk.CTkFrame(self, fg_color="transparent")
        text_col.pack(fill="x", padx=theme_mod.SPACING["md"], pady=theme_mod.SPACING["md"])

        self._title = ctk.CTkLabel(
            text_col,
            text="",
            font=theme_mod.font_body(),
            anchor="w",
        )
        self._title.pack(anchor="w")
        self._body = ctk.CTkLabel(
            text_col,
            text="",
            font=theme_mod.font_caption(),
            anchor="w",
            justify="left",
            wraplength=640,
        )
        self._body.pack(anchor="w", pady=(theme_mod.SPACING["xs"], 0))
        self._not_for = ctk.CTkLabel(
            text_col,
            text="",
            font=theme_mod.font_caption(),
            text_color=palette.text_muted,
            anchor="w",
            justify="left",
            wraplength=640,
        )
        self._not_for.pack(anchor="w", pady=(theme_mod.SPACING["xs"], 0))

    def apply_copy(self, copy: EmptyStateCopy | None) -> None:
        if copy is None:
            self.pack_forget()
            return
        self._title.configure(text=copy.title)
        self._body.configure(text=copy.body)
        self._not_for.configure(text=f"不适用：{copy.not_for.removeprefix('不适用：')}")
        if not self.winfo_ismapped():
            self.pack(fill="x", pady=(theme_mod.SPACING["sm"], 0))

    def hide(self) -> None:
        self.pack_forget()


def build_scenario_grid(
    master,
    cards: tuple[ScenarioCard, ...],
    *,
    on_select: Callable[[str], None],
    columns: int = 3,
) -> ctk.CTkFrame:
    grid = ctk.CTkFrame(master, fg_color="transparent")
    grid.pack(fill="x")
    for index, card in enumerate(cards):
        row, col = divmod(index, columns)
        widget = ScenarioCardWidget(
            grid,
            card,
            command=lambda scenario_id=card.id: on_select(scenario_id),
        )
        widget.grid(
            row=row,
            column=col,
            padx=theme_mod.SPACING["sm"],
            pady=theme_mod.SPACING["sm"],
            sticky="nsew",
        )
        grid.grid_columnconfigure(col, weight=1)
    return grid
