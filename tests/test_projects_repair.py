"""Tests for projects repair."""

from __future__ import annotations

from pathlib import Path

from gitmove.registry import add_project, load_registry, registry_path
from gitmove import projects as projects_mod


def test_repair_dry_run(tmp_path: Path, monkeypatch) -> None:
    reg_file = tmp_path / "projects.toml"
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    old = tmp_path / "missing" / "repo"
    new = tmp_path / "moved" / "repo"
    new.mkdir(parents=True)
    add_project(old, alias="app", reg=load_registry(), save_path=reg_file)

    def chooser(entry) -> str:
        return str(new)

    rows = projects_mod.repair_projects(dry_run=True, path_chooser=chooser)
    assert len(rows) == 1
    assert rows[0].action == "dry_run"
    assert rows[0].new_path == new.resolve()

    reg = load_registry(reg_file)
    assert reg.projects[0].path == old.resolve()


def test_repair_updates_registry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    old = tmp_path / "missing" / "repo"
    new = tmp_path / "moved" / "repo"
    new.mkdir(parents=True)
    add_project(old, alias="app")

    rows = projects_mod.repair_projects(
        path_chooser=lambda entry: str(new),
    )
    assert rows[0].action == "invalid"
    reg = load_registry()
    assert reg.projects[0].path == old.resolve()


def test_repair_accepts_git_repo(tmp_path: Path, git_repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    old = tmp_path / "missing" / "repo"
    add_project(old, alias="app")
    rows = projects_mod.repair_projects(path_chooser=lambda entry: str(git_repo))
    assert rows[0].action == "updated"
    assert load_registry().projects[0].path == git_repo.resolve()


def test_auto_suggest_finds_same_name_sibling(tmp_path: Path) -> None:
    import subprocess

    from gitmove.registry import ProjectEntry

    old = tmp_path / "work" / "my-app"
    sibling = tmp_path / "my-app"
    sibling.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=sibling, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=sibling, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=sibling, check=True)
    entry = ProjectEntry(path=old, alias="my-app")
    suggested = projects_mod._auto_suggest_path(entry)
    assert suggested == sibling.resolve()
