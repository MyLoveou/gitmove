"""Unified JSON envelope for MCP tools and CLI --json."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from gitmove.errors import GitMoveError, error_to_dict


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def success(*, tool: str, repo: str | None, data: Any) -> str:
    payload = {
        "ok": True,
        "tool": tool,
        "repo": repo,
        "data": _serialize(data),
        "remediation": None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def failure(*, tool: str, err: GitMoveError | Exception, repo: str | None = None) -> str:
    if isinstance(err, GitMoveError):
        payload = error_to_dict(err)
        payload["ok"] = False
        payload["tool"] = tool
        payload["repo"] = repo
        return json.dumps(payload, ensure_ascii=False, indent=2)
    payload = {
        "ok": False,
        "tool": tool,
        "repo": repo,
        "code": "INTERNAL_ERROR",
        "message": str(err),
        "cause": "",
        "steps": [],
        "doc_anchor": None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
