from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod
from gitmove.config import LinkEntry
from gitmove import skip as skip_mod


@pytest.mark.skipif(os.name != "nt", reason="Windows junction only")
def test_remove_junction_on_windows(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    link_path = git_repo / "tools/personal"
    link_mod.create_link(link_path, external, "junction")
    assert link_path.exists()

    link_mod._remove_link_path(link_path)
    assert not link_path.exists()
    assert external.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction only")
def test_remove_link_junction_via_api(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "external"
    link_path = git_repo / "tools/personal"
    link_mod.create_link(link_path, external, "junction")

    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("tools/personal", str(external), "junction")]
    skip_mod.save_config(git_repo, cfg)

    link_mod.remove_link(git_repo, "tools/personal", keep_external=True)
    assert not link_path.exists()
    assert external.exists()
    assert link_mod.list_links(git_repo) == []


def test_remove_link_path_rejects_plain_directory(git_repo: Path) -> None:
    plain = git_repo / "plain-dir"
    plain.mkdir()
    with pytest.raises(FileExistsError):
        link_mod._remove_link_path(plain)
