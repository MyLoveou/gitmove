from __future__ import annotations

from pathlib import Path

from gitmove.doctor import apply_all, run_doctor
from gitmove import skip as skip_mod


def test_doctor_warns_missing_skip_path(git_repo: Path) -> None:
    cfg = skip_mod.load_config(git_repo)
    cfg.skip_paths = ["missing.txt"]
    skip_mod.save_config(git_repo, cfg)
    report = run_doctor(git_repo)
    assert any(i.level == "warn" and "missing.txt" in i.message for i in report.issues)


def test_apply_all_returns_report(git_repo: Path) -> None:
    skip_mod.add_skip(git_repo, "tracked.txt")
    report = apply_all(git_repo)
    assert report.skip
    assert report.links == []
    assert report.worktrees == []
