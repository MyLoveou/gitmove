from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove.sync import (
    SyncCheckReport,
    SyncDrift,
    SyncStrategy,
    default_chooser,
    is_remote_modified,
    sync_pull,
)


def test_is_remote_modified_false_when_same(git_repo: Path) -> None:
    assert is_remote_modified(git_repo, "tracked.txt", "HEAD") is False


def test_sync_pull_dry_run(git_repo: Path) -> None:
    from gitmove.doctor import init_repo
    from gitmove import skip as skip_mod

    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "tracked.txt")
    with mock.patch("gitmove.sync.check_sync") as check:
        check.return_value = SyncCheckReport(
            upstream="origin/main",
            drifts=[
                SyncDrift(
                    path="tracked.txt",
                    local_modified=True,
                    remote_modified=True,
                    skip_active=True,
                    in_config=True,
                )
            ],
        )
        result = sync_pull(
            git_repo,
            fetch=False,
            chooser=lambda _: SyncStrategy.REMOTE,
            dry_run=True,
        )
    assert result.pulled is False


def test_sync_pull_calls_chooser_for_remote_only_drift(git_repo: Path) -> None:
    from gitmove.doctor import init_repo

    init_repo(git_repo)
    chosen: list[SyncStrategy] = []

    with mock.patch("gitmove.sync.check_sync") as check, mock.patch(
        "gitmove.sync.git.run_git"
    ) as run_git, mock.patch("gitmove.sync.apply_all"):
        check.return_value = SyncCheckReport(
            upstream="origin/main",
            drifts=[
                SyncDrift(
                    path="tracked.txt",
                    local_modified=False,
                    remote_modified=True,
                    skip_active=True,
                    in_config=True,
                )
            ],
        )
        run_git.return_value = mock.Mock(returncode=0, stdout="", stderr="")

        sync_pull(
            git_repo,
            fetch=False,
            chooser=lambda drift: chosen.append(SyncStrategy.REMOTE) or SyncStrategy.REMOTE,
        )

    assert chosen == [SyncStrategy.REMOTE]


def test_default_chooser_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    drift = SyncDrift(
        path="a.txt",
        local_modified=True,
        remote_modified=True,
        skip_active=True,
        in_config=True,
    )
    monkeypatch.setattr("builtins.input", lambda _: "s")
    assert default_chooser(drift) == SyncStrategy.SKIP
