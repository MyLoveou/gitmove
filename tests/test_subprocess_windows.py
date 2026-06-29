"""Windows subprocess visibility and git call consolidation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from gitmove import git
from gitmove.doctor import init_repo, run_doctor
from gitmove.platform_util import subprocess_no_window_kwargs
from gitmove import skip as skip_mod


def test_subprocess_no_window_kwargs_on_windows() -> None:
    with mock.patch("gitmove.platform_util.sys.platform", "win32"):
        assert subprocess_no_window_kwargs() == {
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }


def test_subprocess_no_window_kwargs_off_windows() -> None:
    with mock.patch("gitmove.platform_util.sys.platform", "linux"):
        assert subprocess_no_window_kwargs() == {}


def test_run_git_passes_no_window_flags_on_windows() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch("gitmove.platform_util.sys.platform", "win32"):
        with mock.patch("gitmove.git.subprocess.run", return_value=completed) as run:
            git.run_git("status")
            assert run.call_args.kwargs.get("creationflags") == subprocess.CREATE_NO_WINDOW


def test_ls_files_index(git_repo: Path) -> None:
    git.update_index_skip(git_repo, "tracked.txt", skip=True)
    skip_active, tracked = git.ls_files_index(git_repo)
    assert "tracked.txt" in skip_active
    assert "tracked.txt" in tracked
    assert "config.local.json" in tracked
    assert "config.local.json" not in skip_active


def test_list_status_uses_single_ls_files_index(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "tracked.txt")
    with mock.patch("gitmove.skip.git.ls_files_index", wraps=git.ls_files_index) as index:
        with mock.patch("gitmove.skip.git.ls_files_skip_worktree") as legacy_skip:
            with mock.patch("gitmove.skip.git.ls_tracked_files") as legacy_tracked:
                skip_mod.list_status(git_repo)
                index.assert_called_once()
                legacy_skip.assert_not_called()
                legacy_tracked.assert_not_called()


def test_run_doctor_reuses_precomputed_items(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_items = skip_mod.list_status(git_repo)
    link_items: list = []
    wt_items: list = []

    with mock.patch("gitmove.doctor.skip_mod.list_status") as mock_skip:
        with mock.patch("gitmove.doctor.link_mod.list_links") as mock_link:
            with mock.patch("gitmove.doctor.worktree_mod.list_worktrees") as mock_wt:
                run_doctor(
                    git_repo,
                    skip_items=skip_items,
                    link_items=link_items,
                    wt_items=wt_items,
                )
                mock_skip.assert_not_called()
                mock_link.assert_not_called()
                mock_wt.assert_not_called()
