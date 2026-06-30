"""Resolve the active Git repository root for CLI and GUI."""

from __future__ import annotations

import os
from pathlib import Path

from gitmove import git
from gitmove.registry import RegistryError, load_registry, resolve_alias


class RepoContextError(RuntimeError):
    """Could not resolve a Git repository root."""


def resolve_repo_root(
    *,
    repo_opt: str | None = None,
    env_repo: str | None = None,
    cwd: Path | None = None,
) -> Path:
    """Resolve repository root using gitmove multi-project priority chain."""
    if repo_opt:
        root = _resolve_candidate(repo_opt, allow_alias=True)
        if root is None:
            raise RepoContextError(f"Could not resolve repository: {repo_opt}")
        return root

    env_value = env_repo if env_repo is not None else os.environ.get("GITMOVE_REPO")
    if env_value:
        root = _resolve_candidate(env_value, allow_alias=True)
        if root is None:
            raise RepoContextError(f"Could not resolve repository: {env_value}")
        return root

    registry = load_registry()
    if registry.default_project:
        try:
            default_path = resolve_alias(registry.default_project, registry)
        except RegistryError:
            default_path = None
        if default_path is not None and git.is_git_repo(default_path):
            return default_path.resolve()

    start = cwd or Path.cwd()
    try:
        return git.repo_root(start)
    except git.GitError as exc:
        raise RepoContextError(str(exc)) from exc


def _resolve_candidate(candidate: str, *, allow_alias: bool) -> Path | None:
    text = candidate.strip()
    if not text:
        return None

    if allow_alias:
        try:
            alias_path = resolve_alias(text)
        except RegistryError:
            alias_path = None
        else:
            if not alias_path.exists():
                raise RepoContextError(f"Registered project path does not exist: {alias_path}")
            if not git.is_git_repo(alias_path):
                raise RepoContextError(f"Registered project is not a Git repository: {alias_path}")
            return alias_path.resolve()

    path = Path(text).expanduser()
    if path.exists():
        if git.is_git_repo(path):
            return git.repo_root(path)
        return None

    return None
