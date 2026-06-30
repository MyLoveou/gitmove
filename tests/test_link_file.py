"""Single-file link migrate and symlink target regression tests."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import link as link_mod


def test_add_link_migrate_single_file(git_repo: Path, tmp_path: Path) -> None:
    env_file = git_repo / ".env"
    env_file.write_text("SECRET=1\n", encoding="utf-8")
    external = tmp_path / "ext" / ".env"

    with mock.patch.object(link_mod, "create_link"):
        entry = link_mod.add_link(git_repo, ".env", str(external), migrate=True, link_type="symlink")

    assert entry.external_path == str(external.resolve())
    assert external.read_text(encoding="utf-8") == "SECRET=1\n"
    assert not env_file.exists()
    assert entry.kind == "file"


def test_create_symlink_for_file_skips_target_mkdir(tmp_path: Path) -> None:
    target = tmp_path / "ext" / ".env"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "repo" / ".env"
    link.parent.mkdir(parents=True)

    link_mod.create_link(link, target, "symlink", is_file=True)
    assert link.is_symlink()
    assert link.resolve() == target.resolve()


def test_add_link_migrate_single_file_uses_symlink_on_windows(git_repo: Path, tmp_path: Path) -> None:
    if link_mod.os.name != "nt":
        pytest.skip("junction default only on Windows")
    env_file = git_repo / ".env"
    env_file.write_text("SECRET=1\n", encoding="utf-8")
    external = tmp_path / "ext" / ".env"

    entry = link_mod.add_link(git_repo, ".env", str(external), migrate=True)
    assert entry.link_type == "symlink"
    assert env_file.is_symlink() or link_mod._is_reparse_point(env_file)


def test_add_link_dotenv_not_treated_as_directory(git_repo: Path, tmp_path: Path) -> None:
    dotfile = git_repo / ".easy.api.config"
    dotfile.write_text("api=local", encoding="utf-8")
    external = tmp_path / "ext" / ".easy.api.config"

    with mock.patch.object(link_mod, "create_link") as mock_create:
        link_mod.add_link(git_repo, ".easy.api.config", str(external), migrate=True, link_type="symlink")
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("is_file") is True
