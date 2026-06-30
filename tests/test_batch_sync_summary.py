"""Tests for shared batch sync pull summary formatting."""

from __future__ import annotations

from pathlib import Path

from gitmove.projects import ProjectSyncPullSummary, format_batch_sync_pull_lines
from gitmove.sync import SyncPullReport


def test_format_batch_sync_pull_lines_shows_report_errors() -> None:
    report = SyncPullReport(
        pulled=True,
        reapplied=[],
        skipped=[],
        errors=["path/a: reconcile failed"],
    )
    item = ProjectSyncPullSummary(
        alias="demo",
        path=Path("/tmp/demo"),
        status="OK",
        pulled=True,
        skipped_project=False,
        report=report,
    )
    lines, had_errors = format_batch_sync_pull_lines([item])
    assert had_errors is True
    assert lines == ["demo: path/a: reconcile failed"]


def test_format_batch_sync_pull_lines_shows_fetch_failure() -> None:
    item = ProjectSyncPullSummary(
        alias="demo",
        path=Path("/tmp/demo"),
        status="OK",
        pulled=False,
        skipped_project=True,
        message="network down",
    )
    lines, had_errors = format_batch_sync_pull_lines([item])
    assert had_errors is True
    assert lines == ["demo: network down"]


def test_format_batch_sync_pull_lines_user_skip_not_error() -> None:
    item = ProjectSyncPullSummary(
        alias="demo",
        path=Path("/tmp/demo"),
        status="OK",
        pulled=False,
        skipped_project=True,
        message="skipped by user",
    )
    lines, had_errors = format_batch_sync_pull_lines([item])
    assert had_errors is False
    assert lines == ["demo: skipped by user"]


def test_format_batch_sync_pull_lines_ok_pulled() -> None:
    report = SyncPullReport(pulled=True, reapplied=[], skipped=[], errors=[])
    item = ProjectSyncPullSummary(
        alias="demo",
        path=Path("/tmp/demo"),
        status="OK",
        pulled=True,
        skipped_project=False,
        report=report,
    )
    lines, had_errors = format_batch_sync_pull_lines([item])
    assert had_errors is False
    assert lines == ["demo: 已 pull"]
