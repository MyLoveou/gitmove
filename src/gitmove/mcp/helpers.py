"""Shared helpers for MCP tool implementations."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from gitmove.api.response import failure, success
from gitmove.errors import GitMoveError, catalog_error, wrap_exception
from gitmove.repo_context import RepoContextError, resolve_repo_root

T = TypeVar("T")


def resolve_repo(repo: str | None = None, alias: str | None = None) -> Path:
    candidate = repo or alias
    return resolve_repo_root(repo_opt=candidate, env_repo=os.environ.get("GITMOVE_REPO"))


def check_confirm(tool: str, confirm: bool) -> str | None:
    """Return failure JSON when confirm/write gate blocks the tool."""
    if not confirm:
        return failure(tool=tool, err=catalog_error("CONFIRM_REQUIRED", message="写操作须 confirm=true"))
    if os.environ.get("GITMOVE_MCP_ALLOW_WRITE", "0") != "1":
        return failure(
            tool=tool,
            err=catalog_error(
                "MCP_WRITE_DISABLED",
                message="写操作被禁用，请设置 GITMOVE_MCP_ALLOW_WRITE=1",
            ),
        )
    return None


def serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if is_dataclass(value) and not isinstance(value, type):
        return {key: serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def run_tool(tool: str, fn: Callable[[], T], *, repo: str | None = None) -> str:
    try:
        data = fn()
        return success(tool=tool, repo=repo, data=serialize(data))
    except Exception as exc:  # noqa: BLE001 — map to JSON envelope
        return failure(tool=tool, err=wrap_exception(exc), repo=repo)


def run_repo_tool(
    tool: str,
    repo: str | None,
    alias: str | None,
    fn: Callable[[Path], T],
) -> str:
    try:
        root = resolve_repo(repo, alias)
    except RepoContextError as exc:
        return failure(tool=tool, err=GitMoveError("REPO_NOT_GIT", str(exc)))
    try:
        data = fn(root)
        return success(tool=tool, repo=str(root), data=serialize(data))
    except Exception as exc:  # noqa: BLE001
        return failure(tool=tool, err=wrap_exception(exc), repo=str(root) if "root" in locals() else None)
