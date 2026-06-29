from __future__ import annotations

from pathlib import Path
from unittest import mock

from gitmove import skip as skip_mod
from gitmove import worktree as worktree_mod
from gitmove.config import WorktreeEntry


def test_apply_worktrees_does_not_mark_unregistered_directory(git_repo: Path) -> None:
    orphan = git_repo.parent / "orphan-worktree"
    orphan.mkdir()
    cfg = skip_mod.load_config(git_repo)
    cfg.worktrees = [WorktreeEntry(name="orphan", path=str(orphan), branch=None)]
    skip_mod.save_config(git_repo, cfg)

    with mock.patch.object(worktree_mod, "add_worktree") as add_mock:
        add_mock.side_effect = lambda root, name, path, **kwargs: worktree_mod.WorktreeStatus(
            name=name,
            path=str(orphan.resolve()),
            branch=None,
            exists=True,
            registered=True,
        )
        results = worktree_mod.apply_worktrees(git_repo)

    add_mock.assert_called_once()
    assert results[0].registered is True


def test_list_worktrees_registered_flag(git_repo: Path) -> None:
    main = str(git_repo.resolve())
    registered = worktree_mod._registered_paths(git_repo)
    assert main in registered
