"""skip-worktree management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitmove import git
from gitmove.config import GitMoveConfig, config_path_for_repo, normalize_rel, resolve_repo_path


@dataclass
class SkipStatus:
    path: str
    tracked: bool
    skip_active: bool
    in_config: bool


def load_config(root: Path) -> GitMoveConfig:
    return GitMoveConfig.load(config_path_for_repo(root))


def save_config(root: Path, cfg: GitMoveConfig) -> None:
    cfg.save(config_path_for_repo(root))


def add_skip(root: Path, rel_path: str, *, persist: bool = True) -> SkipStatus:
    path = normalize_rel(rel_path)
    full = resolve_repo_path(root, path)
    if not full.exists():
        raise FileNotFoundError(f"Path not found in repo: {path}")

    tracked = git.is_tracked(root, path)
    if tracked:
        git.update_index_skip(root, path, skip=True)

    if persist:
        cfg = load_config(root)
        if path not in cfg.skip_paths:
            cfg.skip_paths.append(path)
            save_config(root, cfg)

    active = path in git.ls_files_skip_worktree(root)
    return SkipStatus(path=path, tracked=tracked, skip_active=active, in_config=True)


def remove_skip(root: Path, rel_path: str, *, persist: bool = True) -> SkipStatus:
    path = normalize_rel(rel_path)
    resolve_repo_path(root, path)
    if git.is_tracked(root, path):
        git.update_index_skip(root, path, skip=False)

    if persist:
        cfg = load_config(root)
        cfg.skip_paths = [p for p in cfg.skip_paths if p != path]
        save_config(root, cfg)

    active = path in git.ls_files_skip_worktree(root)
    return SkipStatus(path=path, tracked=git.is_tracked(root, path), skip_active=active, in_config=False)


def apply_all(root: Path) -> list[SkipStatus]:
    cfg = load_config(root)
    skip_active, tracked = git.ls_files_index(root)
    for path in cfg.skip_paths:
        resolve_repo_path(root, path)
        full = root / path
        if full.exists() and path in tracked:
            git.update_index_skip(root, path, skip=True)

    skip_active, tracked = git.ls_files_index(root)
    results: list[SkipStatus] = []
    for path in cfg.skip_paths:
        full = root / path
        is_tracked = path in tracked
        results.append(
            SkipStatus(
                path=path,
                tracked=is_tracked,
                skip_active=path in skip_active,
                in_config=True,
            )
            if full.exists()
            else SkipStatus(path=path, tracked=is_tracked, skip_active=False, in_config=True)
        )
    return results


def list_status(root: Path) -> list[SkipStatus]:
    cfg = load_config(root)
    active, tracked = git.ls_files_index(root)
    all_paths = sorted(set(cfg.skip_paths) | active)
    return [
        SkipStatus(
            path=p,
            tracked=p in tracked,
            skip_active=p in active,
            in_config=p in cfg.skip_paths,
        )
        for p in all_paths
    ]
