"""Import and export gitmove.toml configuration."""

from __future__ import annotations

from pathlib import Path

from gitmove.config import GitMoveConfig, LinkEntry, VendorEntry, WorktreeEntry, config_path_for_repo, resolve_repo_path

EXTERNAL_BASE_VAR = "${EXTERNAL_BASE}"


def export_config(cfg: GitMoveConfig, path: Path) -> None:
    """Write configuration to a portable TOML file."""
    cfg.save(path)


def merge_configs(target: GitMoveConfig, incoming: GitMoveConfig) -> GitMoveConfig:
    """Merge incoming into target; existing link/worktree entries win on conflict."""
    skip_paths = sorted(set(target.skip_paths) | set(incoming.skip_paths))

    external_base = target.external_base or incoming.external_base
    exclude_linked_paths = target.exclude_linked_paths

    links_by_path = {link.repo_path: link for link in target.links}
    for link in incoming.links:
        links_by_path.setdefault(link.repo_path, link)
    links = sorted(links_by_path.values(), key=lambda item: item.repo_path)

    worktrees_by_name = {wt.name: wt for wt in target.worktrees}
    for wt in incoming.worktrees:
        worktrees_by_name.setdefault(wt.name, wt)
    worktrees = sorted(worktrees_by_name.values(), key=lambda item: item.name)

    vendors_by_name = {vendor.name: vendor for vendor in target.vendors}
    vendor_paths = {vendor.repo_path for vendor in target.vendors}
    for vendor in incoming.vendors:
        vendors_by_name.setdefault(vendor.name, vendor)
        vendor_paths.add(vendor.repo_path)
    vendors = sorted(vendors_by_name.values(), key=lambda item: item.name)
    links = [link for link in links if link.repo_path not in vendor_paths]

    return GitMoveConfig(
        skip_paths=skip_paths,
        external_base=external_base,
        exclude_linked_paths=exclude_linked_paths,
        links=links,
        worktrees=worktrees,
        vendors=vendors,
    )


def _apply_path_substitutions(
    cfg: GitMoveConfig,
    *,
    base_override: str | None,
    repo_root: Path,
) -> GitMoveConfig:
    if not base_override:
        return cfg

    base = Path(base_override).expanduser()
    if not base.is_absolute():
        base = (repo_root / base).resolve()
    else:
        base = base.resolve()

    base_text = str(base)
    external_base = base_text

    links: list[LinkEntry] = []
    for link in cfg.links:
        external_path = link.external_path.replace(EXTERNAL_BASE_VAR, base_text)
        external_path = str(Path(external_path).expanduser().resolve())
        links.append(
            LinkEntry(
                repo_path=link.repo_path,
                external_path=external_path,
                link_type=link.link_type,
                kind=link.kind,
                migrate_skipped=list(link.migrate_skipped),
            )
        )

    worktrees: list[WorktreeEntry] = []
    for wt in cfg.worktrees:
        path = wt.path.replace(EXTERNAL_BASE_VAR, base_text)
        path = str(Path(path).expanduser().resolve())
        worktrees.append(WorktreeEntry(name=wt.name, path=path, branch=wt.branch))

    return GitMoveConfig(
        skip_paths=list(cfg.skip_paths),
        external_base=external_base,
        exclude_linked_paths=cfg.exclude_linked_paths,
        links=links,
        worktrees=worktrees,
        vendors=list(cfg.vendors),
    )


def _validate_config(root: Path, cfg: GitMoveConfig) -> None:
    for path in cfg.skip_paths:
        resolve_repo_path(root, path)
    for link in cfg.links:
        resolve_repo_path(root, link.repo_path)


def _prepare_incoming(
    root: Path,
    incoming: GitMoveConfig,
    *,
    base_override: str | None,
) -> GitMoveConfig:
    prepared = _apply_path_substitutions(incoming, base_override=base_override, repo_root=root)
    _validate_config(root, prepared)
    return prepared


def import_config(
    root: Path,
    source: Path,
    *,
    merge: bool = True,
    base_override: str | None = None,
    persist: bool = True,
) -> GitMoveConfig:
    """Import configuration from a TOML file into the repository."""
    if not source.is_file():
        raise FileNotFoundError(f"Config file not found: {source}")

    incoming = _prepare_incoming(root, GitMoveConfig.load(source), base_override=base_override)
    dest_path = config_path_for_repo(root)

    if merge and dest_path.exists():
        target = GitMoveConfig.load(dest_path)
        result = merge_configs(target, incoming)
    else:
        result = incoming

    if persist:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(dest_path)
    return result


def import_config_from_repo(
    root: Path,
    other_repo: Path,
    *,
    merge: bool = True,
    base_override: str | None = None,
    persist: bool = True,
) -> GitMoveConfig:
    """Import configuration from another clone's .git/gitmove.toml."""
    source = other_repo.resolve() / ".git" / "gitmove.toml"
    if not source.is_file():
        raise FileNotFoundError(f"gitmove.toml not found in repository: {other_repo}")
    return import_config(
        root,
        source,
        merge=merge,
        base_override=base_override,
        persist=persist,
    )
