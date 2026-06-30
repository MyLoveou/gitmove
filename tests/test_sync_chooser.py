"""Tests for GUI sync strategy chooser."""

from __future__ import annotations

from unittest import mock

from gitmove.gui.sync_chooser import gui_file_chooser
from gitmove.sync import SyncDrift, SyncStrategy


def _drift(**overrides) -> SyncDrift:
    base = {
        "path": "rules.md",
        "local_modified": False,
        "remote_modified": False,
        "skip_active": True,
        "in_config": True,
    }
    base.update(overrides)
    return SyncDrift(**base)


def test_gui_file_chooser_offers_merge_when_both_modified() -> None:
    drift = _drift(local_modified=True, remote_modified=True)
    parent = mock.Mock()
    with mock.patch("gitmove.gui.sync_chooser._ask_local_modified_strategy") as ask:
        ask.return_value = SyncStrategy.MERGE
        result = gui_file_chooser(parent, drift)
    ask.assert_called_once_with(parent, drift)
    assert result is SyncStrategy.MERGE


def test_gui_file_chooser_remote_only() -> None:
    drift = _drift(remote_modified=True)
    parent = mock.Mock()
    with mock.patch("gitmove.gui.sync_chooser.messagebox.askyesno", return_value=True):
        assert gui_file_chooser(parent, drift) is SyncStrategy.REMOTE
