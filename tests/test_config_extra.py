from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove.config import GitMoveConfig, LinkEntry, WorktreeEntry, config_path_for_repo


def test_load_config_with_links_and_worktrees(git_repo: Path) -> None:
    cfg = GitMoveConfig(
        skip_paths=["tracked.txt"],
        external_base="",
        links=[LinkEntry("tools/personal", "/tmp/external", "symlink")],
        worktrees=[WorktreeEntry("sandbox", "/tmp/sandbox", "dev")],
    )
    path = config_path_for_repo(git_repo)
    cfg.save(path)
    loaded = GitMoveConfig.load(path)
    assert loaded.links[0].repo_path == "tools/personal"
    assert loaded.worktrees[0].name == "sandbox"


def test_load_empty_config(git_repo: Path) -> None:
    assert GitMoveConfig.load(config_path_for_repo(git_repo)) == GitMoveConfig()
