"""Unit tests for GUI scenario cards (T-G1)."""

from __future__ import annotations

from gitmove.gui.scenarios import SCENARIO_CARDS, get_scenario, scenario_ids


def test_scenario_cards_has_six_entries() -> None:
    assert len(SCENARIO_CARDS) == 6


def test_scenario_ids_are_unique() -> None:
    assert len(scenario_ids()) == len(set(scenario_ids()))


def test_get_scenario_skip_targets_skip_tab() -> None:
    card = get_scenario("skip_tracked")
    assert card is not None
    assert card.target_tab == "Skip-worktree"


def test_get_scenario_vendor_targets_vendor_tab() -> None:
    card = get_scenario("vendor_upstream")
    assert card is not None
    assert card.target_tab == "Vendor"


def test_get_scenario_unknown_returns_none() -> None:
    assert get_scenario("missing") is None
