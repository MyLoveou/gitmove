"""Upstream Git vendor: cache clone + whole-repo link into business repository."""

from __future__ import annotations

import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from gitmove import git
from gitmove.config import VendorEntry, normalize_rel, resolve_repo_path
from gitmove.errors import GitMoveError, catalog_error
from gitmove.exclude import sync_link_excludes
from gitmove import link as link_mod
from gitmove.platform_util import resolve_link_type
from gitmove.skip import load_config, save_config

VENDOR_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
PIN_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class VendorError(RuntimeError):
    """Invalid vendor operation."""


@dataclass
class VendorStatus:
    name: str
    repo_path: str
    source_url: str
    source_ref: str
    cache_path: Path
    link_ok: bool
    cache_exists: bool


@dataclass
class VendorSyncResult:
    name: str
    ok: bool
    updated: bool = False
    old_commit: str | None = None
    new_commit: str | None = None
    message: str | None = None
    repo_path: str = ""
    behind: int = 0
    dirty: bool = False
    pinned_drift: bool = False
    source_pin: str | None = None
    link_ok: bool = True
    head_commit: str | None = None
    error_code: str | None = None


def _purge_cache_dir(cache: Path) -> None:
    if not cache.exists():
        return

    def _on_rm_error(func, path, exc_info) -> None:  # type: ignore[no-untyped-def]
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            raise exc_info[1]  # noqa: B904

    shutil.rmtree(cache, onerror=_on_rm_error)


def vendor_cache_home() -> Path:
    override = os.environ.get("GITMOVE_VENDOR_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "gitmove-vendor"


def default_cache_path(vendor_name: str) -> Path:
    return vendor_cache_home() / vendor_name


def default_vendor_name(repo_path: str) -> str:
    cleaned = normalize_rel(repo_path).replace("/", "-").replace(".", "-").strip("-")
    name = cleaned or "vendor"
    if not VENDOR_NAME_PATTERN.match(name):
        name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-") or "vendor"
    return name[:64]


def _validate_vendor_name(name: str) -> None:
    if not VENDOR_NAME_PATTERN.match(name):
        raise VendorError(f"Invalid vendor name {name!r}: use [a-zA-Z0-9_-], 1-64 chars")


def _find_vendor(cfg, name_or_path: str) -> VendorEntry | None:
    text = normalize_rel(name_or_path)
    for entry in cfg.vendors:
        if entry.name == name_or_path or entry.repo_path == text:
            return entry
    return None


def _resolve_cache_path(entry: VendorEntry) -> Path:
    if entry.cache_path:
        return Path(entry.cache_path).expanduser().resolve()
    return default_cache_path(entry.name)


def _vendor_link_target(cache: Path, entry: VendorEntry) -> Path:
    if entry.include_paths:
        return cache / normalize_rel(entry.include_paths[0])
    return cache


def _validate_include_path(cache: Path, entry: VendorEntry) -> None:
    if not entry.include_paths:
        return
    rel = normalize_rel(entry.include_paths[0])
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise catalog_error(
            "INCLUDE_PATH_NOT_IN_CACHE",
            message=f"include_paths must stay inside cache: {rel}",
            include_path=rel,
            cache=str(cache),
        )
    target = _vendor_link_target(cache, entry)
    try:
        target.resolve().relative_to(cache.resolve())
    except ValueError as exc:
        raise catalog_error(
            "INCLUDE_PATH_NOT_IN_CACHE",
            message=f"include_paths escapes cache: {rel}",
            include_path=rel,
            cache=str(cache),
        ) from exc
    if not target.exists():
        raise catalog_error(
            "INCLUDE_PATH_NOT_IN_CACHE",
            message=f"include_paths not found in cache: {rel}",
            include_path=rel,
            cache=str(cache),
        )


def _is_correct_vendor_link(root: Path, entry: VendorEntry, cache: Path) -> bool:
    link_path = root / entry.repo_path
    expected = _vendor_link_target(cache, entry)
    if not link_mod._is_reparse_point(link_path):
        return False
    try:
        return link_path.resolve() == expected.resolve()
    except OSError:
        return False


def _clone_cache(cache: Path, source_url: str, source_ref: str, *, shallow: bool = True) -> None:
    if cache.exists():
        return
    cache.parent.mkdir(parents=True, exist_ok=True)
    args = ["clone", "--branch", source_ref, "--single-branch"]
    if shallow:
        args.extend(["--depth", "1"])
    args.extend([source_url, str(cache)])
    result = git.run_git(*args, check=False)
    if result.returncode != 0:
        if cache.exists():
            _purge_cache_dir(cache)
        stderr = result.stderr.strip() or result.stdout.strip() or "git clone failed"
        raise catalog_error("VENDOR_CLONE_FAILED", message=stderr, url=source_url)


def _commit_cache_changes(cache: Path, message: str = "gitmove vendor migrate") -> None:
    if not _cache_dirty(cache):
        return
    git.run_git("add", "-A", cwd=cache)
    result = git.run_git("commit", "-m", message, cwd=cache, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "cache commit failed"
        raise VendorError(stderr)


def _migrate_repo_path_to_cache(link_path: Path, cache: Path, *, migrate_target: Path | None = None) -> None:
    if not link_path.exists():
        return
    if link_mod._is_reparse_point(link_path):
        return
    target = migrate_target or cache
    target.parent.mkdir(parents=True, exist_ok=True)
    if link_path.is_dir():
        if target.exists():
            shutil.copytree(link_path, target, dirs_exist_ok=True)
            shutil.rmtree(link_path)
        else:
            shutil.copytree(link_path, target, dirs_exist_ok=False)
            shutil.rmtree(link_path)
    else:
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(link_path), str(target / link_path.name))


def _apply_skip_for_vendor(root: Path, entry: VendorEntry) -> None:
    if not entry.auto_skip_tracked:
        return
    cfg = load_config(root)
    tracked = git.ls_tracked_under_prefix(root, entry.repo_path)
    changed = False
    for path in tracked:
        git.update_index_skip(root, path, skip=True)
        if path not in cfg.skip_paths:
            cfg.skip_paths.append(path)
            changed = True
    if changed:
        save_config(root, cfg)


def add_vendor(
    root: Path,
    repo_rel: str,
    *,
    source_url: str,
    name: str | None = None,
    source_ref: str = "main",
    cache_path: str | None = None,
    link_type: str | None = None,
    migrate: bool = False,
    auto_skip_tracked: bool = True,
    shallow: bool = True,
    include_paths: list[str] | None = None,
    source_pin: str | None = None,
) -> VendorEntry:
    repo_path = normalize_rel(repo_rel)
    resolve_repo_path(root, repo_path)
    cfg = load_config(root)

    if any(link.repo_path == repo_path for link in cfg.links):
        raise VendorError(f"repo_path already has external link configured: {repo_path}")
    if any(vendor.repo_path == repo_path for vendor in cfg.vendors):
        raise VendorError(f"repo_path already has vendor configured: {repo_path}")

    vendor_name = name or default_vendor_name(repo_path)
    _validate_vendor_name(vendor_name)
    if any(vendor.name == vendor_name for vendor in cfg.vendors):
        raise VendorError(f"Vendor name already exists: {vendor_name}")

    resolved_type = resolve_link_type(link_type)
    cache = (
        Path(cache_path).expanduser().resolve()
        if cache_path
        else default_cache_path(vendor_name)
    )
    link_path = root / repo_path

    if link_path.exists() and not link_mod._is_reparse_point(link_path) and not migrate:
        raise catalog_error(
            "VENDOR_PATH_EXISTS",
            message=f"{repo_path} exists and is not a link. Use --migrate to move content to cache.",
            path=repo_path,
        )

    normalized_include = [normalize_rel(p) for p in (include_paths or []) if p.strip()]
    if len(normalized_include) > 1:
        raise VendorError("Only one include_paths entry is supported in v1")
    try:
        _clone_cache(cache, source_url, source_ref, shallow=shallow)
        pin_entry = VendorEntry(
            name=vendor_name,
            repo_path=repo_path,
            source_url=source_url,
            source_ref=source_ref,
            include_paths=normalized_include,
            source_pin=source_pin,
        )
        _validate_include_path(cache, pin_entry)
        _apply_pin_after_clone(cache, pin_entry)
    except Exception:
        if cache.exists():
            _purge_cache_dir(cache)
        raise

    if link_path.exists() and not link_mod._is_reparse_point(link_path):
        migrate_target = (
            cache / normalize_rel(normalized_include[0]) if normalized_include else cache
        )
        _migrate_repo_path_to_cache(link_path, cache, migrate_target=migrate_target)
        _commit_cache_changes(cache)

    entry = VendorEntry(
        name=vendor_name,
        repo_path=repo_path,
        source_url=source_url,
        source_ref=source_ref,
        cache_path=str(cache).replace("\\", "/"),
        link_type=resolved_type,
        auto_skip_tracked=auto_skip_tracked,
        shallow=shallow,
        include_paths=normalized_include,
        source_pin=source_pin,
    )

    link_target = _vendor_link_target(cache, entry)
    try:
        if not _is_correct_vendor_link(root, entry, cache):
            if link_path.exists() and link_mod._is_reparse_point(link_path):
                link_mod._remove_link_path(link_path)
            if not link_path.exists():
                link_mod.create_link(link_path, link_target, resolved_type)
        cfg.vendors.append(entry)
        save_config(root, cfg)
        _apply_skip_for_vendor(root, entry)
    except Exception:
        cfg.vendors = [vendor for vendor in cfg.vendors if vendor.name != vendor_name]
        save_config(root, cfg)
        if link_path.exists() and link_mod._is_reparse_point(link_path):
            link_mod._remove_link_path(link_path)
        raise

    sync_link_excludes(root)
    return entry


def apply_vendors(root: Path) -> list[VendorStatus]:
    cfg = load_config(root)
    statuses: list[VendorStatus] = []
    for entry in cfg.vendors:
        cache = _resolve_cache_path(entry)
        if not cache.exists():
            _clone_cache(cache, entry.source_url, entry.source_ref, shallow=entry.shallow)
            _apply_pin_after_clone(cache, entry)
        _validate_include_path(cache, entry)
        link_path = root / entry.repo_path
        link_target = _vendor_link_target(cache, entry)
        if not _is_correct_vendor_link(root, entry, cache):
            if link_path.exists() and link_mod._is_reparse_point(link_path):
                link_mod._remove_link_path(link_path)
            if not link_path.exists():
                link_mod.create_link(link_path, link_target, entry.link_type)
        _apply_skip_for_vendor(root, entry)
        statuses.append(_status_for_entry(root, entry))
    sync_link_excludes(root)
    return statuses


def list_vendors(root: Path) -> list[VendorStatus]:
    cfg = load_config(root)
    return [_status_for_entry(root, entry) for entry in cfg.vendors]


def _status_for_entry(root: Path, entry: VendorEntry) -> VendorStatus:
    cache = _resolve_cache_path(entry)
    return VendorStatus(
        name=entry.name,
        repo_path=entry.repo_path,
        source_url=entry.source_url,
        source_ref=entry.source_ref,
        cache_path=cache,
        link_ok=_is_correct_vendor_link(root, entry, cache),
        cache_exists=cache.exists(),
    )


def _cache_head(cache: Path) -> str:
    result = git.run_git("rev-parse", "HEAD", cwd=cache)
    return result.stdout.strip()


def _cache_dirty(cache: Path) -> bool:
    result = git.run_git("status", "--porcelain", cwd=cache, check=False)
    return bool(result.stdout.strip())


def _remote_ref(entry: VendorEntry) -> str:
    return f"origin/{entry.source_ref}"


def _is_pin_sha(pin: str) -> bool:
    return bool(PIN_SHA_PATTERN.match(pin))


def _resolve_git_ref(cache: Path, ref: str, *, shallow: bool = False) -> str:
    result = git.run_git("rev-parse", "--verify", ref, cwd=cache, check=False)
    if result.returncode != 0:
        cause = None
        if shallow and _is_pin_sha(ref):
            cause = (
                "Shallow cache 可能不包含该 commit。"
                "请使用 vendor add --no-shallow，或移除 vendor 后重新添加。"
            )
        raise catalog_error(
            "VENDOR_PIN_NOT_FOUND",
            message=f"Pin ref not found in cache: {ref}",
            cause=cause,
            pin=ref,
            cache=str(cache),
        )
    return result.stdout.strip()


def _fetch_vendor_upstream(cache: Path, entry: VendorEntry) -> None:
    if entry.source_pin and not _is_pin_sha(entry.source_pin):
        git.run_git("fetch", "origin", "tag", entry.source_pin, cwd=cache, check=False)
    elif entry.source_pin and _is_pin_sha(entry.source_pin):
        pin = entry.source_pin
        fetched = git.run_git("fetch", "origin", pin, cwd=cache, check=False)
        if fetched.returncode != 0 and entry.shallow:
            git.run_git("fetch", "--unshallow", cwd=cache, check=False)
            git.run_git("fetch", "origin", pin, cwd=cache, check=False)
    fetch_result = git.run_git("fetch", "origin", cwd=cache, check=False)
    if fetch_result.returncode != 0:
        raise catalog_error(
            "GIT_COMMAND_FAILED",
            message=fetch_result.stderr.strip() or "git fetch failed",
        )


def _sync_target_ref(entry: VendorEntry) -> str:
    if entry.source_pin:
        return entry.source_pin
    return _remote_ref(entry)


def _move_cache_to_ref(
    cache: Path,
    target_ref: str,
    *,
    allow_detach: bool = False,
    shallow: bool = False,
) -> None:
    target_commit = _resolve_git_ref(cache, target_ref, shallow=shallow)
    head = _cache_head(cache)
    if head == target_commit:
        return
    merge = git.run_git("merge", "--ff-only", target_commit, cwd=cache, check=False)
    if merge.returncode == 0:
        return
    if not allow_detach:
        stderr = merge.stderr.strip() or merge.stdout.strip() or "merge --ff-only failed"
        raise catalog_error(
            "VENDOR_FF_BLOCKED",
            message=stderr,
            ref=target_ref,
            cache=str(cache),
        )
    checkout = git.run_git("checkout", "--detach", target_commit, cwd=cache, check=False)
    if checkout.returncode != 0:
        stderr = checkout.stderr.strip() or checkout.stdout.strip() or "checkout failed"
        raise catalog_error(
            "VENDOR_FF_BLOCKED",
            message=stderr,
            ref=target_ref,
            cache=str(cache),
        )


def _apply_pin_after_clone(cache: Path, entry: VendorEntry) -> None:
    if not entry.source_pin:
        return
    _fetch_vendor_upstream(cache, entry)
    _move_cache_to_ref(
        cache,
        entry.source_pin,
        allow_detach=True,
        shallow=entry.shallow and _is_pin_sha(entry.source_pin or ""),
    )


def vendor_updates_exit_code(results: list[VendorSyncResult]) -> int:
    if any(not r.ok for r in results):
        return 1
    if any(r.behind > 0 or r.pinned_drift for r in results):
        return 2
    return 0


def check_vendor_updates(root: Path, *, fetch: bool = True) -> list[VendorSyncResult]:
    results: list[VendorSyncResult] = []
    for entry in load_config(root).vendors:
        results.append(vendor_status(root, entry.name, fetch=fetch))
    return results


def vendor_status(root: Path, name_or_path: str, *, fetch: bool = True) -> VendorSyncResult:
    cfg = load_config(root)
    entry = _find_vendor(cfg, name_or_path)
    if entry is None:
        raise VendorError(f"Vendor not found: {name_or_path}")
    cache = _resolve_cache_path(entry)
    if not cache.exists():
        return VendorSyncResult(
            entry.name,
            ok=False,
            repo_path=entry.repo_path,
            source_pin=entry.source_pin,
            message="cache missing",
        )

    if fetch:
        try:
            _fetch_vendor_upstream(cache, entry)
        except GitMoveError as exc:
            return VendorSyncResult(
                entry.name,
                ok=False,
                repo_path=entry.repo_path,
                source_pin=entry.source_pin,
                message=exc.message,
                error_code=exc.code,
            )

    head = _cache_head(cache)
    dirty = _cache_dirty(cache)
    link_ok = _is_correct_vendor_link(root, entry, cache)
    behind = 0
    pinned_drift = False

    if entry.source_pin:
        try:
            pin_commit = _resolve_git_ref(
                cache,
                entry.source_pin,
                shallow=entry.shallow and _is_pin_sha(entry.source_pin),
            )
            pinned_drift = head != pin_commit
        except GitMoveError as exc:
            return VendorSyncResult(
                entry.name,
                ok=False,
                repo_path=entry.repo_path,
                source_pin=entry.source_pin,
                head_commit=head,
                dirty=dirty,
                link_ok=link_ok,
                message=exc.message,
                error_code=exc.code,
            )
    else:
        behind_result = git.run_git(
            "rev-list",
            "--count",
            f"HEAD..{_remote_ref(entry)}",
            cwd=cache,
            check=False,
        )
        if behind_result.returncode == 0 and behind_result.stdout.strip().isdigit():
            behind = int(behind_result.stdout.strip())

    parts = [f"commit={head[:7]}"]
    if entry.source_pin:
        parts.append(f"pin={entry.source_pin}")
        if pinned_drift:
            parts.append("pinned_drift")
    elif behind:
        parts.append(f"behind={behind}")
    if dirty:
        parts.append("dirty")
    if not link_ok:
        parts.append("link_broken")

    ok = link_ok and not dirty
    if entry.source_pin:
        try:
            _resolve_git_ref(
                cache,
                entry.source_pin,
                shallow=entry.shallow and _is_pin_sha(entry.source_pin),
            )
        except GitMoveError:
            ok = False

    return VendorSyncResult(
        entry.name,
        ok=ok,
        repo_path=entry.repo_path,
        behind=behind,
        dirty=dirty,
        pinned_drift=pinned_drift,
        source_pin=entry.source_pin,
        link_ok=link_ok,
        head_commit=head,
        message="; ".join(parts),
    )


def sync_vendor(root: Path, name_or_path: str, *, fetch: bool = True) -> VendorSyncResult:
    cfg = load_config(root)
    entry = _find_vendor(cfg, name_or_path)
    if entry is None:
        raise VendorError(f"Vendor not found: {name_or_path}")
    cache = _resolve_cache_path(entry)
    if not cache.exists():
        raise VendorError(f"Cache missing for vendor {entry.name}: {cache}")

    if _cache_dirty(cache):
        raise catalog_error("VENDOR_CACHE_DIRTY", message=f"Cache has uncommitted changes: {cache}", cache=str(cache))

    old_commit = _cache_head(cache)
    if fetch:
        _fetch_vendor_upstream(cache, entry)

    _move_cache_to_ref(
        cache,
        _sync_target_ref(entry),
        allow_detach=bool(entry.source_pin),
        shallow=bool(entry.source_pin and entry.shallow and _is_pin_sha(entry.source_pin)),
    )

    new_commit = _cache_head(cache)
    return VendorSyncResult(
        entry.name,
        ok=True,
        updated=old_commit != new_commit,
        old_commit=old_commit,
        new_commit=new_commit,
    )


def sync_all_vendors(root: Path, *, fetch: bool = True) -> list[VendorSyncResult]:
    results: list[VendorSyncResult] = []
    for entry in load_config(root).vendors:
        try:
            results.append(sync_vendor(root, entry.name, fetch=fetch))
        except (VendorError, GitMoveError) as exc:
            results.append(VendorSyncResult(entry.name, ok=False, message=str(exc)))
    return results


def remove_vendor(
    root: Path,
    name_or_path: str,
    *,
    purge_cache: bool = False,
    keep_skip: bool = True,
) -> None:
    cfg = load_config(root)
    entry = _find_vendor(cfg, name_or_path)
    if entry is None:
        raise VendorError(f"Vendor not found: {name_or_path}")

    link_path = root / entry.repo_path
    if link_path.exists() and link_mod._is_reparse_point(link_path):
        link_mod._remove_link_path(link_path)

    cache = _resolve_cache_path(entry)
    if purge_cache and cache.exists():
        _purge_cache_dir(cache)

    if not keep_skip and entry.auto_skip_tracked:
        tracked = git.ls_tracked_under_prefix(root, entry.repo_path)
        for path in tracked:
            if git.is_tracked(root, path):
                git.update_index_skip(root, path, skip=False)
        cfg = load_config(root)
        cfg.skip_paths = [p for p in cfg.skip_paths if p not in tracked]

    cfg.vendors = [vendor for vendor in cfg.vendors if vendor.name != entry.name]
    save_config(root, cfg)
    sync_link_excludes(root)


def check_vendors_for_doctor(root: Path, *, fetch_behind: bool = False) -> list[tuple[str, str, str]]:
    """Return (level, category, message) tuples for doctor."""
    issues: list[tuple[str, str, str]] = []
    cfg = load_config(root)
    skip_active, _ = git.ls_files_index(root)

    for entry in cfg.vendors:
        cache = _resolve_cache_path(entry)
        link_path = root / entry.repo_path
        if not cache.exists():
            issues.append(("error", "vendor", f"vendor cache 缺失: {entry.name} ({cache})"))
        if not link_path.exists():
            issues.append(("error", "vendor", f"vendor 链接缺失: {entry.repo_path}"))
        elif not _is_correct_vendor_link(root, entry, cache):
            issues.append(("error", "vendor", f"vendor 链接目标不是 cache: {entry.repo_path}"))

        if entry.auto_skip_tracked:
            for path in git.ls_tracked_under_prefix(root, entry.repo_path):
                if path not in skip_active:
                    issues.append(
                        ("error", "vendor", f"vendor 追踪路径未 skip: {path}")
                    )

        if fetch_behind and cache.exists():
            fetch_result = git.run_git("fetch", "origin", cwd=cache, check=False)
            if entry.source_pin and not _is_pin_sha(entry.source_pin):
                git.run_git("fetch", "origin", "tag", entry.source_pin, cwd=cache, check=False)
            if fetch_result.returncode == 0:
                if entry.source_pin:
                    try:
                        pin_commit = _resolve_git_ref(cache, entry.source_pin)
                        if _cache_head(cache) != pin_commit:
                            issues.append(
                                (
                                    "warn",
                                    "vendor",
                                    f"vendor {entry.name} pin drift: HEAD != {entry.source_pin}",
                                )
                            )
                    except GitMoveError:
                        issues.append(
                            (
                                "error",
                                "vendor",
                                f"vendor {entry.name} pin not found: {entry.source_pin}",
                            )
                        )
                else:
                    behind = git.run_git(
                        "rev-list",
                        "--count",
                        f"HEAD..{_remote_ref(entry)}",
                        cwd=cache,
                        check=False,
                    )
                    if behind.returncode == 0 and behind.stdout.strip().isdigit():
                        count = int(behind.stdout.strip())
                        if count > 0:
                            issues.append(
                                (
                                    "warn",
                                    "vendor",
                                    f"vendor {entry.name} 落后上游 {count} 个 commit",
                                )
                            )
    return issues
