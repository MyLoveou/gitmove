from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from gitmove import git
from gitmove.doctor import init_repo
from gitmove import skip as skip_mod
from gitmove.sync import (
    SyncDrift,
    SyncStrategy,
    check_sync,
    is_local_modified,
    is_remote_modified,
    sync_pull,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _push_remote(clone: Path, *, branch: str = "main") -> None:
    _git(clone, "branch", "-M", branch)
    _git(clone, "push", "origin", branch)


def _push_remote_change(bare: Path, tmp_path: Path, content: str) -> None:
    wt = tmp_path / "bare-checkout"
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    subprocess.run(
        ["git", "--git-dir", str(bare), "worktree", "add", "-f", str(wt), "main"],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(wt, "config", "user.email", "test@example.com")
    _git(wt, "config", "user.name", "test")
    (wt / "config.local.json").write_text(content, encoding="utf-8")
    _git(wt, "add", "config.local.json")
    _git(wt, "commit", "-m", "remote change")
    subprocess.run(
        ["git", "--git-dir", str(bare), "worktree", "remove", str(wt), "--force"],
        check=True,
        capture_output=True,
        text=True,
    )


def _setup_remote(git_repo: Path, tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True, text=True)
    _git(git_repo, "remote", "add", "origin", str(bare))
    _git(git_repo, "branch", "-M", "main")
    _git(git_repo, "push", "-u", "origin", "main")
    return bare


def test_is_local_modified_detects_worktree_change(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "config.local.json")
    (git_repo / "config.local.json").write_text('{"local": true}', encoding="utf-8")
    assert is_local_modified(git_repo, "config.local.json") is True


def test_check_sync_reports_remote_change(git_repo: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "config.local.json")
    (git_repo / "config.local.json").write_text('{"local": true}', encoding="utf-8")

    bare = _setup_remote(git_repo, tmp_path)
    _push_remote_change(bare, tmp_path, '{"remote": true}')

    report = check_sync(git_repo, fetch=True)
    drift = next(item for item in report.drifts if item.path == "config.local.json")
    assert drift.remote_modified is True
    assert drift.local_modified is True
    assert drift.needs_choice is True


def test_sync_pull_remote_strategy(git_repo: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "config.local.json")
    (git_repo / "config.local.json").write_text('{"local": true}', encoding="utf-8")
    _setup_remote(git_repo, tmp_path)
    _push_remote_change(tmp_path / "remote.git", tmp_path, '{"remote": true}')

    def choose_remote(drift: SyncDrift) -> SyncStrategy:
        assert drift.path == "config.local.json"
        return SyncStrategy.REMOTE

    result = sync_pull(git_repo, fetch=True, chooser=choose_remote)
    assert result.pulled is True
    assert "config.local.json" in result.reapplied
    assert '{"remote": true}' in (git_repo / "config.local.json").read_text(encoding="utf-8")
    assert "config.local.json" in git.ls_files_skip_worktree(git_repo)


def test_sync_pull_skip_strategy_leaves_file(git_repo: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "config.local.json")
    local_text = '{"local": true}'
    (git_repo / "config.local.json").write_text(local_text, encoding="utf-8")
    _setup_remote(git_repo, tmp_path)
    _push_remote_change(tmp_path / "remote.git", tmp_path, '{"remote": true}')

    result = sync_pull(git_repo, fetch=True, chooser=lambda _: SyncStrategy.SKIP)
    assert "config.local.json" in result.skipped
    assert (git_repo / "config.local.json").read_text(encoding="utf-8") == local_text


def test_sync_pull_requires_upstream(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "config.local.json")
    with pytest.raises(git.GitError, match="upstream"):
        sync_pull(git_repo, fetch=False, chooser=lambda _: SyncStrategy.REMOTE)
