"""skip-worktree management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitmove import git
from gitmove.config import GitMoveConfig, config_path_for_repo, normalize_rel


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
    full = root / path
    if not full.exists():
        raise FileNotFoundError(f"Path not found in repo: {path}")

    tracked = git.is_tracked(root, path)
    if tracked:
        git.update_index_skip(root, path, skip=True)
    elif persist:
        # Untracked files: config-only until tracked; still useful as checklist.
        pass

    if persist:
        cfg = load_config(root)
        if path not in cfg.skip_paths:
            cfg.skip_paths.append(path)
            save_config(root, cfg)

    active = path in git.ls_files_skip_worktree(root)
    return SkipStatus(path=path, tracked=tracked, skip_active=active, in_config=True)


def remove_skip(root: Path, rel_path: str, *, persist: bool = True) -> SkipStatus:
    path = normalize_rel(rel_path)
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
    results: list[SkipStatus] = []
    for path in cfg.skip_paths:
        full = root / path
        tracked = git.is_tracked(root, path)
        if not full.exists():
            results.append(SkipStatus(path=path, tracked=tracked, skip_active=False, in_config=True))
            continue
        if tracked:
            git.update_index_skip(root, path, skip=True)
        active = path in git.ls_files_skip_worktree(root)
        results.append(SkipStatus(path=path, tracked=tracked, skip_active=active, in_config=True))
    return results


def list_status(root: Path) -> list[SkipStatus]:
    cfg = load_config(root)
    active = git.ls_files_skip_worktree(root)
    all_paths = sorted(set(cfg.skip_paths) | active)
    return [
        SkipStatus(
            path=p,
            tracked=git.is_tracked(root, p),
            skip_active=p in active,
            in_config=p in cfg.skip_paths,
        )
        for p in all_paths
    ]
