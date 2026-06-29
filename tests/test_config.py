from __future__ import annotations

from pathlib import Path

import pytest

from gitmove.config import GitMoveConfig, config_path_for_repo, resolve_repo_path


def test_resolve_repo_path_accepts_relative_file(git_repo: Path) -> None:
    resolved = resolve_repo_path(git_repo, "tracked.txt")
    assert resolved == (git_repo / "tracked.txt").resolve()


def test_resolve_repo_path_rejects_parent_segment(git_repo: Path) -> None:
    with pytest.raises(ValueError, match="stay inside repository"):
        resolve_repo_path(git_repo, "../outside.txt")


def test_resolve_repo_path_rejects_absolute(git_repo: Path) -> None:
    with pytest.raises(ValueError, match="stay inside repository"):
        resolve_repo_path(git_repo, str(git_repo / "tracked.txt"))


def test_config_roundtrip(git_repo: Path) -> None:
    cfg = GitMoveConfig(
        skip_paths=["config.local.json"],
        external_base=str(git_repo / "external"),
        links=[],
        worktrees=[],
    )
    path = config_path_for_repo(git_repo)
    cfg.save(path)
    loaded = GitMoveConfig.load(path)
    assert loaded.skip_paths == ["config.local.json"]
    assert loaded.external_base == str(git_repo / "external")
