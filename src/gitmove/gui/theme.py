"""Visual design tokens and styling helpers for the gitmove GUI."""



from __future__ import annotations



from dataclasses import dataclass



import customtkinter as ctk

from tkinter import ttk





@dataclass(frozen=True)

class ThemePalette:

    accent: str

    accent_hover: str

    text_on_accent: str

    surface: tuple[str, str]

    surface_elevated: tuple[str, str]

    surface_secondary: tuple[str, str]

    border: tuple[str, str]

    text_primary: tuple[str, str]

    text_muted: tuple[str, str]

    error: str

    warning: str

    success: str

    info: str





LIGHT = ThemePalette(

    accent="#141414",

    accent_hover="#2A2A2A",

    text_on_accent="#FFFFFF",

    surface=("#FAFAFA", "#FAFAFA"),

    surface_elevated=("#FFFFFF", "#FFFFFF"),

    surface_secondary=("#F5F5F5", "#F5F5F5"),

    border=("#E0E0E0", "#E0E0E0"),

    text_primary=("#141414", "#141414"),

    text_muted=("#6B6B6B", "#6B6B6B"),

    error="#8B2E2E",

    warning="#7A5C12",

    success="#2D5A3D",

    info="#4A5568",

)



DARK = ThemePalette(

    accent="#F0F0F0",

    accent_hover="#D8D8D8",

    text_on_accent="#141414",

    surface=("#0D0D0D", "#0D0D0D"),

    surface_elevated=("#141414", "#141414"),

    surface_secondary=("#1A1A1A", "#1A1A1A"),

    border=("#2E2E2E", "#2E2E2E"),

    text_primary=("#F5F5F5", "#F5F5F5"),

    text_muted=("#9A9A9A", "#9A9A9A"),

    error="#C47070",

    warning="#C4A84A",

    success="#6B9E7A",

    info="#8A9AAA",

)



SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}

RADIUS = {"sm": 4, "md": 6, "lg": 8}





def is_dark_mode() -> bool:

    mode = ctk.get_appearance_mode()

    return mode == "Dark" or (mode == "System" and _system_prefers_dark())





def _system_prefers_dark() -> bool:

    try:

        import tkinter as tk



        root = tk.Tk()

        root.withdraw()

        try:

            result = root.tk.call("tk", "windowingsystem")

        finally:

            root.destroy()

        if result == "win32":

            import winreg



            key = winreg.OpenKey(

                winreg.HKEY_CURRENT_USER,

                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",

            )

            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")

            winreg.CloseKey(key)

            return value == 0

    except OSError:

        pass

    return True





def resolve_theme() -> ThemePalette:

    return DARK if is_dark_mode() else LIGHT





def pick(pair: tuple[str, str]) -> str:

    return pair[1] if is_dark_mode() else pair[0]





def font_title() -> ctk.CTkFont:

    return ctk.CTkFont(size=18, weight="bold")





def font_section() -> ctk.CTkFont:

    return ctk.CTkFont(size=15, weight="bold")





def font_body() -> ctk.CTkFont:

    return ctk.CTkFont(size=13)





def font_caption() -> ctk.CTkFont:

    return ctk.CTkFont(size=11)





def font_tree_heading() -> ctk.CTkFont:

    return ctk.CTkFont(size=11, weight="bold")





def apply_app_defaults() -> None:

    ctk.set_appearance_mode("System")

    ctk.set_widget_scaling(1.0)





def entry_kwargs(**overrides) -> dict:

    palette = resolve_theme()

    defaults = {

        "fg_color": palette.surface_elevated,

        "border_color": palette.border,

        "text_color": palette.text_primary,

        "placeholder_text_color": palette.text_muted,

    }

    defaults.update(overrides)

    return defaults





def tabview_kwargs(**overrides) -> dict:

    palette = resolve_theme()

    defaults = {

        "fg_color": palette.surface,

        "segmented_button_fg_color": palette.surface_secondary,

        "segmented_button_selected_color": palette.accent,

        "segmented_button_selected_hover_color": palette.accent_hover,

        "segmented_button_unselected_color": palette.surface_secondary,

        "segmented_button_unselected_hover_color": palette.surface_elevated,

        "text_color": palette.text_primary,

    }

    defaults.update(overrides)

    return defaults





def combobox_kwargs(**overrides) -> dict:

    palette = resolve_theme()

    defaults = {

        "fg_color": palette.surface_elevated,

        "border_color": palette.border,

        "button_color": palette.surface_secondary,

        "button_hover_color": palette.surface_elevated,

        "dropdown_fg_color": palette.surface_elevated,

        "dropdown_text_color": palette.text_primary,

        "text_color": palette.text_primary,

    }

    defaults.update(overrides)

    return defaults





def textbox_kwargs(**overrides) -> dict:

    palette = resolve_theme()

    defaults = {

        "fg_color": palette.surface_elevated,

        "border_color": palette.border,

        "text_color": palette.text_primary,

    }

    defaults.update(overrides)

    return defaults





def checkbox_kwargs(**overrides) -> dict:

    palette = resolve_theme()

    defaults = {

        "fg_color": palette.surface_elevated,

        "border_color": palette.border,

        "text_color": palette.text_primary,

        "hover_color": palette.surface_secondary,

    }

    defaults.update(overrides)

    return defaults





def style_treeview(style: ttk.Style | None = None) -> ttk.Style:

    theme = resolve_theme()

    style = style or ttk.Style()

    style.theme_use("clam")

    bg = pick(theme.surface_elevated)

    fg = pick(theme.text_primary)

    style.configure(

        "Treeview",

        background=bg,

        foreground=fg,

        fieldbackground=bg,

        rowheight=28,

        borderwidth=0,

    )

    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    return style





def configure_level_tags(tree: ttk.Treeview) -> None:

    theme = resolve_theme()

    tree.tag_configure("error", foreground=theme.error)

    tree.tag_configure("warn", foreground=theme.warning)

    tree.tag_configure("info", foreground=theme.info)





def level_tag(level: str) -> str:

    if level == "error":

        return "error"

    if level == "warn":

        return "warn"

    return "info"

