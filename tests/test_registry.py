"""Tests for project registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from gitmove.registry import (
    RegistryError,
    add_project,
    load_registry,
    registry_path,
    remove_project,
    resolve_alias,
    save_registry,
    set_default,
    validate_alias,
)


@pytest.fixture
def registry_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "gitmove-home"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_HOME", str(home))
    return home


def test_config_dir_uses_gitmove_home(registry_home: Path) -> None:
    assert registry_path().parent == registry_home


def test_add_normalizes_absolute_path(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    entry = add_project(repo, alias="repo1")
    assert entry.path == repo.resolve()
    loaded = load_registry()
    assert loaded.projects[0].path == repo.resolve()


def test_alias_duplicate_raises(registry_home: Path, tmp_path: Path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    add_project(one, alias="dup")
    with pytest.raises(RegistryError, match="Alias already registered"):
        add_project(two, alias="dup")


def test_alias_invalid_chars_raises() -> None:
    with pytest.raises(RegistryError, match="Invalid alias"):
        validate_alias("bad alias!")


def test_same_path_twice_raises(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "same"
    repo.mkdir()
    add_project(repo, alias="first")
    with pytest.raises(RegistryError, match="Path already registered"):
        add_project(repo, alias="second")


def test_resolve_alias_unknown_raises(registry_home: Path) -> None:
    with pytest.raises(RegistryError, match="Unknown project alias"):
        resolve_alias("missing")


def test_add_default_alias_from_dirname(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "dirname-alias"
    repo.mkdir()
    entry = add_project(repo)
    assert entry.alias == "dirname-alias"


def test_remove_by_path(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "remove-me"
    repo.mkdir()
    add_project(repo, alias="gone")
    remove_project(str(repo))
    assert load_registry().projects == []


def test_set_default_persists(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "defaulted"
    repo.mkdir()
    add_project(repo, alias="main")
    set_default("main")
    assert load_registry().default_project == "main"


def test_missing_path_allowed_on_add(registry_home: Path, tmp_path: Path) -> None:
    missing = tmp_path / "future-repo"
    entry = add_project(missing, alias="future")
    assert entry.path == missing.resolve()
    assert load_registry().projects[0].alias == "future"


def test_round_trip_toml(registry_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "roundtrip"
    repo.mkdir()
    add_project(repo, alias="rt", group="work", notes="note")
    set_default("rt")
    loaded = load_registry()
    assert loaded.default_project == "rt"
    assert loaded.projects[0].group == "work"
    assert loaded.projects[0].notes == "note"
