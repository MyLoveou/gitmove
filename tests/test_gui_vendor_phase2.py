"""GUI integration tests for Vendor Phase 2."""

from __future__ import annotations

import os
import sys
from unittest import mock

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "linux" and not os.environ.get("DISPLAY"),
    reason="GUI tests need DISPLAY or xvfb-run",
)

pytest.importorskip("customtkinter")

from gitmove.gui.app import GitMoveApp  # noqa: E402


@pytest.fixture(scope="module")
def gui_app(tmp_path_factory):
    non_repo = tmp_path_factory.mktemp("not-a-repo")
    with (
        mock.patch("gitmove.gui.app.messagebox.showinfo"),
        mock.patch("gitmove.gui.app.messagebox.showerror"),
        mock.patch("gitmove.gui.app.messagebox.showwarning"),
    ):
        app = GitMoveApp(repo_path=str(non_repo))
        app.withdraw()
        app.update()
        yield app
        try:
            app.destroy()
        except Exception:
            pass


def test_vendor_tab_has_add_button(gui_app: GitMoveApp) -> None:
    gui_app.tabs.set("Vendor")
    assert hasattr(gui_app, "_open_vendor_add_dialog")


def test_vendor_tab_has_sync_and_remove_handlers(gui_app: GitMoveApp) -> None:
    assert hasattr(gui_app, "_on_vendor_sync_selected")
    assert hasattr(gui_app, "_on_vendor_remove_selected")
    assert hasattr(gui_app, "_on_vendor_check_updates")
