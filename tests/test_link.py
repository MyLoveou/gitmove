from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod


def test_add_link_rejects_escape(git_repo: Path) -> None:
    with pytest.raises(ValueError):
        link_mod.add_link(git_repo, "../outside")


def test_list_links_empty(git_repo: Path) -> None:
    assert link_mod.list_links(git_repo) == []


def test_set_external_base(git_repo: Path) -> None:
    base = git_repo / "external"
    resolved = link_mod.set_external_base(git_repo, str(base))
    assert resolved == base.resolve()


def test_create_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    link = tmp_path / "link"
    target.mkdir()
    link_mod.create_link(link, target, "symlink")
    assert link.is_symlink()
