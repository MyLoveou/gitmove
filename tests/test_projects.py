"""Tests for multi-project batch orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from gitmove.config import config_path_for_repo
from gitmove.doctor import init_repo
from gitmove.projects import (
    batch_apply,
    batch_doctor,
    batch_exit_code,
    batch_sync_check,
    batch_sync_pull,
    project_status,
)
from gitmove.registry import ProjectEntry, add_project
from gitmove.sync import SyncStrategy


@pytest.fixture
def registry_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "gitmove-home"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_HOME", str(home))
    return home


def test_project_status_missing(tmp_path: Path) -> None:
    assert project_status(tmp_path / "missing") == "MISSING"


def test_project_status_no_init(git_repo: Path) -> None:
    assert project_status(git_repo) == "NO_INIT"


def test_project_status_ok(git_repo: Path) -> None:
    init_repo(git_repo)
    assert project_status(git_repo) == "OK"


def test_batch_doctor_skips_missing(registry_home: Path, git_repo: Path, tmp_path: Path) -> None:
    missing = tmp_path / "gone"
    add_project(git_repo, alias="good")
    add_project(missing, alias="bad")
    rows = batch_doctor(
        [
            ProjectEntry(path=git_repo.resolve(), alias="good"),
            ProjectEntry(path=missing.resolve(), alias="bad"),
        ]
    )
    by_alias = {row.alias: row for row in rows}
    assert by_alias["bad"].status == "MISSING"
    assert by_alias["bad"].warn_count == 1
    assert batch_exit_code(rows) == 0


def test_batch_doctor_exit_code_on_error(git_repo: Path) -> None:
    from gitmove import skip as skip_mod

    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "tracked.txt")
    skip_mod.remove_skip(git_repo, "tracked.txt", persist=False)
    rows = batch_doctor([ProjectEntry(path=git_repo.resolve(), alias="broken")])
    assert rows[0].error_count > 0
    assert batch_exit_code(rows) == 1


def test_batch_apply_invokes_apply_all(git_repo: Path) -> None:
    init_repo(git_repo)
    with mock.patch("gitmove.projects.apply_all_report") as apply_mock:
        batch_apply([ProjectEntry(path=git_repo.resolve(), alias="one")])
    apply_mock.assert_called_once_with(git_repo.resolve())


def test_batch_sync_check_no_interaction(git_repo: Path) -> None:
    init_repo(git_repo)
    summaries = batch_sync_check([ProjectEntry(path=git_repo.resolve(), alias="one")], fetch=False)
    assert summaries[0].status == "OK"


def test_batch_sync_pull_skips_project(git_repo: Path) -> None:
    init_repo(git_repo)
    entry = ProjectEntry(path=git_repo.resolve(), alias="one")

    def skip_project(_entry, _report) -> bool:
        return False

    from gitmove.sync import SyncCheckReport, SyncDrift

    drift = SyncDrift(
        path="tracked.txt",
        local_modified=True,
        remote_modified=True,
        skip_active=True,
        in_config=True,
    )

    with mock.patch(
        "gitmove.projects.check_sync",
        return_value=SyncCheckReport(upstream="origin/main", drifts=[drift]),
    ):
        results = batch_sync_pull(
            [entry],
            project_chooser=skip_project,
            file_chooser=lambda _: SyncStrategy.SKIP,
        )
    assert results[0].skipped_project is True
    assert results[0].pulled is False


def test_batch_sync_pull_uses_file_chooser(git_repo: Path) -> None:
    init_repo(git_repo)
    entry = ProjectEntry(path=git_repo.resolve(), alias="one")
    chooser_calls: list[str] = []

    def file_chooser(drift) -> SyncStrategy:
        chooser_calls.append(drift.path)
        return SyncStrategy.SKIP

    with mock.patch("gitmove.projects.check_sync") as check_mock, mock.patch(
        "gitmove.projects.sync_pull"
    ) as pull_mock:
        from gitmove.sync import SyncCheckReport, SyncPullReport

        check_mock.return_value = SyncCheckReport(upstream=None, drifts=[])
        pull_mock.return_value = SyncPullReport(pulled=False, reapplied=[], skipped=[], errors=[])
        batch_sync_pull([entry], project_chooser=None, file_chooser=file_chooser)
        pull_mock.assert_called_once()
        assert pull_mock.call_args.kwargs["chooser"] is file_chooser
