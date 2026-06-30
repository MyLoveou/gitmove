"""Directory migrate with special files (socket, symlink) skipped."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod


def test_copy_tree_skip_special_skips_symlink(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "ok.txt").write_text("data", encoding="utf-8")
    nested = src / "nested"
    target = tmp_path / "target"
    target.mkdir()
    nested.symlink_to(target, target_is_directory=True)

    skipped = link_mod._copy_tree_skip_special(src, dst)
    assert (dst / "ok.txt").read_text(encoding="utf-8") == "data"
    assert not (dst / "nested").exists()
    assert any("nested" in s and "symlink" in s for s in skipped)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO not supported")
def test_copy_tree_skip_special_skips_fifo(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    fifo = src / "pipe.fifo"
    os.mkfifo(fifo)

    skipped = link_mod._copy_tree_skip_special(src, dst)
    assert not fifo.exists() or not (dst / "pipe.fifo").exists()
    assert any("pipe.fifo" in s and "special" in s for s in skipped)


def test_add_link_migrate_dir_records_skipped(git_repo: Path, tmp_path: Path) -> None:
    config_dir = git_repo / "config"
    config_dir.mkdir()
    (config_dir / "app.yml").write_text("x", encoding="utf-8")
    nested = config_dir / "nested"
    external_target = tmp_path / "other"
    external_target.mkdir()
    nested.symlink_to(external_target, target_is_directory=True)
    external = tmp_path / "ext"

    with mock.patch.object(link_mod, "create_link"):
        entry = link_mod.add_link(git_repo, "config", str(external), migrate=True)

    assert entry.migrate_skipped
    assert any("nested" in s for s in entry.migrate_skipped)
    assert (external / "app.yml").exists()
