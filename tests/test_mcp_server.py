"""Tests for MCP tool handlers and JSON responses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitmove.mcp import impl as mcp_impl


def test_gitmove_doctor_on_git_repo(git_repo: Path) -> None:
    raw = mcp_impl.doctor_impl(repo=str(git_repo))
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["tool"] == "gitmove_doctor"
    assert Path(payload["repo"]) == git_repo.resolve()


def test_gitmove_explain_error_known_code() -> None:
    raw = mcp_impl.explain_error_impl("REPO_NOT_GIT")
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["data"]["code"] == "REPO_NOT_GIT"


def test_gitmove_apply_requires_confirm(git_repo: Path) -> None:
    raw = mcp_impl.apply_impl(repo=str(git_repo), confirm=False)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["code"] == "CONFIRM_REQUIRED"


def test_gitmove_skip_add_requires_confirm(git_repo: Path) -> None:
    raw = mcp_impl.skip_add_impl(".cursor", repo=str(git_repo), confirm=False)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["code"] == "CONFIRM_REQUIRED"


def test_gitmove_skip_list_on_init_repo(git_repo: Path) -> None:
    from gitmove.doctor import init_repo

    init_repo(git_repo)
    raw = mcp_impl.skip_list_impl(repo=str(git_repo))
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["tool"] == "gitmove_skip_list"
    assert isinstance(payload["data"], list)


def test_gitmove_link_list_empty(git_repo: Path) -> None:
    from gitmove.doctor import init_repo

    init_repo(git_repo)
    raw = mcp_impl.link_list_impl(repo=str(git_repo))
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["data"] == []


def test_gitmove_vendor_template_list() -> None:
    raw = mcp_impl.vendor_template_list_impl()
    payload = json.loads(raw)
    assert payload["ok"] is True
    ids = [item["id"] for item in payload["data"]]
    assert "cursor-spec" in ids


def test_gitmove_list_projects_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    raw = mcp_impl.list_projects_impl()
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["data"] == []


def test_gitmove_repo_summary_uninitialized(git_repo: Path) -> None:
    raw = mcp_impl.repo_summary_impl(repo=str(git_repo))
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["data"]["initialized"] is False


def test_gitmove_sync_pull_blocked_on_conflict(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from gitmove.doctor import init_repo
    from gitmove.mcp import impl as mcp_impl
    from gitmove.sync import SyncCheckReport, SyncConflictBlocked, SyncDrift

    init_repo(git_repo)
    monkeypatch.setenv("GITMOVE_MCP_ALLOW_WRITE", "1")
    report = SyncCheckReport(
        upstream="origin/main",
        drifts=[
            SyncDrift(
                path="a.txt",
                local_modified=True,
                remote_modified=True,
                skip_active=True,
                in_config=True,
            )
        ],
    )

    def _abort(*_args, **_kwargs):
        raise SyncConflictBlocked(report)

    monkeypatch.setattr("gitmove.mcp.impl.sync_mod.sync_pull_abort_on_conflict", _abort)
    raw = mcp_impl.sync_pull_impl(repo=str(git_repo), confirm=True)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["code"] == "SYNC_CONFLICT_BLOCKED"
    assert payload["context"]["conflicts"]


def test_gitmove_mcp_tool_count() -> None:
    from gitmove.mcp import server as mcp_server

    tool_names = [name for name in dir(mcp_server) if name.startswith("gitmove_")]
    assert len(tool_names) >= 20
