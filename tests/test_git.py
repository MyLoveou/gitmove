from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import git


def test_run_git_timeout() -> None:
    with mock.patch("gitmove.git.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("git", 30)):
        with pytest.raises(git.GitError, match="timed out"):
            git.run_git("status")


def test_ls_files_skip_worktree_parsing(git_repo: Path) -> None:
    git.update_index_skip(git_repo, "tracked.txt", skip=True)
    active = git.ls_files_skip_worktree(git_repo)
    assert "tracked.txt" in active


def test_ls_tracked_files(git_repo: Path) -> None:
    tracked = git.ls_tracked_files(git_repo)
    assert "tracked.txt" in tracked
    assert "config.local.json" in tracked
