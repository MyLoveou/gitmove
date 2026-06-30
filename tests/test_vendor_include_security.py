"""Tests for include_paths security and cache rollback."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitmove.errors import GitMoveError
from gitmove.doctor import init_repo
from gitmove import vendor as vendor_mod


@pytest.fixture
def vendor_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "vendor-cache-root"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_VENDOR_HOME", str(home))
    return home


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_upstream(tmp_path: Path) -> Path:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init")
    _git(upstream, "config", "user.email", "vendor@test.local")
    _git(upstream, "config", "user.name", "vendor")
    (upstream / "README.md").write_text("upstream", encoding="utf-8")
    _git(upstream, "add", "README.md")
    _git(upstream, "commit", "-m", "init")
    _git(upstream, "branch", "-M", "main")
    return upstream


def test_include_path_rejects_traversal(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    with pytest.raises(GitMoveError) as exc:
        vendor_mod.add_vendor(
            git_repo,
            "tools",
            source_url=upstream.resolve().as_uri(),
            name="tools",
            include_paths=["../outside"],
        )
    assert exc.value.code == "INCLUDE_PATH_NOT_IN_CACHE"
    assert not (vendor_home / "tools").exists()


def test_include_path_invalid_purges_cache(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    with pytest.raises(GitMoveError):
        vendor_mod.add_vendor(
            git_repo,
            "tools",
            source_url=upstream.resolve().as_uri(),
            name="tools2",
            include_paths=["missing/sub"],
        )
    assert not (vendor_home / "tools2").exists()
