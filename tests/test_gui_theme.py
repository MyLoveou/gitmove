"""Unit tests for GUI theme and scenario visual metadata."""

from __future__ import annotations

from gitmove.errors import catalog_error
from gitmove.gui.error_dialog import format_error_detail
from gitmove.gui import theme as theme_mod
from gitmove.gui.overview import doctor_counts, format_doctor_summary
from gitmove.gui.scenarios import SCENARIO_CARDS
from gitmove.doctor import DoctorIssue, DoctorReport


def test_theme_palette_has_accent_and_semantic_colors() -> None:
    palette = theme_mod.resolve_theme()
    assert palette.accent.startswith("#")
    assert palette.text_on_accent.startswith("#")
    assert palette.error.startswith("#")
    assert palette.success.startswith("#")
    assert palette.text_primary[0].startswith("#")


def test_theme_native_widget_kwargs_use_palette() -> None:
    entry = theme_mod.entry_kwargs()
    tab = theme_mod.tabview_kwargs()
    assert "fg_color" in entry
    assert "segmented_button_selected_color" in tab
    assert entry["border_color"] == theme_mod.resolve_theme().border


def test_level_tag_maps_doctor_levels() -> None:
    assert theme_mod.level_tag("error") == "error"
    assert theme_mod.level_tag("warn") == "warn"
    assert theme_mod.level_tag("info") == "info"


def test_scenario_cards_have_visual_fields() -> None:
    for card in SCENARIO_CARDS:
        assert len(card.index) == 2 and card.index.isdigit()
        assert card.title
        assert card.tag
        assert card.target_tab


def test_format_error_detail_lists_code_and_context() -> None:
    err = catalog_error("VENDOR_FF_BLOCKED", name="cursor-spec", ref="main", cache="/tmp/cache")
    detail = format_error_detail(err)
    assert "VENDOR_FF_BLOCKED" in detail
    assert "cursor-spec" in detail
    assert "/tmp/cache" in detail


def test_doctor_counts_and_summary_align() -> None:
    report = DoctorReport(
        issues=[
            DoctorIssue("error", "link", "x"),
            DoctorIssue("warn", "vendor", "y"),
            DoctorIssue("info", "general", "z"),
        ]
    )
    assert doctor_counts(report) == (1, 1, 1)
    summary = format_doctor_summary(report)
    assert "1" in summary
    assert "错误" in summary
