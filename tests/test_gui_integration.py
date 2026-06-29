"""GUI integration tests (requires Tk; Linux CI uses xvfb)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "linux" and not os.environ.get("DISPLAY"),
    reason="GUI tests need DISPLAY or xvfb-run",
)

tkinter = pytest.importorskip("tkinter")
customtkinter = pytest.importorskip("customtkinter")

from gitmove.doctor import DoctorIssue, DoctorReport  # noqa: E402
from gitmove.gui.app import GitMoveApp  # noqa: E402
from gitmove import skip as skip_mod  # noqa: E402


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


def _wait_until(app: GitMoveApp, predicate, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            app.update()
        except tkinter.TclError:
            break
        if predicate():
            return
        time.sleep(0.02)
    raise TimeoutError("condition not met before timeout")


def test_gui_refresh_renders_skip_rows(gui_app: GitMoveApp, git_repo: Path) -> None:
    skip_mod.add_skip(git_repo, "tracked.txt")
    gui_app.repo_root = git_repo.resolve()
    gui_app.refresh_all()
    _wait_until(gui_app, lambda: not gui_app._busy)
    _wait_until(gui_app, lambda: "tracked.txt" in gui_app.skip_tree.get_children())


def test_gui_refresh_updates_status(gui_app: GitMoveApp, git_repo: Path) -> None:
    gui_app.repo_root = git_repo.resolve()
    gui_app.refresh_all()
    _wait_until(gui_app, lambda: not gui_app._busy)
    assert "已加载" in gui_app._status_var.get()


def test_gui_render_overview(gui_app: GitMoveApp, git_repo: Path) -> None:
    report = DoctorReport(issues=[DoctorIssue("info", "general", "所有检查通过")])
    gui_app._render_overview(git_repo, report)
    assert "所有检查通过" in gui_app.overview_text.get("1.0", "end")


def test_gui_busy_ignores_duplicate_jobs(gui_app: GitMoveApp, git_repo: Path) -> None:
    calls: list[str] = []

    def task(name: str):
        def _inner() -> str:
            calls.append(name)
            time.sleep(0.2)
            return name

        return _inner

    gui_app.repo_root = git_repo.resolve()
    gui_app._run_background("first", task("first"))
    _wait_until(gui_app, lambda: gui_app._busy)
    gui_app._run_background("second", task("second"))
    _wait_until(gui_app, lambda: not gui_app._busy)
    assert calls == ["first"]
