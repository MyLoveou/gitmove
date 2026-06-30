"""GUI tests for multi-project sidebar."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "linux" and not os.environ.get("DISPLAY"),
    reason="GUI tests need DISPLAY or xvfb-run",
)

customtkinter = pytest.importorskip("customtkinter")
tkinter = pytest.importorskip("tkinter")

from gitmove.gui.app import GitMoveApp  # noqa: E402
from gitmove.registry import add_project, list_projects  # noqa: E402


@pytest.fixture
def registry_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "gitmove-home"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_HOME", str(home))
    return home


@pytest.fixture
def gui_with_registry(registry_home: Path, git_repo: Path, tmp_path: Path):
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()
    add_project(git_repo, alias="main", group="test")
    with (
        mock.patch("gitmove.gui.app.messagebox.showinfo"),
        mock.patch("gitmove.gui.app.messagebox.showerror"),
        mock.patch("gitmove.gui.app.messagebox.showwarning"),
    ):
        try:
            app = GitMoveApp(repo_path=str(non_repo))
        except tkinter.TclError as exc:
            pytest.skip(f"Tk not available: {exc}")
        app.withdraw()
        app.update()
        yield app
        try:
            app.destroy()
        except Exception:
            pass


def test_gui_sidebar_lists_registered_projects(gui_with_registry: GitMoveApp) -> None:
    assert "main" in gui_with_registry._project_buttons
    assert len(list_projects()) == 1


def test_gui_select_registered_alias_updates_repo(gui_with_registry: GitMoveApp, git_repo: Path) -> None:
    gui_with_registry._select_registered_alias("main")
    assert gui_with_registry.repo_root == git_repo.resolve()
    assert gui_with_registry._selected_alias == "main"
