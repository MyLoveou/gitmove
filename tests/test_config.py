from __future__ import annotations

from pathlib import Path

import pytest

from gitmove.config import GitMoveConfig, VendorEntry, config_path_for_repo, resolve_repo_path


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


def test_config_vendor_roundtrip(git_repo: Path) -> None:
    cfg = GitMoveConfig(
        skip_paths=[],
        vendors=[
            VendorEntry(
                name="cursor-spec",
                repo_path=".cursor",
                source_url="https://example.com/spec.git",
                source_ref="main",
                cache_path="~/gitmove-vendor/cursor-spec",
                link_type="junction",
                auto_skip_tracked=True,
                source_pin="v1.0.0",
            )
        ],
    )
    path = config_path_for_repo(git_repo)
    cfg.save(path)
    loaded = GitMoveConfig.load(path)
    assert len(loaded.vendors) == 1
    assert loaded.vendors[0].name == "cursor-spec"
    assert loaded.vendors[0].repo_path == ".cursor"
    assert loaded.vendors[0].source_pin == "v1.0.0"


def test_config_vendor_empty_repo_path_rejected(git_repo: Path) -> None:
    path = config_path_for_repo(git_repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '[vendors.bad]\nrepo_path = ""\nsource_url = "https://example.com/x.git"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="repo_path must not be empty"):
        GitMoveConfig.load(path)

