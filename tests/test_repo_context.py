"""Tests for repository root resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from gitmove.registry import add_project, set_default
from gitmove.repo_context import RepoContextError, resolve_repo_root


@pytest.fixture
def registry_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "gitmove-home"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_HOME", str(home))
    return home


def test_resolve_repo_root_from_alias(registry_home: Path, git_repo: Path) -> None:
    add_project(git_repo, alias="alias-repo")
    root = resolve_repo_root(repo_opt="alias-repo")
    assert root == git_repo.resolve()


def test_resolve_repo_root_default_project(
    registry_home: Path, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    non_git = tmp_path / "not-git"
    non_git.mkdir()
    monkeypatch.chdir(non_git)
    add_project(git_repo, alias="defaulted")
    set_default("defaulted")
    root = resolve_repo_root()
    assert root == git_repo.resolve()


def test_resolve_repo_root_falls_back_cwd(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    root = resolve_repo_root()
    assert root == git_repo.resolve()


def test_resolve_repo_root_from_absolute_path(git_repo: Path) -> None:
    root = resolve_repo_root(repo_opt=str(git_repo))
    assert root == git_repo.resolve()


def test_resolve_repo_root_env_gitmove_repo(
    registry_home: Path, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_project(git_repo, alias="env-alias")
    monkeypatch.setenv("GITMOVE_REPO", "env-alias")
    root = resolve_repo_root()
    assert root == git_repo.resolve()


def test_resolve_unknown_alias_raises(registry_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    non_git = tmp_path / "not-git"
    non_git.mkdir()
    monkeypatch.chdir(non_git)
    with pytest.raises(RepoContextError):
        resolve_repo_root(repo_opt="nope")


def test_alias_wins_over_cwd_git_dir(
    registry_home: Path, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    import subprocess

    subprocess.run(["git", "init"], cwd=other, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.com"], cwd=other, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=other, check=True, capture_output=True)
    (other / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=other, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=other, check=True, capture_output=True)

    shadow = tmp_path / "shadow-name"
    shadow.mkdir()
    subprocess.run(["git", "init"], cwd=shadow, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.com"], cwd=shadow, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=shadow, check=True, capture_output=True)
    (shadow / "f.txt").write_text("y", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=shadow, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=shadow, check=True, capture_output=True)

    add_project(git_repo, alias="shadow-name")
    monkeypatch.chdir(shadow)
    root = resolve_repo_root(repo_opt="shadow-name")
    assert root == git_repo.resolve()


def test_repo_opt_overrides_env(
    registry_home: Path, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    import subprocess

    subprocess.run(["git", "init"], cwd=other, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "a@b.com"],
        cwd=other,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=other,
        check=True,
        capture_output=True,
    )
    (other / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=other, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=other, check=True, capture_output=True)

    add_project(git_repo, alias="first")
    add_project(other, alias="second")
    monkeypatch.setenv("GITMOVE_REPO", "first")
    root = resolve_repo_root(repo_opt="second")
    assert root == other.resolve()
