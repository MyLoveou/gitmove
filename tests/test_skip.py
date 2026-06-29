from __future__ import annotations

from pathlib import Path

import pytest

from gitmove import skip as skip_mod
from gitmove.config import config_path_for_repo


def test_add_skip_tracked_file(git_repo: Path) -> None:
    skip_mod.save_config(git_repo, skip_mod.load_config(git_repo))
    result = skip_mod.add_skip(git_repo, "tracked.txt")
    assert result.tracked is True
    assert result.skip_active is True
    assert "tracked.txt" in skip_mod.load_config(git_repo).skip_paths


def test_add_skip_rejects_escape(git_repo: Path) -> None:
    with pytest.raises(ValueError):
        skip_mod.add_skip(git_repo, "../outside")


def test_remove_skip(git_repo: Path) -> None:
    skip_mod.add_skip(git_repo, "tracked.txt")
    result = skip_mod.remove_skip(git_repo, "tracked.txt")
    assert result.skip_active is False
    assert result.in_config is False


def test_apply_all_restores_skip(git_repo: Path) -> None:
    skip_mod.add_skip(git_repo, "tracked.txt")
    skip_mod.remove_skip(git_repo, "tracked.txt", persist=False)
    skip_mod.save_config(
        git_repo,
        skip_mod.load_config(git_repo),
    )
    cfg = skip_mod.load_config(git_repo)
    cfg.skip_paths = ["tracked.txt"]
    skip_mod.save_config(git_repo, cfg)

    results = skip_mod.apply_all(git_repo)
    assert any(r.path == "tracked.txt" and r.skip_active for r in results)


def test_list_status_batch(git_repo: Path) -> None:
    skip_mod.add_skip(git_repo, "tracked.txt")
    statuses = skip_mod.list_status(git_repo)
    paths = {s.path for s in statuses}
    assert "tracked.txt" in paths
