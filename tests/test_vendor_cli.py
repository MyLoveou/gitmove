"""CLI smoke tests for vendor subcommands."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gitmove.cli import app
from gitmove.doctor import init_repo


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


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_vendor_list_empty(
    runner: CliRunner, git_repo: Path, vendor_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repo(git_repo)
    monkeypatch.chdir(git_repo)
    result = runner.invoke(app, ["vendor", "list"])
    assert result.exit_code == 0
    assert "—" in result.stdout


def test_cli_vendor_add_list_sync(
    runner: CliRunner,
    git_repo: Path,
    vendor_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    monkeypatch.chdir(git_repo)
    url = upstream.resolve().as_uri()

    add = runner.invoke(
        app,
        ["vendor", "add", "tools", "--from", url, "--name", "tools"],
    )
    assert add.exit_code == 0, add.stdout

    listing = runner.invoke(app, ["vendor", "list"])
    assert listing.exit_code == 0
    assert "tools" in listing.stdout

    status = runner.invoke(app, ["vendor", "status", "tools", "--no-fetch"])
    assert status.exit_code == 0

    sync = runner.invoke(app, ["vendor", "sync", "tools", "--no-fetch"])
    assert sync.exit_code == 0


def test_cli_vendor_sync_all_exit_code_on_failure(
    runner: CliRunner,
    git_repo: Path,
    vendor_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    monkeypatch.chdir(git_repo)
    url = upstream.resolve().as_uri()
    runner.invoke(app, ["vendor", "add", "tools", "--from", url, "--name", "tools"])
    cache = vendor_home / "tools"
    (cache / "dirty.txt").write_text("x", encoding="utf-8")
    result = runner.invoke(app, ["vendor", "sync", "--all", "--no-fetch"])
    assert result.exit_code == 1
