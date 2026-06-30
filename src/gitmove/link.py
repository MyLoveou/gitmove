"""External directory links (junction / symlink) without .gitignore changes."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gitmove.config import LinkEntry, normalize_rel, resolve_external_base, resolve_repo_path
from gitmove.platform_util import resolve_link_type, subprocess_no_window_kwargs
from gitmove.skip import load_config, save_config


@dataclass
class LinkStatus:
    repo_path: str
    external_path: str
    link_type: str
    repo_exists: bool
    external_exists: bool
    is_link: bool
    link_ok: bool


def _is_reparse_point(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            attrs = path.lstat().st_file_attributes
            return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return False
    except OSError:
        return False


def _create_junction(link_path: Path, target: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        raise FileExistsError(f"Already exists: {link_path}")
    # mklink /J works for directories on Windows without admin (unlike symlinks).
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **subprocess_no_window_kwargs(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "mklink failed")


def _create_symlink(link_path: Path, target: Path, *, is_dir: bool) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        raise FileExistsError(f"Already exists: {link_path}")
    link_path.symlink_to(target, target_is_directory=is_dir)


def create_link(link_path: Path, target: Path, link_type: str | None = None) -> None:
    resolved_type = resolve_link_type(link_type)
    target.mkdir(parents=True, exist_ok=True)
    if resolved_type == "junction":
        if not target.is_dir():
            raise ValueError("junction requires a directory target")
        _create_junction(link_path, target)
    else:
        _create_symlink(link_path, target, is_dir=target.is_dir())


def add_link(
    root: Path,
    repo_rel: str,
    external: str | None = None,
    *,
    link_type: str | None = None,
    migrate: bool = False,
) -> LinkEntry:
    repo_path = normalize_rel(repo_rel)
    resolve_repo_path(root, repo_path)
    cfg = load_config(root)
    if any(vendor.repo_path == repo_path for vendor in cfg.vendors):
        raise FileExistsError(f"repo_path is managed by vendor: {repo_path}")
    resolved_type = resolve_link_type(link_type)
    base = resolve_external_base(cfg, root)

    if external:
        external_path = str(Path(external).expanduser().resolve())
    else:
        external_path = str((base / repo_path).resolve())

    link_path = root / repo_path
    target = Path(external_path)

    if link_path.exists() and not _is_reparse_point(link_path):
        if migrate:
            if target.exists() and any(target.iterdir()):
                raise FileExistsError(f"External target not empty: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if link_path.is_dir():
                shutil.copytree(link_path, target, dirs_exist_ok=False)
                shutil.rmtree(link_path)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(link_path), str(target / link_path.name))
                link_path = root / repo_path
        else:
            raise FileExistsError(
                f"{repo_path} exists and is not a link. Use --migrate to move content externally."
            )

    if not link_path.exists():
        use_dir_target = target.is_dir() or resolved_type == "junction"
        create_link(
            link_path,
            target if use_dir_target else target.parent,
            resolved_type,
        )

    entry = LinkEntry(repo_path=repo_path, external_path=external_path, link_type=resolved_type)
    cfg.links = [l for l in cfg.links if l.repo_path != repo_path]
    cfg.links.append(entry)
    save_config(root, cfg)
    return entry


def apply_links(root: Path) -> list[LinkStatus]:
    cfg = load_config(root)
    results: list[LinkStatus] = []
    for entry in cfg.links:
        results.append(_status_for_entry(root, entry))
        link_path = root / entry.repo_path
        target = Path(entry.external_path)
        if link_path.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        create_link(link_path, target, entry.link_type)
        results[-1] = _status_for_entry(root, entry)
    return results


def list_links(root: Path) -> list[LinkStatus]:
    cfg = load_config(root)
    return [_status_for_entry(root, entry) for entry in cfg.links]


def _remove_link_path(link_path: Path) -> None:
    """Remove a junction/symlink without deleting the external target."""
    if not link_path.exists():
        return
    if not _is_reparse_point(link_path):
        raise FileExistsError(f"Path is not a link: {link_path}")
    if os.name == "nt" and not link_path.is_symlink():
        subprocess.run(
            ["cmd", "/c", "rmdir", str(link_path)],
            check=True,
            **subprocess_no_window_kwargs(),
        )
    else:
        link_path.unlink()


def remove_link(root: Path, repo_rel: str, *, keep_external: bool = True) -> None:
    repo_path = normalize_rel(repo_rel)
    resolve_repo_path(root, repo_path)
    cfg = load_config(root)
    if any(vendor.repo_path == repo_path for vendor in cfg.vendors):
        raise FileExistsError(f"repo_path is managed by vendor: {repo_path}")
    entry = next((l for l in cfg.links if l.repo_path == repo_path), None)
    if not entry:
        raise KeyError(f"Link not in config: {repo_path}")

    link_path = root / repo_path
    if link_path.exists() and _is_reparse_point(link_path):
        _remove_link_path(link_path)

    if not keep_external:
        target = Path(entry.external_path)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    cfg.links = [l for l in cfg.links if l.repo_path != repo_path]
    save_config(root, cfg)


def _status_for_entry(root: Path, entry: LinkEntry) -> LinkStatus:
    link_path = root / entry.repo_path
    target = Path(entry.external_path)
    is_link = _is_reparse_point(link_path) if link_path.exists() else False
    link_ok = False
    if is_link:
        try:
            link_ok = link_path.resolve() == target.resolve()
        except OSError:
            link_ok = False
    return LinkStatus(
        repo_path=entry.repo_path,
        external_path=entry.external_path,
        link_type=entry.link_type,
        repo_exists=link_path.exists(),
        external_exists=target.exists(),
        is_link=is_link,
        link_ok=link_ok,
    )


def set_external_base(root: Path, base_path: str) -> Path:
    cfg = load_config(root)
    cfg.external_base = base_path
    save_config(root, cfg)
    return resolve_external_base(cfg, root)
