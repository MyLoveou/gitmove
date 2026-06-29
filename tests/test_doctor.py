from __future__ import annotations

from pathlib import Path

from gitmove.doctor import init_repo, run_doctor
from gitmove import skip as skip_mod


def test_doctor_reports_uninitialized(git_repo: Path) -> None:
    report = run_doctor(git_repo)
    assert any(i.category == "config" for i in report.issues)


def test_doctor_ok_after_init_and_apply(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "tracked.txt")
    report = run_doctor(git_repo)
    assert report.error_count == 0


def test_init_repo_sets_external_base(git_repo: Path) -> None:
    base = git_repo / "personal"
    resolved = init_repo(git_repo, str(base))
    assert resolved == base.resolve()
