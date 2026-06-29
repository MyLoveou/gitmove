"""Pytest fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    tracked = repo / "tracked.txt"
    tracked.write_text("hello", encoding="utf-8")
    local = repo / "config.local.json"
    local.write_text("{}", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "config.local.json")
    _git(repo, "commit", "-m", "init")
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
