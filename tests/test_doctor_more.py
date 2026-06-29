from __future__ import annotations

from unittest import mock

from gitmove import git
from gitmove.doctor import run_doctor
from gitmove import skip as skip_mod
from gitmove.config import LinkEntry


def test_doctor_reports_missing_link(git_repo) -> None:
    cfg = skip_mod.load_config(git_repo)
    cfg.links = [LinkEntry("tools/personal", "/tmp/ext", "symlink")]
    skip_mod.save_config(git_repo, cfg)
    report = run_doctor(git_repo)
    assert any(i.category == "link" and i.level == "error" for i in report.issues)


def test_doctor_reports_inactive_skip(git_repo) -> None:
    cfg = skip_mod.load_config(git_repo)
    cfg.skip_paths = ["tracked.txt"]
    skip_mod.save_config(git_repo, cfg)
    report = run_doctor(git_repo)
    assert any(i.category == "skip" and i.level == "error" for i in report.issues)


def test_is_git_repo_false(tmp_path) -> None:
    assert git.is_git_repo(tmp_path) is False
