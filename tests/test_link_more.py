from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod
from gitmove.config import LinkEntry
from gitmove import skip as skip_mod


def test_status_for_broken_link(git_repo: Path, tmp_path: Path) -> None:
    external = tmp_path / "ext"
    external.mkdir()
    link_path = git_repo / "tools/personal"
    link_path.parent.mkdir(parents=True)
    link_path.symlink_to(external, target_is_directory=True)

    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("tools/personal", str(tmp_path / "other"), "symlink")]
    skip_mod.save_config(git_repo, cfg)

    statuses = link_mod.list_links(git_repo)
    assert statuses[0].is_link is True
    assert statuses[0].link_ok is False


def test_add_link_migrate_existing_dir(git_repo: Path, tmp_path: Path) -> None:
    existing = git_repo / "tools/personal"
    existing.mkdir(parents=True)
    (existing / "data.txt").write_text("x", encoding="utf-8")
    external = tmp_path / "ext"

    with mock.patch.object(link_mod, "create_link"):
        entry = link_mod.add_link(git_repo, "tools/personal", str(external), migrate=True)
    assert entry.external_path == str(external.resolve())
    assert external.exists()
    assert not existing.exists()


def test_create_junction_on_windows(tmp_path: Path) -> None:
    if link_mod.os.name != "nt":
        pytest.skip("junction test only on Windows")
    target = tmp_path / "target"
    link = tmp_path / "link"
    target.mkdir()
    link_mod.create_link(link, target, "junction")
    assert link.exists()
