"""Git command helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gitmove.platform_util import subprocess_no_window_kwargs

DEFAULT_GIT_TIMEOUT = 30


class GitError(RuntimeError):
    pass


def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = DEFAULT_GIT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **subprocess_no_window_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git command timed out after {timeout}s: git {' '.join(args)}") from exc
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise GitError(stderr)
    return result


def repo_root(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    result = run_git("rev-parse", "--show-toplevel", cwd=cwd)
    return Path(result.stdout.strip())


def is_git_repo(path: Path | None = None) -> bool:
    try:
        repo_root(path)
        return True
    except GitError:
        return False


def _parse_ls_files_v(stdout: str) -> tuple[set[str], set[str]]:
    skip_active: set[str] = set()
    tracked: set[str] = set()
    for line in stdout.splitlines():
        if len(line) < 3:
            continue
        path = line[2:].replace("\\", "/")
        tracked.add(path)
        if line.startswith("S "):
            skip_active.add(path)
    return skip_active, tracked


def ls_files_index(root: Path) -> tuple[set[str], set[str]]:
    """Return (skip-worktree paths, all tracked paths) from one ls-files -v call."""
    result = run_git("ls-files", "-v", cwd=root)
    return _parse_ls_files_v(result.stdout)


def ls_files_skip_worktree(root: Path) -> set[str]:
    skip_active, _ = ls_files_index(root)
    return skip_active


def ls_tracked_files(root: Path) -> set[str]:
    _, tracked = ls_files_index(root)
    return tracked


def update_index_skip(root: Path, path: str, *, skip: bool) -> None:
    flag = "--skip-worktree" if skip else "--no-skip-worktree"
    run_git("update-index", flag, path, cwd=root)


def is_tracked(root: Path, rel_path: str) -> bool:
    result = run_git("ls-files", "--error-unmatch", rel_path, cwd=root, check=False)
    return result.returncode == 0
