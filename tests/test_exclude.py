"""`.git/info/exclude` managed section sync for links and vendors."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove import exclude as exclude_mod
from gitmove import link as link_mod
from gitmove.config import GitMoveConfig, LinkEntry, VendorEntry, config_path_for_repo
from gitmove import skip as skip_mod


def _exclude_path(git_repo: Path) -> Path:
    return git_repo / ".git" / "info" / "exclude"


def test_sync_link_excludes_writes_managed_section(git_repo: Path, tmp_path: Path) -> None:
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    _exclude_path(git_repo).write_text("# user rule\n*.log\n", encoding="utf-8")

    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("config", str(tmp_path / "config"), "symlink")]
    skip_mod.save_config(git_repo, cfg)

    exclude_mod.sync_link_excludes(git_repo)
    content = _exclude_path(git_repo).read_text(encoding="utf-8")
    assert "# user rule" in content
    assert "*.log" in content
    assert exclude_mod.MANAGED_MARKER_START in content
    assert "/config" in content


def test_sync_includes_vendor_paths(git_repo: Path, tmp_path: Path) -> None:
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    cfg = skip_mod.load_config(git_repo)
    cfg.vendors = [
        VendorEntry(
            name="tools",
            repo_path="tools",
            source_url="https://example.com/tools.git",
        )
    ]
    skip_mod.save_config(git_repo, cfg)

    exclude_mod.sync_link_excludes(git_repo)
    content = _exclude_path(git_repo).read_text(encoding="utf-8")
    assert "/tools" in content


def test_sync_disabled_removes_managed_section_only(git_repo: Path, tmp_path: Path) -> None:
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    _exclude_path(git_repo).write_text("# user\n*.tmp\n", encoding="utf-8")

    cfg = skip_mod.load_config(git_repo)
    cfg.exclude_linked_paths = False
    cfg.links = [LinkEntry("config", str(tmp_path / "config"), "symlink")]
    skip_mod.save_config(git_repo, cfg)
    exclude_mod.sync_link_excludes(git_repo)

    content = _exclude_path(git_repo).read_text(encoding="utf-8")
    assert "# user" in content
    assert "*.tmp" in content
    assert exclude_mod.MANAGED_MARKER_START not in content


def test_add_link_syncs_exclude(git_repo: Path, tmp_path: Path) -> None:
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    existing = git_repo / "config"
    existing.mkdir()
    external = tmp_path / "ext"

    with mock.patch.object(link_mod, "create_link"):
        link_mod.add_link(git_repo, "config", str(external), migrate=True)

    content = _exclude_path(git_repo).read_text(encoding="utf-8")
    assert "/config" in content


def test_remove_link_updates_exclude(git_repo: Path, tmp_path: Path) -> None:
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("config", str(tmp_path / "config"), "symlink")]
    skip_mod.save_config(git_repo, cfg)
    exclude_mod.sync_link_excludes(git_repo)

    link_mod.remove_link(git_repo, "config")
    content = _exclude_path(git_repo).read_text(encoding="utf-8")
    assert "/config" not in content


def test_remove_vendor_updates_exclude(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gitmove import vendor as vendor_mod
    from gitmove.doctor import init_repo

    vendor_home = tmp_path / "vendor-cache-root"
    vendor_home.mkdir()
    monkeypatch.setenv("GITMOVE_VENDOR_HOME", str(vendor_home))

    init_repo(git_repo)
    _exclude_path(git_repo).parent.mkdir(parents=True, exist_ok=True)
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    import subprocess

    subprocess.run(["git", "init"], cwd=upstream, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=upstream, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=upstream, check=True, capture_output=True)
    (upstream / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=upstream, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=upstream, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=upstream, check=True, capture_output=True)

    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=upstream.resolve().as_uri(),
        name="company-tools",
    )
    assert "/tools" in _exclude_path(git_repo).read_text(encoding="utf-8")

    vendor_mod.remove_vendor(git_repo, "company-tools")
    assert "/tools" not in _exclude_path(git_repo).read_text(encoding="utf-8")

