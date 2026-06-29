from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import skip as skip_mod
from gitmove import worktree as worktree_mod
from gitmove.config import WorktreeEntry
from gitmove import git


def test_remove_worktree(git_repo: Path) -> None:
    cfg = skip_mod.load_config(git_repo)
    cfg.worktrees = [WorktreeEntry("sandbox", str(git_repo.parent / "wt"), None)]
    skip_mod.save_config(git_repo, cfg)

    with mock.patch.object(git, "run_git") as run_mock:
        worktree_mod.remove_worktree(git_repo, "sandbox")
    run_mock.assert_called()


def test_remove_worktree_unknown(git_repo: Path) -> None:
    with pytest.raises(KeyError):
        worktree_mod.remove_worktree(git_repo, "missing")


def test_add_worktree_invokes_git(git_repo: Path, tmp_path: Path) -> None:
    destination = tmp_path / "wt"
    with mock.patch.object(git, "run_git") as run_mock:
        with mock.patch.object(worktree_mod, "_registered_paths", return_value={str(destination.resolve())}):
            status = worktree_mod.add_worktree(git_repo, "sandbox", str(destination), create_branch=True)
    assert status.name == "sandbox"
    run_mock.assert_called()
