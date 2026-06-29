"""Git command helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def run_git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
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


def ls_files_skip_worktree(root: Path) -> set[str]:
    result = run_git("ls-files", "-v", cwd=root)
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.startswith("S "):
            continue
        paths.add(line[2:].replace("\\", "/"))
    return paths


def update_index_skip(root: Path, path: str, *, skip: bool) -> None:
    flag = "--skip-worktree" if skip else "--no-skip-worktree"
    run_git("update-index", flag, path, cwd=root)


def is_tracked(root: Path, rel_path: str) -> bool:
    result = run_git("ls-files", "--error-unmatch", rel_path, cwd=root, check=False)
    return result.returncode == 0
