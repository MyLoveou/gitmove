"""GUI UX integration tests (Phase 1)."""

from __future__ import annotations

import os
import sys
from unittest import mock

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "linux" and not os.environ.get("DISPLAY"),
    reason="GUI tests need DISPLAY or xvfb-run",
)

tkinter = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")

from gitmove.gui.app import GitMoveApp  # noqa: E402
from gitmove.gui.empty_state import get_empty_state  # noqa: E402


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
        except tkinter.TclError:
            pass


def test_navigate_scenario_switches_tab(gui_app: GitMoveApp) -> None:
    gui_app.navigate_to_scenario("vendor_upstream")
    assert gui_app.tabs.get() == "Vendor"


def test_empty_state_skip_has_guidance() -> None:
    state = get_empty_state("Skip-worktree")
    assert state is not None
    assert "Git 追踪" in state.body
    assert "外部链接" in state.not_for
