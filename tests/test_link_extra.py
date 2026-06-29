from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod
from gitmove import skip as skip_mod
from gitmove.config import LinkEntry


def test_add_link_creates_symlink(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "external-tools"
    with mock.patch.object(link_mod, "create_link") as create_mock:
        entry = link_mod.add_link(
            git_repo,
            "tools/personal",
            str(external),
            link_type="symlink",
        )
    create_mock.assert_called_once()
    assert entry.repo_path == "tools/personal"
    assert entry.external_path == str(external.resolve())


def test_apply_links_recreates_missing(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "ext"
    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("tools/personal", str(external), "symlink")]
    skip_mod.save_config(git_repo, cfg)

    with mock.patch.object(link_mod, "create_link") as create_mock:
        results = link_mod.apply_links(git_repo)
    create_mock.assert_called_once()
    assert results[0].repo_path == "tools/personal"


def test_remove_link_keeps_external(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "ext"
    external.mkdir()
    link_path = git_repo / "tools/personal"
    link_path.parent.mkdir(parents=True)
    link_path.symlink_to(external, target_is_directory=True)

    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("tools/personal", str(external), "symlink")]
    skip_mod.save_config(git_repo, cfg)

    link_mod.remove_link(git_repo, "tools/personal", keep_external=True)
    assert external.exists()
    assert link_mod.list_links(git_repo) == []


def test_remove_link_unknown_raises(git_repo: Path) -> None:
    with pytest.raises(KeyError):
        link_mod.remove_link(git_repo, "missing")
