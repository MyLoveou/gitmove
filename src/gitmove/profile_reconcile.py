"""Reconcile disk resources when switching gitmove profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitmove.config import GitMoveConfig, LinkEntry, VendorEntry, config_path_for_repo
from gitmove.exclude import sync_link_excludes
from gitmove import git
from gitmove import link as link_mod
from gitmove import vendor as vendor_mod


@dataclass(frozen=True)
class ProfileResourceDiff:
    removed_vendors: tuple[VendorEntry, ...]
    added_vendors: tuple[VendorEntry, ...]
    removed_links: tuple[LinkEntry, ...]
    added_links: tuple[LinkEntry, ...]
    removed_skip_paths: frozenset[str]
    added_skip_paths: frozenset[str]


def compute_profile_diff(old: GitMoveConfig, new: GitMoveConfig) -> ProfileResourceDiff:
    old_vendor_names = {vendor.name: vendor for vendor in old.vendors}
    new_vendor_names = {vendor.name: vendor for vendor in new.vendors}
    removed_vendors = tuple(
        sorted(
            (old_vendor_names[name] for name in old_vendor_names if name not in new_vendor_names),
            key=lambda item: item.name,
        )
    )
    added_vendors = tuple(
        sorted(
            (new_vendor_names[name] for name in new_vendor_names if name not in old_vendor_names),
            key=lambda item: item.name,
        )
    )

    old_link_paths = {link.repo_path: link for link in old.links}
    new_link_paths = {link.repo_path: link for link in new.links}
    removed_links = tuple(
        sorted(
            (old_link_paths[path] for path in old_link_paths if path not in new_link_paths),
            key=lambda item: item.repo_path,
        )
    )
    added_links = tuple(
        sorted(
            (new_link_paths[path] for path in new_link_paths if path not in old_link_paths),
            key=lambda item: item.repo_path,
        )
    )

    old_skip = set(old.skip_paths)
    new_skip = set(new.skip_paths)
    return ProfileResourceDiff(
        removed_vendors=removed_vendors,
        added_vendors=added_vendors,
        removed_links=removed_links,
        added_links=added_links,
        removed_skip_paths=frozenset(old_skip - new_skip),
        added_skip_paths=frozenset(new_skip - old_skip),
    )


def teardown_vendor_mount(root: Path, entry: VendorEntry, *, restore_tracked: bool = True) -> None:
    link_path = root / entry.repo_path
    tracked = git.ls_tracked_under_prefix(root, entry.repo_path)
    if restore_tracked:
        for path in tracked:
            git.update_index_skip(root, path, skip=False)
    if link_path.exists() and link_mod._is_reparse_point(link_path):
        link_mod._remove_link_path(link_path)
    if not restore_tracked or not tracked:
        return
    git.run_git(
        "restore",
        "--source=HEAD",
        "--worktree",
        "--staged",
        entry.repo_path,
        cwd=root,
        check=False,
    )


def teardown_link_mount(root: Path, entry: LinkEntry) -> None:
    link_path = root / entry.repo_path
    if link_path.exists() and link_mod._is_reparse_point(link_path):
        link_mod._remove_link_path(link_path)


def sync_skip_paths(root: Path, old: GitMoveConfig, new: GitMoveConfig) -> None:
    diff = compute_profile_diff(old, new)
    for path in sorted(diff.removed_skip_paths):
        if git.is_tracked(root, path):
            git.update_index_skip(root, path, skip=False)
    for path in new.skip_paths:
        full = root / path
        if full.exists() and git.is_tracked(root, path):
            git.update_index_skip(root, path, skip=True)


def apply_profile_transition(root: Path, old: GitMoveConfig, new: GitMoveConfig) -> None:
    """Teardown removed resources, persist new config, mount added resources, apply."""
    diff = compute_profile_diff(old, new)

    for entry in diff.removed_vendors:
        teardown_vendor_mount(root, entry)
    for entry in diff.removed_links:
        teardown_link_mount(root, entry)

    config_path = config_path_for_repo(root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    new.save(config_path)

    for entry in diff.added_vendors:
        vendor_mod.ensure_vendor_mount(root, entry)

    sync_skip_paths(root, old, new)

    from gitmove.doctor import apply_all

    apply_all(root)
    sync_link_excludes(root)
