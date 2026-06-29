"""Personal git worktree helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitmove import git
from gitmove.config import WorktreeEntry
from gitmove.skip import load_config, save_config


@dataclass
class WorktreeStatus:
    name: str
    path: str
    branch: str | None
    exists: bool
    registered: bool


def _registered_paths(root: Path) -> set[str]:
    result = git.run_git("worktree", "list", "--porcelain", cwd=root)
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(str(Path(line.split(" ", 1)[1]).resolve()))
    return paths


def add_worktree(
    root: Path,
    name: str,
    wt_path: str,
    *,
    branch: str | None = None,
    create_branch: bool = False,
) -> WorktreeStatus:
    cfg = load_config(root)
    destination = Path(wt_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = ["worktree", "add"]
    if create_branch:
        if not branch:
            branch = f"personal/{name}"
        args.extend(["-b", branch, str(destination)])
    elif branch:
        args.extend([str(destination), branch])
    else:
        args.append(str(destination))

    git.run_git(*args, cwd=root)

    entry = WorktreeEntry(name=name, path=str(destination), branch=branch)
    cfg.worktrees = [w for w in cfg.worktrees if w.name != name]
    cfg.worktrees.append(entry)
    save_config(root, cfg)

    registered = str(destination) in _registered_paths(root)
    return WorktreeStatus(
        name=name,
        path=str(destination),
        branch=branch,
        exists=destination.exists(),
        registered=registered,
    )


def list_worktrees(root: Path) -> list[WorktreeStatus]:
    cfg = load_config(root)
    existing_paths = _registered_paths(root)

    statuses: list[WorktreeStatus] = []
    for entry in cfg.worktrees:
        resolved = str(Path(entry.path).expanduser().resolve())
        statuses.append(
            WorktreeStatus(
                name=entry.name,
                path=resolved,
                branch=entry.branch,
                exists=Path(resolved).exists(),
                registered=resolved in existing_paths,
            )
        )
    return statuses


def remove_worktree(root: Path, name: str, *, force: bool = False) -> None:
    cfg = load_config(root)
    entry = next((w for w in cfg.worktrees if w.name == name), None)
    if not entry:
        raise KeyError(f"Worktree not in config: {name}")

    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(entry.path)
    git.run_git(*args, cwd=root)

    cfg.worktrees = [w for w in cfg.worktrees if w.name != name]
    save_config(root, cfg)


def apply_worktrees(root: Path) -> list[WorktreeStatus]:
    cfg = load_config(root)
    results: list[WorktreeStatus] = []
    registered = _registered_paths(root)

    for entry in cfg.worktrees:
        path = Path(entry.path).expanduser().resolve()
        if str(path) in registered:
            results.append(
                WorktreeStatus(
                    name=entry.name,
                    path=str(path),
                    branch=entry.branch,
                    exists=path.exists(),
                    registered=True,
                )
            )
            continue
        status = add_worktree(root, entry.name, entry.path, branch=entry.branch)
        results.append(status)
    return results
