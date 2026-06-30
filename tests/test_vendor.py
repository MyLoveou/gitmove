"""Tests for upstream vendor (cache clone + whole-repo link)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from gitmove import git
from gitmove.doctor import init_repo, run_doctor
from gitmove import link as link_mod
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


def _init_upstream(tmp_path: Path) -> Path:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init")
    _git(upstream, "config", "user.email", "vendor@test.local")
    _git(upstream, "config", "user.name", "vendor")
    (upstream / "README.md").write_text("upstream", encoding="utf-8")
    _git(upstream, "add", "README.md")
    _git(upstream, "commit", "-m", "init")
    _git(upstream, "branch", "-M", "main")
    return upstream


def _upstream_url(path: Path) -> str:
    return path.resolve().as_uri()


def test_add_vendor_clone_and_link(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="company-tools",
    )
    assert entry.name == "company-tools"
    assert entry.repo_path == "tools"
    assert (git_repo / "tools" / "README.md").read_text(encoding="utf-8") == "upstream"
    assert Path(entry.cache_path).exists()
    cfg = skip_mod.load_config(git_repo)
    assert len(cfg.vendors) == 1


def test_add_vendor_rejects_existing_dir_without_migrate(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    tools = git_repo / "tools"
    tools.mkdir()
    (tools / "local.txt").write_text("local", encoding="utf-8")
    upstream = _init_upstream(tmp_path)
    with pytest.raises(FileExistsError, match="--migrate"):
        vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream))
    assert not (vendor_home / "tools").exists()


def test_link_add_rejects_vendor_path(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    with pytest.raises(FileExistsError, match="vendor"):
        link_mod.add_link(git_repo, "tools", str(tmp_path / "ext"))


def test_vendor_sync_aborts_non_ff(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    cache = Path(entry.cache_path)
    (cache / "local.txt").write_text("local", encoding="utf-8")
    vendor_mod._commit_cache_changes(cache, "local commit")
    (upstream / "diverge.txt").write_text("d", encoding="utf-8")
    _git(upstream, "add", "diverge.txt")
    _git(upstream, "commit", "-m", "diverge")
    with pytest.raises(vendor_mod.VendorError):
        vendor_mod.sync_vendor(git_repo, "tools")


def test_add_vendor_migrate_tracked_path(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    cursor = git_repo / ".cursor"
    cursor.mkdir()
    rules = cursor / "rules.md"
    rules.write_text("team rules", encoding="utf-8")
    _git(git_repo, "add", ".cursor/rules.md")
    _git(git_repo, "commit", "-m", "track cursor")

    upstream = _init_upstream(tmp_path)
    (upstream / "rules.md").write_text("upstream rules", encoding="utf-8")
    _git(upstream, "add", "rules.md")
    _git(upstream, "commit", "-m", "add rules")

    entry = vendor_mod.add_vendor(
        git_repo,
        ".cursor",
        source_url=_upstream_url(upstream),
        name="cursor-spec",
        migrate=True,
    )
    assert link_mod._is_reparse_point(git_repo / ".cursor")
    cfg = skip_mod.load_config(git_repo)
    assert ".cursor/rules.md" in cfg.skip_paths
    assert ".cursor/rules.md" in git.ls_files_skip_worktree(git_repo)


def test_vendor_sync_ff_only(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    (upstream / "v2.txt").write_text("v2", encoding="utf-8")
    _git(upstream, "add", "v2.txt")
    _git(upstream, "commit", "-m", "v2")

    result = vendor_mod.sync_vendor(git_repo, "tools")
    assert result.updated is True
    assert (git_repo / "tools" / "v2.txt").read_text(encoding="utf-8") == "v2"


def test_vendor_sync_aborts_on_dirty_cache(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    cache = Path(entry.cache_path)
    (cache / "dirty.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(vendor_mod.VendorError, match="uncommitted"):
        vendor_mod.sync_vendor(git_repo, "tools")


def test_add_vendor_rejects_link_conflict(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    ext = tmp_path / "external"
    ext.mkdir()
    link_mod.add_link(git_repo, "tools", str(ext))
    upstream = _init_upstream(tmp_path)
    with pytest.raises(vendor_mod.VendorError, match="link"):
        vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream))


def test_remove_vendor_keeps_skip_by_default(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    cursor = git_repo / ".cursor"
    cursor.mkdir()
    rules = cursor / "rules.md"
    rules.write_text("x", encoding="utf-8")
    _git(git_repo, "add", ".cursor/rules.md")
    _git(git_repo, "commit", "-m", "c")
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(
        git_repo, ".cursor", source_url=_upstream_url(upstream), name="c", migrate=True
    )
    vendor_mod.remove_vendor(git_repo, "c", keep_skip=True)
    cfg = skip_mod.load_config(git_repo)
    assert ".cursor/rules.md" in cfg.skip_paths
    assert len(cfg.vendors) == 0


def test_apply_vendors_restores_link(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    link_path = git_repo / "tools"
    link_mod._remove_link_path(link_path)
    assert not link_path.exists()
    vendor_mod.apply_vendors(git_repo)
    assert link_path.exists()
    assert (link_path / "README.md").exists()


def test_doctor_reports_vendor_link_error(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    (git_repo / "tools").rename(git_repo / "tools-broken")
    report = run_doctor(git_repo)
    assert any(issue.category == "vendor" and issue.level == "error" for issue in report.issues)


def test_sync_all_reports_partial_failure(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    (tmp_path / "u1").mkdir(parents=True)
    (tmp_path / "u2").mkdir(parents=True)
    up1 = _init_upstream(tmp_path / "u1")
    up2 = _init_upstream(tmp_path / "u2")
    e1 = vendor_mod.add_vendor(git_repo, "a", source_url=_upstream_url(up1), name="a")
    vendor_mod.add_vendor(git_repo, "b", source_url=_upstream_url(up2), name="b")
    cache = Path(e1.cache_path)
    (cache / "dirty.txt").write_text("x", encoding="utf-8")
    results = vendor_mod.sync_all_vendors(git_repo)
    assert len(results) == 2
    assert results[0].ok != results[1].ok


def test_remove_vendor_purge_cache_and_unskip(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    cursor = git_repo / ".cursor"
    cursor.mkdir()
    rules = cursor / "rules.md"
    rules.write_text("x", encoding="utf-8")
    _git(git_repo, "add", ".cursor/rules.md")
    _git(git_repo, "commit", "-m", "c")
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(
        git_repo, ".cursor", source_url=_upstream_url(upstream), name="c", migrate=True
    )
    cache = Path(entry.cache_path)
    vendor_mod.remove_vendor(git_repo, "c", purge_cache=True, keep_skip=False)
    cfg = skip_mod.load_config(git_repo)
    assert ".cursor/rules.md" not in cfg.skip_paths
    assert not cache.exists()


def test_vendor_status_reports_behind(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    (upstream / "new.txt").write_text("n", encoding="utf-8")
    _git(upstream, "add", "new.txt")
    _git(upstream, "commit", "-m", "new")
    status = vendor_mod.vendor_status(git_repo, "tools", fetch=True)
    assert status.ok
    assert status.message and "behind=1" in status.message


def test_add_vendor_invalid_name(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    with pytest.raises(vendor_mod.VendorError, match="Invalid vendor name"):
        vendor_mod.add_vendor(
            git_repo,
            "tools",
            source_url=_upstream_url(upstream),
            name="bad name!",
        )


def test_add_vendor_re_add_same_path_errors(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    with pytest.raises(vendor_mod.VendorError, match="already has vendor"):
        vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools2")


def test_remove_link_rejects_vendor_path(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    with pytest.raises(FileExistsError, match="vendor"):
        link_mod.remove_link(git_repo, "tools")


def test_doctor_vendor_skip_error(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    cursor = git_repo / ".cursor"
    cursor.mkdir()
    rules = cursor / "rules.md"
    rules.write_text("x", encoding="utf-8")
    _git(git_repo, "add", ".cursor/rules.md")
    _git(git_repo, "commit", "-m", "c")
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(
        git_repo, ".cursor", source_url=_upstream_url(upstream), name="c", migrate=True
    )
    git.update_index_skip(git_repo, ".cursor/rules.md", skip=False)
    report = run_doctor(git_repo)
    assert any(issue.category == "vendor" and issue.level == "error" for issue in report.issues)


def test_vendor_not_found_errors(git_repo: Path) -> None:
    init_repo(git_repo)
    with pytest.raises(vendor_mod.VendorError):
        vendor_mod.sync_vendor(git_repo, "missing")
    with pytest.raises(vendor_mod.VendorError):
        vendor_mod.remove_vendor(git_repo, "missing")


def test_apply_vendors_recreates_missing_cache(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    cache = Path(entry.cache_path)
    vendor_mod._purge_cache_dir(cache)
    link_mod._remove_link_path(git_repo / "tools")
    vendor_mod.apply_vendors(git_repo)
    assert cache.exists()
    assert (git_repo / "tools" / "README.md").exists()


def test_vendor_status_cache_missing(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    vendor_mod._purge_cache_dir(Path(entry.cache_path))
    result = vendor_mod.vendor_status(git_repo, "tools", fetch=False)
    assert result.ok is False
    assert result.message == "cache missing"


def test_default_vendor_name_sanitizes() -> None:
    assert vendor_mod.default_vendor_name(".cursor") == "cursor"
    assert vendor_mod.default_vendor_name("tools/pkg") == "tools-pkg"
    assert vendor_mod.default_vendor_name("weird@repo") == "weird-repo"


def test_add_vendor_rollback_on_link_failure(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    with mock.patch("gitmove.vendor.link_mod.create_link", side_effect=RuntimeError("link failed")):
        with pytest.raises(RuntimeError, match="link failed"):
            vendor_mod.add_vendor(
                git_repo, "tools", source_url=_upstream_url(upstream), name="tools"
            )
    assert skip_mod.load_config(git_repo).vendors == []


def test_add_vendor_auto_skip_disabled(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    tracked = git_repo / "tools" / "tracked.txt"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("t", encoding="utf-8")
    _git(git_repo, "add", "tools/tracked.txt")
    _git(git_repo, "commit", "-m", "track tools")
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(
        git_repo,
        "tools",
        source_url=_upstream_url(upstream),
        name="tools",
        migrate=True,
        auto_skip_tracked=False,
    )
    cfg = skip_mod.load_config(git_repo)
    assert "tools/tracked.txt" not in cfg.skip_paths


def test_sync_vendor_by_repo_path(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    (upstream / "v2.txt").write_text("v2", encoding="utf-8")
    _git(upstream, "add", "v2.txt")
    _git(upstream, "commit", "-m", "v2")
    result = vendor_mod.sync_vendor(git_repo, "tools")
    assert result.ok and result.updated


def test_sync_vendor_fetch_failure(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    with (
        mock.patch("gitmove.vendor._cache_dirty", return_value=False),
        mock.patch("gitmove.vendor.git.run_git") as run_git,
    ):
        run_git.return_value.returncode = 1
        run_git.return_value.stderr = "fetch failed"
        with pytest.raises(vendor_mod.VendorError, match="fetch failed"):
            vendor_mod.sync_vendor(git_repo, "tools", fetch=True)


def test_vendor_status_dirty_reports_not_ok(
    git_repo: Path, vendor_home: Path, tmp_path: Path
) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    entry = vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    (Path(entry.cache_path) / "dirty.txt").write_text("d", encoding="utf-8")
    result = vendor_mod.vendor_status(git_repo, "tools", fetch=False)
    assert result.ok is False
    assert result.message and "dirty" in result.message


def test_vendor_status_fetch_failure(git_repo: Path, vendor_home: Path, tmp_path: Path) -> None:
    init_repo(git_repo)
    upstream = _init_upstream(tmp_path)
    vendor_mod.add_vendor(git_repo, "tools", source_url=_upstream_url(upstream), name="tools")
    with mock.patch("gitmove.vendor.git.run_git") as run_git:
        run_git.return_value.returncode = 1
        run_git.return_value.stderr = "network down"
        result = vendor_mod.vendor_status(git_repo, "tools", fetch=True)
    assert result.ok is False
    assert result.message == "network down"
