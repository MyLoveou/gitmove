"""Phase 2 tests: F7 pin, F12 check-updates, F11 update, F10 scan, F8 hooks, F9 profile."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from gitmove import git
from gitmove.doctor import init_repo, run_doctor
from gitmove.errors import GitMoveError
from gitmove import hooks as hooks_mod
from gitmove import profile as profile_mod
from gitmove import projects as projects_mod
from gitmove import skip as skip_mod
from gitmove import vendor as vendor_mod
from gitmove.registry import add_project, list_projects


@pytest.fixture
def vendor_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "vendor-cache-root"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_VENDOR_HOME", str(home))
    return home


@pytest.fixture
def registry_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "gitmove-home"
    home.mkdir()
    monkeypatch.setenv("GITMOVE_HOME", str(home))
    return home


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_upstream(tmp_path: Path) -> Path:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init")
    _git(upstream, "config", "user.email", "vendor@test.local")
    _git(upstream, "config", "user.name", "vendor")
    (upstream / "README.md").write_text("v1", encoding="utf-8")
    _git(upstream, "add", "README.md")
    _git(upstream, "commit", "-m", "init")
    _git(upstream, "branch", "-M", "main")
    return upstream


def _upstream_url(path: Path) -> str:
    return path.resolve().as_uri()


def _tag_upstream(upstream: Path, tag: str) -> str:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=upstream,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(upstream, "tag", tag)
    return commit


def test_add_vendor_with_pin_tag(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    _tag_upstream(upstream, "v1.0.0")
    (upstream / "v2.txt").write_text("v2", encoding="utf-8")
    _git(upstream, "add", "v2.txt")
    _git(upstream, "commit", "-m", "v2")

    entry = vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    assert entry.source_pin == "v1.0.0"
    cache = Path(entry.cache_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cache,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tag_commit = subprocess.run(
        ["git", "rev-parse", "v1.0.0"],
        cwd=cache,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == tag_commit
    assert not (git_repo / "tools" / "v2.txt").exists()


def test_vendor_status_shows_pin_drift(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    _tag_upstream(upstream, "v1.0.0")
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cache = Path(vendor_mod.list_vendors(git_repo)[0].cache_path)
    (upstream / "ahead.txt").write_text("a", encoding="utf-8")
    _git(upstream, "add", "ahead.txt")
    _git(upstream, "commit", "-m", "ahead")
    _git(cache, "fetch", "origin")
    _git(cache, "merge", "--ff-only", "origin/main")

    result = vendor_mod.vendor_status(git_repo, "tools", fetch=False)
    assert result.source_pin == "v1.0.0"
    assert result.pinned_drift is True


def test_vendor_sync_ff_to_pin(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    tag_commit = _tag_upstream(upstream, "v1.0.0")
    (upstream / "v2.txt").write_text("v2", encoding="utf-8")
    _git(upstream, "add", "v2.txt")
    _git(upstream, "commit", "-m", "v2")

    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cache = Path(vendor_mod.list_vendors(git_repo)[0].cache_path)
    _git(cache, "fetch", "origin")
    _git(cache, "checkout", "main")
    _git(cache, "merge", "--ff-only", "origin/main")

    result = vendor_mod.sync_vendor(git_repo, "tools", fetch=True)
    assert result.ok
    assert result.updated
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cache,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == tag_commit


def test_vendor_updates_exit_code(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
    )
    (upstream / "new.txt").write_text("n", encoding="utf-8")
    _git(upstream, "add", "new.txt")
    _git(upstream, "commit", "-m", "new")

    results = vendor_mod.check_vendor_updates(git_repo, fetch=True)
    assert vendor_mod.vendor_updates_exit_code(results) == 2

    vendor_mod.sync_vendor(git_repo, "tools", fetch=True)
    results = vendor_mod.check_vendor_updates(git_repo, fetch=True)
    assert vendor_mod.vendor_updates_exit_code(results) == 0


def test_batch_update_ff_only(git_repo: Path, registry_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote = tmp_path / "remote.git"
    _git(tmp_path, "clone", "--bare", str(git_repo), str(remote))
    _git(git_repo, "remote", "add", "origin", str(remote))
    _git(git_repo, "push", "-u", "origin", branch)

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(remote), str(clone))
    _git(clone, "config", "user.email", "u@test.local")
    _git(clone, "config", "user.name", "u")
    (git_repo / "tracked.txt").write_text("local", encoding="utf-8")
    _git(git_repo, "add", "tracked.txt")
    _git(git_repo, "commit", "-m", "local")
    _git(git_repo, "push", "origin", branch)

    add_project(clone, alias="app")
    rows = projects_mod.batch_update(
        [projects_mod.iter_projects()[0]],
        ff_only=True,
    )
    assert rows[0].pulled is True
    assert rows[0].old_commit != rows[0].new_commit


def test_batch_update_skips_dirty(git_repo: Path, registry_home: Path) -> None:
    init_repo(git_repo)
    add_project(git_repo, alias="dirty")
    (git_repo / "tracked.txt").write_text("dirty", encoding="utf-8")
    rows = projects_mod.batch_update(
        [projects_mod.iter_projects()[0]],
        ff_only=True,
    )
    assert rows[0].pulled is False
    assert rows[0].message and "dirty" in rows[0].message.lower()


def test_scan_finds_git_roots(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    repo_a = root / "alpha"
    repo_a.mkdir()
    _git(repo_a, "init")
    _git(repo_a, "config", "user.email", "a@test.local")
    _git(repo_a, "config", "user.name", "a")
    (repo_a / "f.txt").write_text("a", encoding="utf-8")
    _git(repo_a, "add", "f.txt")
    _git(repo_a, "commit", "-m", "init")

    nested = root / "pkg" / "beta"
    nested.parent.mkdir()
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "user.email", "b@test.local")
    _git(nested, "config", "user.name", "b")
    (nested / "f.txt").write_text("b", encoding="utf-8")
    _git(nested, "add", "f.txt")
    _git(nested, "commit", "-m", "init")

    found = projects_mod.scan_git_roots(root, max_depth=4)
    paths = {p.resolve() for p in found}
    assert repo_a.resolve() in paths
    assert nested.resolve() in paths


def test_scan_registers_with_yes(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    repo = root / "solo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "s@test.local")
    _git(repo, "config", "user.name", "s")
    (repo / "f.txt").write_text("s", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-m", "init")

    results = projects_mod.scan_and_register(
        root,
        max_depth=2,
        yes=True,
    )
    assert len(results) == 1
    assert results[0].registered is True
    aliases = [p.alias for p in list_projects()]
    assert "solo" in aliases


def test_hooks_install_uninstall_idempotent(git_repo: Path) -> None:
    init_repo(git_repo)
    hooks_mod.install_hooks(git_repo, post_merge=True, run_cmd="apply")
    status = hooks_mod.hooks_status(git_repo)
    assert status.post_merge_installed
    hooks_mod.uninstall_hooks(git_repo)
    status = hooks_mod.hooks_status(git_repo)
    assert not status.post_merge_installed
    hooks_mod.install_hooks(git_repo, post_merge=True, run_cmd="apply")
    hooks_mod.install_hooks(git_repo, post_merge=True, run_cmd="apply")
    assert hooks_mod.hooks_status(git_repo).post_merge_installed


def test_hooks_rejects_existing_third_party(git_repo: Path) -> None:
    init_repo(git_repo)
    hook = git_repo / ".git" / "hooks" / "post-merge"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
    with pytest.raises(GitMoveError) as exc_info:
        hooks_mod.install_hooks(git_repo, post_merge=True, run_cmd="apply")
    assert exc_info.value.code == "HOOK_EXISTS"


def test_profile_save_use_roundtrip(git_repo: Path) -> None:
    init_repo(git_repo)
    skip_mod.add_skip(git_repo, "tracked.txt")
    profile_mod.save_profile(git_repo, "work")
    skip_mod.remove_skip(git_repo, "tracked.txt", persist=True)

    profile_mod.use_profile(git_repo, "work")
    cfg = skip_mod.load_config(git_repo)
    assert "tracked.txt" in cfg.skip_paths
    assert profile_mod.active_profile_name(git_repo) == "work"


def test_profile_not_found(git_repo: Path) -> None:
    init_repo(git_repo)
    with pytest.raises(GitMoveError) as exc_info:
        profile_mod.use_profile(git_repo, "missing")
    assert exc_info.value.code == "PROFILE_NOT_FOUND"


def test_scan_respects_max_depth(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    deep = root / "a" / "b" / "c" / "deep-repo"
    deep.mkdir(parents=True)
    _git(deep, "init")
    _git(deep, "config", "user.email", "d@test.local")
    _git(deep, "config", "user.name", "d")
    (deep / "f.txt").write_text("d", encoding="utf-8")
    _git(deep, "add", "f.txt")
    _git(deep, "commit", "-m", "init")

    shallow_found = projects_mod.scan_git_roots(root, max_depth=2)
    deep_found = projects_mod.scan_git_roots(root, max_depth=6)
    assert not shallow_found
    assert deep.resolve() in {p.resolve() for p in deep_found}


def test_hooks_post_checkout(git_repo: Path) -> None:
    init_repo(git_repo)
    hooks_mod.install_hooks(git_repo, post_merge=False, post_checkout=True, run_cmd="doctor")
    status = hooks_mod.hooks_status(git_repo)
    assert status.post_checkout_installed
    assert status.post_checkout_run == "doctor"


def test_vendor_pin_not_found_in_status(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    _tag_upstream(upstream, "v1.0.0")
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cfg = skip_mod.load_config(git_repo)
    cfg.vendors[0].source_pin = "nonexistent-tag"
    skip_mod.save_config(git_repo, cfg)
    result = vendor_mod.vendor_status(git_repo, "tools", fetch=False)
    assert result.ok is False
    assert result.error_code == "VENDOR_PIN_NOT_FOUND"


def test_profile_save_requires_config(git_repo: Path) -> None:
    with pytest.raises(GitMoveError) as exc_info:
        profile_mod.save_profile(git_repo, "work")
    assert exc_info.value.code == "CONFIG_NOT_FOUND"


def test_profile_delete_clears_active(git_repo: Path) -> None:
    init_repo(git_repo)
    profile_mod.save_profile(git_repo, "work")
    profile_mod.use_profile(git_repo, "work")
    profile_mod.delete_profile(git_repo, "work")
    assert profile_mod.active_profile_name(git_repo) is None


def test_batch_update_exit_code_on_pull_failure(git_repo: Path, registry_home: Path) -> None:
    init_repo(git_repo)
    add_project(git_repo, alias="bad-pull")
    entry = projects_mod.iter_projects()[0]
    with mock.patch("gitmove.projects._working_tree_dirty", return_value=False):
        with mock.patch("gitmove.projects._repo_head", return_value="abc1234"):
            with mock.patch("gitmove.projects.git.run_git") as run_git:
                run_git.return_value = mock.Mock(returncode=1, stdout="", stderr="pull failed")
                rows = projects_mod.batch_update([entry], ff_only=True)
    assert rows[0].message == "pull failed"
    assert projects_mod.batch_update_exit_code(rows) == 1


def test_scan_dry_run_lists_without_register(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    repo = root / "solo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "s@test.local")
    _git(repo, "config", "user.name", "s")
    (repo / "f.txt").write_text("s", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-m", "init")

    results = projects_mod.scan_and_register(root, max_depth=2, dry_run=True)
    assert len(results) == 1
    assert results[0].registered is False
    assert results[0].message == "dry-run"
    assert not list_projects()


def test_scan_skips_registered_and_node_modules(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    repo = root / "app"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "a@test.local")
    _git(repo, "config", "user.name", "a")
    (repo / "f.txt").write_text("a", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-m", "init")
    add_project(repo, alias="app")

    noise = root / "node_modules" / "pkg"
    noise.mkdir(parents=True)
    _git(noise, "init")

    assert projects_mod.scan_git_roots(root, max_depth=3) == []


def test_scan_register_chooser_can_skip(tmp_path: Path, registry_home: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    repo = root / "solo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "s@test.local")
    _git(repo, "config", "user.name", "s")
    (repo / "f.txt").write_text("s", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-m", "init")

    results = projects_mod.scan_and_register(
        root,
        max_depth=2,
        chooser=lambda _path, _alias: False,
    )
    assert results[0].skipped is True
    assert results[0].registered is False


def test_profile_use_dry_run(git_repo: Path) -> None:
    init_repo(git_repo)
    profile_mod.save_profile(git_repo, "work")
    skip_mod.remove_skip(git_repo, "tracked.txt", persist=True)
    profile_mod.use_profile(git_repo, "work", dry_run=True)
    assert "tracked.txt" not in skip_mod.load_config(git_repo).skip_paths


def test_doctor_warns_vendor_pin_drift(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    _tag_upstream(upstream, "v1.0.0")
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cache = Path(vendor_mod.list_vendors(git_repo)[0].cache_path)
    (upstream / "ahead.txt").write_text("a", encoding="utf-8")
    _git(upstream, "add", "ahead.txt")
    _git(upstream, "commit", "-m", "ahead")
    _git(cache, "fetch", "origin")
    _git(cache, "checkout", "main")
    _git(cache, "merge", "--ff-only", "origin/main")

    report = run_doctor(git_repo)
    messages = [issue.message for issue in report.issues]
    assert any("pin drift" in msg for msg in messages)


def test_vendor_exit_code_error() -> None:
    result = vendor_mod.VendorSyncResult("bad", ok=False, message="cache missing")
    assert vendor_mod.vendor_updates_exit_code([result]) == 1


def test_batch_update_dry_run_and_missing(git_repo: Path, registry_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    add_project(git_repo, alias="ok")
    rows = projects_mod.batch_update([projects_mod.iter_projects()[0]], dry_run=True)
    assert rows[0].message == "dry-run"

    from gitmove.registry import ProjectEntry

    missing = tmp_path / "missing"
    rows = projects_mod.batch_update(
        [ProjectEntry(path=missing.resolve(), alias="gone")],
        dry_run=False,
    )
    assert rows[0].status == "MISSING"


def test_profile_invalid_name(git_repo: Path) -> None:
    init_repo(git_repo)
    with pytest.raises(GitMoveError) as exc_info:
        profile_mod.save_profile(git_repo, "bad name!")
    assert exc_info.value.code == "PROFILE_INVALID_NAME"


def test_scan_root_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        projects_mod.scan_git_roots(tmp_path / "missing")


def test_unique_alias_suffix(registry_home: Path, git_repo: Path) -> None:
    init_repo(git_repo)
    add_project(git_repo, alias="solo")
    assert projects_mod._unique_alias("solo", {"solo"}) == "solo-2"


def test_doctor_vendor_pin_not_found(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    _tag_upstream(upstream, "v1.0.0")
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cfg = skip_mod.load_config(git_repo)
    cfg.vendors[0].source_pin = "missing-tag"
    skip_mod.save_config(git_repo, cfg)
    issues = vendor_mod.check_vendors_for_doctor(git_repo, fetch_behind=True)
    assert any("pin not found" in msg for _lvl, _cat, msg in issues)


def test_hooks_invalid_run_cmd(git_repo: Path) -> None:
    init_repo(git_repo)
    with pytest.raises(ValueError, match="Invalid run command"):
        hooks_mod.install_hooks(git_repo, run_cmd="invalid")


def test_profile_list_empty(git_repo: Path) -> None:
    assert profile_mod.list_profiles(git_repo) == []


def test_apply_vendors_restores_pin_after_cache_missing(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    tag_commit = _tag_upstream(upstream, "v1.0.0")
    (upstream / "v2.txt").write_text("v2", encoding="utf-8")
    _git(upstream, "add", "v2.txt")
    _git(upstream, "commit", "-m", "v2")

    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin="v1.0.0",
    )
    cache = Path(vendor_mod.list_vendors(git_repo)[0].cache_path)
    vendor_mod._purge_cache_dir(cache)

    vendor_mod.apply_vendors(git_repo)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cache,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == tag_commit


def test_is_git_root_rejects_submodule_gitfile(tmp_path: Path) -> None:
    sub = tmp_path / "submodule"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n", encoding="utf-8")
    assert projects_mod._is_git_root(sub) is False


def test_add_vendor_with_pin_sha(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    first_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=upstream,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    entry = vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        source_pin=first_commit,
        shallow=True,
    )
    cfg = skip_mod.load_config(git_repo)
    assert cfg.vendors[0].source_pin == first_commit

    cache = Path(entry.cache_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cache,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == first_commit


def test_batch_update_ff_failed_sets_error_code(git_repo: Path, registry_home: Path) -> None:
    init_repo(git_repo)
    add_project(git_repo, alias="bad-pull")
    entry = projects_mod.iter_projects()[0]
    with mock.patch("gitmove.projects._working_tree_dirty", return_value=False):
        with mock.patch("gitmove.projects._repo_head", return_value="abc1234"):
            with mock.patch("gitmove.projects.git.run_git") as run_git:
                run_git.return_value = mock.Mock(returncode=1, stdout="", stderr="not possible to fast-forward")
                rows = projects_mod.batch_update([entry], ff_only=True)
    assert rows[0].error_code == "PROJECTS_UPDATE_FF_FAILED"
