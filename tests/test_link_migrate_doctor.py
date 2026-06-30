"""Doctor warnings for migrate_skipped entries."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from gitmove.config import LinkEntry
from gitmove.doctor import run_doctor
from gitmove import skip as skip_mod


def test_doctor_warns_migrate_skipped(git_repo: Path, tmp_path: Path) -> None:
    from gitmove.doctor import init_repo

    init_repo(git_repo)
    cfg = skip_mod.load_config(git_repo)
    cfg.links = [
        LinkEntry(
            "config",
            str(tmp_path / "config"),
            "symlink",
            migrate_skipped=["nested (symlink)"],
        )
    ]
    skip_mod.save_config(git_repo, cfg)

    report = run_doctor(git_repo)
    warns = [i for i in report.issues if i.level == "warn" and "nested" in i.message]
    assert warns


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="AF_UNIX not available")
def test_migrate_skips_unix_socket(git_repo: Path, tmp_path: Path) -> None:
    from gitmove import link as link_mod
    from unittest import mock

    codegraph = git_repo / ".codegraph"
    codegraph.mkdir()
    sock_path = codegraph / "daemon.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        srv.bind(str(sock_path))
        external = tmp_path / "ext"

        with mock.patch.object(link_mod, "create_link"):
            entry = link_mod.add_link(git_repo, ".codegraph", str(external), migrate=True)

        assert any("daemon.sock" in s for s in entry.migrate_skipped)
    finally:
        srv.close()
        if sock_path.exists():
            sock_path.unlink()
