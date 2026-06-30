"""Batch orchestration across registered gitmove projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gitmove import git
from gitmove.config import config_path_for_repo
from gitmove.doctor import apply_all as apply_all_report, run_doctor
from gitmove.errors import catalog_error
from gitmove.registry import ProjectEntry, add_project, list_projects, load_registry, save_registry
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


def format_batch_sync_pull_lines(
    results: list[ProjectSyncPullSummary],
) -> tuple[list[str], bool]:
    lines: list[str] = []
    had_errors = False
    for item in results:
        if item.report and item.report.errors:
            had_errors = True
            for error in item.report.errors:
                lines.append(f"{item.alias}: {error}")
            continue
        if item.message:
            lines.append(f"{item.alias}: {item.message}")
            if item.message != "skipped by user":
                had_errors = True
            continue
        if item.skipped_project:
            lines.append(f"{item.alias}: 跳过")
        elif item.pulled:
            lines.append(f"{item.alias}: 已 pull")
        else:
            lines.append(f"{item.alias}: 无变更")
    return lines, had_errors


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


@dataclass
class RepairRow:
    alias: str
    old_path: Path
    new_path: Path | None
    action: str  # updated | skipped | dry_run | no_match | invalid


def _validate_repair_target(path: Path) -> str | None:
    if not path.exists():
        return "path does not exist"
    if not git.is_git_repo(path):
        return "not a git repository"
    return None


RepairPathChooser = Callable[[ProjectEntry], str | None]


def _auto_suggest_path(entry: ProjectEntry) -> Path | None:
    old = entry.path
    if old.exists():
        return None
    name = old.name
    parent = old.parent
    matches: list[Path] = []
    if parent.exists():
        for child in parent.iterdir():
            if child.is_dir() and child.name == name and git.is_git_repo(child):
                matches.append(child.resolve())
    search_root = parent.parent if parent.parent.exists() else (parent if parent.exists() else None)
    if search_root is not None:
        for child in search_root.iterdir():
            if child.is_dir() and child.name == name and git.is_git_repo(child):
                candidate = child.resolve()
                if candidate not in matches:
                    matches.append(candidate)
    if len(matches) == 1:
        return matches[0]
    return None


def repair_projects(
    *,
    dry_run: bool = False,
    auto: bool = False,
    path_chooser: RepairPathChooser | None = None,
) -> list[RepairRow]:
    registry = load_registry()
    rows: list[RepairRow] = []
    for entry in registry.projects:
        if entry.path.exists():
            continue
        old_path = entry.path
        new_path: Path | None = None
        if auto:
            new_path = _auto_suggest_path(entry)
        elif path_chooser is not None:
            raw = path_chooser(entry)
            if raw:
                new_path = Path(raw).expanduser().resolve()
        else:
            continue
        if new_path is None:
            rows.append(RepairRow(entry.alias, old_path, None, "skipped" if path_chooser else "no_match"))
            continue
        if dry_run:
            rows.append(RepairRow(entry.alias, old_path, new_path, "dry_run"))
            continue
        invalid = _validate_repair_target(new_path)
        if invalid:
            rows.append(RepairRow(entry.alias, old_path, new_path, "invalid"))
            continue
        entry.path = new_path
        rows.append(RepairRow(entry.alias, old_path, new_path, "updated"))
    if not dry_run:
        save_registry(registry)
    return rows


SCAN_EXCLUDE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        ".gitmove-vendor",
        "__pycache__",
        ".venv",
        "venv",
        "vendor",
        ".hg",
        ".tox",
        "dist",
        "build",
    }
)


@dataclass
class ScanRegisterResult:
    path: Path
    alias: str
    registered: bool
    skipped: bool = False
    message: str | None = None


def _is_git_root(path: Path) -> bool:
    git_dir = path / ".git"
    if not git_dir.exists():
        return False
    if git_dir.is_file():
        return False
    result = git.run_git("rev-parse", "--show-toplevel", cwd=path, check=False)
    if result.returncode != 0:
        return False
    top = Path(result.stdout.strip()).resolve()
    return top == path.resolve()


def scan_git_roots(root: Path, *, max_depth: int = 4) -> list[Path]:
    root = root.expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Scan root does not exist: {root}")
    found: list[Path] = []
    seen: set[Path] = set()
    queue: list[tuple[Path, int]] = [(root, 0)]
    registered = {entry.path.resolve() for entry in load_registry().projects}

    while queue:
        current, depth = queue.pop(0)
        current = current.resolve()
        if current in seen:
            continue
        seen.add(current)

        if _is_git_root(current):
            if current not in registered:
                found.append(current)
            continue

        if depth >= max_depth:
            continue

        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue

        for child in children:
            if not child.is_dir():
                continue
            if child.name in SCAN_EXCLUDE_DIRS:
                continue
            queue.append((child, depth + 1))

    return found


def _unique_alias(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    index = 2
    while f"{base}-{index}" in taken:
        index += 1
    return f"{base}-{index}"


def scan_and_register(
    root: Path,
    *,
    max_depth: int = 4,
    group: str | None = None,
    dry_run: bool = False,
    yes: bool = False,
    chooser: Callable[[Path, str], bool] | None = None,
) -> list[ScanRegisterResult]:
    candidates = scan_git_roots(root, max_depth=max_depth)
    registry = load_registry()
    taken = {entry.alias for entry in registry.projects}
    results: list[ScanRegisterResult] = []

    for candidate in candidates:
        alias = _unique_alias(candidate.name, taken)
        register = yes
        if not yes and not dry_run:
            if chooser is not None:
                register = chooser(candidate, alias)
            else:
                register = False
                results.append(
                    ScanRegisterResult(
                        path=candidate,
                        alias=alias,
                        registered=False,
                        skipped=True,
                        message="interactive chooser required",
                    )
                )
                continue

        if dry_run:
            results.append(
                ScanRegisterResult(path=candidate, alias=alias, registered=False, message="dry-run")
            )
            continue

        if register:
            add_project(candidate, alias=alias, group=group, reg=registry)
            registry = load_registry()
            taken.add(alias)
            results.append(ScanRegisterResult(path=candidate, alias=alias, registered=True))
        else:
            results.append(
                ScanRegisterResult(
                    path=candidate,
                    alias=alias,
                    registered=False,
                    skipped=True,
                )
            )

    return results


@dataclass
class ProjectUpdateRow:
    alias: str
    path: Path
    status: str
    pulled: bool = False
    old_commit: str | None = None
    new_commit: str | None = None
    message: str | None = None
    error_code: str | None = None


def _repo_head(path: Path) -> str | None:
    result = git.run_git("rev-parse", "HEAD", cwd=path, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _working_tree_dirty(path: Path) -> bool:
    result = git.run_git("status", "--porcelain", cwd=path, check=False)
    return bool(result.stdout.strip())


def batch_update(
    entries: list[ProjectEntry],
    *,
    ff_only: bool = True,
    dry_run: bool = False,
) -> list[ProjectUpdateRow]:
    rows: list[ProjectUpdateRow] = []
    for entry in entries:
        status = project_status(entry.path)
        if status in {"MISSING", "NOT_GIT"}:
            rows.append(
                ProjectUpdateRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    message=status.lower(),
                )
            )
            continue

        if _working_tree_dirty(entry.path):
            rows.append(
                ProjectUpdateRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    message="working tree dirty; skipped",
                )
            )
            continue

        old_commit = _repo_head(entry.path)
        if dry_run:
            rows.append(
                ProjectUpdateRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    message="dry-run",
                    old_commit=old_commit,
                )
            )
            continue

        pull_args = ["pull", "--ff-only"] if ff_only else ["pull"]
        pull = git.run_git(*pull_args, cwd=entry.path, check=False)
        new_commit = _repo_head(entry.path)
        if pull.returncode != 0:
            stderr = pull.stderr.strip() or pull.stdout.strip() or "git pull failed"
            error_code = "PROJECTS_UPDATE_FF_FAILED" if ff_only else None
            rows.append(
                ProjectUpdateRow(
                    alias=entry.alias,
                    path=entry.path,
                    status=status,
                    pulled=False,
                    old_commit=old_commit,
                    new_commit=new_commit,
                    message=stderr,
                    error_code=error_code,
                )
            )
            continue

        rows.append(
            ProjectUpdateRow(
                alias=entry.alias,
                path=entry.path,
                status=status,
                pulled=old_commit != new_commit,
                old_commit=old_commit,
                new_commit=new_commit,
                message=None if old_commit != new_commit else "already up to date",
            )
        )
    return rows


def batch_update_exit_code(rows: list[ProjectUpdateRow]) -> int:
    for row in rows:
        if row.status in {"MISSING", "NOT_GIT"}:
            continue
        if row.message in {None, "already up to date", "dry-run", "working tree dirty; skipped"}:
            continue
        if row.pulled:
            continue
        return 1
    return 0
