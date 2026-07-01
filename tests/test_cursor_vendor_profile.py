"""Profile reconcile: cursor vendor + company/personal profile switching (Phase 2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitmove.config import GitMoveConfig, LinkEntry, VendorEntry, config_path_for_repo
from gitmove.doctor import init_repo, run_doctor
from gitmove import link as link_mod
from gitmove import profile as profile_mod
from gitmove.profile_reconcile import compute_profile_diff
from gitmove import skip as skip_mod
from gitmove import vendor as vendor_mod


@pytest.fixture
def vendor_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "vendor-cache-root"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_VENDOR_HOME", str(home))
    return home


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_cursor_upstream(tmp_path: Path) -> Path:
    upstream = tmp_path / "cursor-spec"
    upstream.mkdir()
    _git(upstream, "init")
    _git(upstream, "config", "user.email", "cursor@test.local")
    _git(upstream, "config", "user.name", "cursor")
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "personal.mdc").write_text("personal rules", encoding="utf-8")
    _git(upstream, "add", "rules")
    _git(upstream, "commit", "-m", "init")
    _git(upstream, "branch", "-M", "main")
    return upstream


def _upstream_url(path: Path) -> str:
    return path.resolve().as_uri()


@pytest.fixture
def cursor_tracked_repo(git_repo: Path) -> Path:
    rules = git_repo / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "company.mdc").write_text("company rules", encoding="utf-8")
    _git(git_repo, "add", ".cursor")
    _git(git_repo, "commit", "-m", "add company cursor")
    init_repo(git_repo)
    return git_repo


def _write_profile(root: Path, name: str, cfg: GitMoveConfig) -> None:
    path = root / ".git" / "gitmove.profiles" / f"{name}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg.save(path)


def test_compute_profile_diff_removed_vendor() -> None:
    old = GitMoveConfig(
        vendors=[
            VendorEntry(
                name="personal-cursor",
                repo_path=".cursor",
                source_url="https://example.com/spec.git",
            )
        ],
        skip_paths=[".cursor/rules/company.mdc"],
    )
    new = GitMoveConfig(skip_paths=[])
    diff = compute_profile_diff(old, new)
    assert len(diff.removed_vendors) == 1
    assert diff.removed_vendors[0].name == "personal-cursor"
    assert ".cursor/rules/company.mdc" in diff.removed_skip_paths


def test_profile_use_company_removes_orphan_vendor_link(
    cursor_tracked_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    upstream = _init_cursor_upstream(tmp_path)
    vendor_mod.add_vendor(
        cursor_tracked_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="personal-cursor",
        migrate=True,
    )
    assert link_mod._is_reparse_point(cursor_tracked_repo / ".cursor")

    personal_cfg = skip_mod.load_config(cursor_tracked_repo)
    _write_profile(cursor_tracked_repo, "personal", personal_cfg)
    _write_profile(cursor_tracked_repo, "company", GitMoveConfig())

    profile_mod.use_profile(cursor_tracked_repo, "company")

    cursor_path = cursor_tracked_repo / ".cursor"
    assert not link_mod._is_reparse_point(cursor_path)
    assert (cursor_path / "rules" / "company.mdc").read_text(encoding="utf-8") == "company rules"


def test_profile_use_personal_creates_vendor_link(
    cursor_tracked_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    upstream = _init_cursor_upstream(tmp_path)
    vendor_mod.add_vendor(
        cursor_tracked_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="personal-cursor",
        migrate=True,
    )
    personal_cfg = skip_mod.load_config(cursor_tracked_repo)
    _write_profile(cursor_tracked_repo, "personal", personal_cfg)
    _write_profile(cursor_tracked_repo, "company", GitMoveConfig())

    profile_mod.use_profile(cursor_tracked_repo, "company")
    profile_mod.use_profile(cursor_tracked_repo, "personal")

    cursor_path = cursor_tracked_repo / ".cursor"
    assert link_mod._is_reparse_point(cursor_path)
    assert (cursor_path / "rules" / "personal.mdc").exists()


def test_profile_roundtrip_personal_company_doctor_ok(
    cursor_tracked_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    upstream = _init_cursor_upstream(tmp_path)
    vendor_mod.add_vendor(
        cursor_tracked_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="personal-cursor",
        migrate=True,
    )
    _write_profile(cursor_tracked_repo, "personal", skip_mod.load_config(cursor_tracked_repo))
    _write_profile(cursor_tracked_repo, "company", GitMoveConfig())

    profile_mod.use_profile(cursor_tracked_repo, "company")
    assert run_doctor(cursor_tracked_repo).error_count == 0
    profile_mod.use_profile(cursor_tracked_repo, "personal")
    assert run_doctor(cursor_tracked_repo).error_count == 0


def test_profile_switch_syncs_skip_paths(
    cursor_tracked_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    upstream = _init_cursor_upstream(tmp_path)
    vendor_mod.add_vendor(
        cursor_tracked_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="personal-cursor",
        migrate=True,
    )
    cfg = skip_mod.load_config(cursor_tracked_repo)
    assert any(p.startswith(".cursor/") for p in cfg.skip_paths)

    _write_profile(cursor_tracked_repo, "personal", cfg)
    _write_profile(cursor_tracked_repo, "company", GitMoveConfig())

    profile_mod.use_profile(cursor_tracked_repo, "company")

    skip_active, _ = git_ls_skip(cursor_tracked_repo)
    assert not any(p.startswith(".cursor/") for p in skip_active)


def test_profile_use_dry_run_does_not_remove_vendor_link(
    cursor_tracked_repo: Path, vendor_home: Path, tmp_path: Path,
) -> None:
    upstream = _init_cursor_upstream(tmp_path)
    vendor_mod.add_vendor(
        cursor_tracked_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="personal-cursor",
        migrate=True,
    )
    _write_profile(cursor_tracked_repo, "personal", skip_mod.load_config(cursor_tracked_repo))
    _write_profile(cursor_tracked_repo, "company", GitMoveConfig())

    profile_mod.use_profile(cursor_tracked_repo, "company", dry_run=True)

    assert link_mod._is_reparse_point(cursor_tracked_repo / ".cursor")
    assert profile_mod.active_profile_name(cursor_tracked_repo) is None


def git_ls_skip(root: Path) -> tuple[set[str], set[str]]:
    from gitmove import git

    return git.ls_files_index(root)
