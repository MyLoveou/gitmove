"""Batch orchestration across registered gitmove projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gitmove import git
from gitmove.config import config_path_for_repo
from gitmove.doctor import apply_all as apply_all_report, run_doctor
from gitmove.registry import ProjectEntry, list_projects
from gitmove.sync import (
    StrategyChooser,
    SyncCheckReport,
    SyncPullReport,
    check_sync,
    sync_pull,
)

ProjectContinueChooser = Callable[[ProjectEntry, SyncCheckReport], bool]


@dataclass
class ProjectBatchRow:
    alias: str
    path: Path
    status: str
    error_count: int
    warn_count: int
    message: str | None = None


@dataclass
class ProjectSyncSummary:
    alias: str
    path: Path
    status: str
    upstream: str | None
    attention_count: int
    message: str | None = None


@dataclass
class ProjectSyncPullSummary:
    alias: str
    path: Path
    status: str
    pulled: bool
    skipped_project: bool
    report: SyncPullReport | None = None
    message: str | None = None


def project_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    if not git.is_git_repo(path):
        return "NOT_GIT"
    if not config_path_for_repo(path).exists():
        return "NO_INIT"
    return "OK"


def iter_projects(*, group: str | None = None) -> list[ProjectEntry]:
    return list_projects(group=group)


def batch_doctor(entries: list[ProjectEntry]) -> list[ProjectBatchRow]:
    rows: list[ProjectBatchRow] = []
    for entry in entries:
        status = project_status(entry.path)
        if status == "MISSING":
            rows.append(
                ProjectBatchRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    error_count=0,
                    warn_count=1,
                    message="path missing",
                )
            )
            continue
        if status != "OK":
            rows.append(
                ProjectBatchRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    error_count=0,
                    warn_count=1,
                    message=status.lower(),
                )
            )
            continue

        report = run_doctor(entry.path)
        rows.append(
            ProjectBatchRow(
                alias=entry.alias,
                path=entry.path,
                status=status,
                error_count=report.error_count,
                warn_count=report.warn_count,
                message=None if report.ok else "doctor issues",
            )
        )
    return rows


def batch_apply(entries: list[ProjectEntry]) -> list[ProjectBatchRow]:
    rows: list[ProjectBatchRow] = []
    for entry in entries:
        status = project_status(entry.path)
        if status != "OK":
            rows.append(
                ProjectBatchRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    error_count=0,
                    warn_count=1,
                    message=status.lower(),
                )
            )
            continue
        apply_all_report(entry.path)
        report = run_doctor(entry.path)
        rows.append(
            ProjectBatchRow(
                alias=entry.alias,
                path=entry.path,
                status=status,
                error_count=report.error_count,
                warn_count=report.warn_count,
                message="applied",
            )
        )
    return rows


def batch_sync_check(entries: list[ProjectEntry], *, fetch: bool = False) -> list[ProjectSyncSummary]:
    summaries: list[ProjectSyncSummary] = []
    for entry in entries:
        status = project_status(entry.path)
        if status != "OK":
            summaries.append(
                ProjectSyncSummary(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    upstream=None,
                    attention_count=0,
                    message=status.lower(),
                )
            )
            continue
        try:
            report = check_sync(entry.path, fetch=fetch)
        except git.GitError as exc:
            summaries.append(
                ProjectSyncSummary(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    upstream=None,
                    attention_count=0,
                    message=str(exc),
                )
            )
            continue
        summaries.append(
            ProjectSyncSummary(
                alias=entry.alias,
                path=entry.path,
                status=status,
                upstream=report.upstream,
                attention_count=len(report.attention_items),
                message=None,
            )
        )
    return summaries


def batch_sync_pull(
    entries: list[ProjectEntry],
    *,
    fetch: bool = True,
    project_chooser: ProjectContinueChooser | None = None,
    file_chooser: StrategyChooser | None = None,
) -> list[ProjectSyncPullSummary]:
    results: list[ProjectSyncPullSummary] = []
    for entry in entries:
        status = project_status(entry.path)
        if status != "OK":
            results.append(
                ProjectSyncPullSummary(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    pulled=False,
                    skipped_project=True,
                    message=status.lower(),
                )
            )
            continue

        try:
            report = check_sync(entry.path, fetch=fetch)
        except git.GitError as exc:
            results.append(
                ProjectSyncPullSummary(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    pulled=False,
                    skipped_project=True,
                    message=str(exc),
                )
            )
            continue

        if project_chooser is not None and report.attention_items:
            if not project_chooser(entry, report):
                results.append(
                    ProjectSyncPullSummary(
                        alias=entry.alias,
                        path=entry.path,
                        status=status,
                        pulled=False,
                        skipped_project=True,
                        message="skipped by user",
                    )
                )
                continue

        try:
            pull_report = sync_pull(entry.path, fetch=False, chooser=file_chooser)
        except (FileNotFoundError, git.GitError) as exc:
            results.append(
                ProjectSyncPullSummary(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    pulled=False,
                    skipped_project=False,
                    message=str(exc),
                )
            )
            continue

        results.append(
            ProjectSyncPullSummary(
                alias=entry.alias,
                path=entry.path,
                status=status,
                pulled=pull_report.pulled,
                skipped_project=False,
                report=pull_report,
                message=None,
            )
        )
    return results


def batch_exit_code(rows: list[ProjectBatchRow]) -> int:
    return 1 if any(row.error_count > 0 for row in rows) else 0


def default_project_chooser(entry: ProjectEntry, report: SyncCheckReport) -> bool:
    count = len(report.attention_items)
    print(f"\n=== 项目: {entry.alias} ({entry.path}) ===")
    print(f"{count} 个 skip 路径需关注。是否处理此项目？")
    print("  [y] 继续  [n] 跳过整个项目")
    while True:
        choice = input("选择: ").strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("无效输入，请重新选择")
