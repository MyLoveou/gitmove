"""Named configuration profiles stored under .git/gitmove.profiles/."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from gitmove.config import CONFIG_FILENAME, config_path_for_repo
from gitmove.doctor import apply_all, run_doctor
from gitmove.errors import catalog_error

PROFILE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
PROFILES_DIRNAME = "gitmove.profiles"
ACTIVE_FILENAME = "gitmove.active"


def _profiles_dir(root: Path) -> Path:
    return root / ".git" / PROFILES_DIRNAME


def _active_path(root: Path) -> Path:
    return root / ".git" / ACTIVE_FILENAME


def _validate_profile_name(name: str) -> None:
    if not PROFILE_NAME_PATTERN.match(name):
        raise catalog_error(
            "PROFILE_INVALID_NAME",
            message=f"Invalid profile name: {name!r}",
            name=name,
        )


def _profile_path(root: Path, name: str) -> Path:
    _validate_profile_name(name)
    return _profiles_dir(root) / f"{name}.toml"


def list_profiles(root: Path) -> list[str]:
    directory = _profiles_dir(root)
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.toml"))


def active_profile_name(root: Path) -> str | None:
    active = _active_path(root)
    if not active.exists():
        return None
    name = active.read_text(encoding="utf-8").strip()
    return name or None


def save_profile(root: Path, name: str) -> None:
    config = config_path_for_repo(root)
    if not config.exists():
        raise catalog_error(
            "CONFIG_NOT_FOUND",
            message=f"No active configuration to save: {config}",
            path=str(config),
        )
    target = _profile_path(root, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config, target)


def use_profile(root: Path, name: str, *, dry_run: bool = False) -> None:
    source = _profile_path(root, name)
    if not source.exists():
        raise catalog_error(
            "PROFILE_NOT_FOUND",
            message=f"Profile not found: {name}",
            name=name,
        )
    if dry_run:
        config = config_path_for_repo(root)
        backup = config.read_bytes() if config.exists() else None
        active_backup = None
        active = _active_path(root)
        if active.exists():
            active_backup = active.read_bytes()
        try:
            shutil.copy2(source, config)
            report = run_doctor(root)
            if not report.ok:
                raise catalog_error(
                    "PROFILE_DRY_RUN_FAILED",
                    message=f"Profile {name!r} would fail doctor checks",
                    name=name,
                )
        finally:
            if backup is not None:
                config.write_bytes(backup)
            elif config.exists():
                config.unlink()
            if active_backup is not None:
                active.write_bytes(active_backup)
            elif active.exists() and active_backup is None:
                active.unlink(missing_ok=True)
        return
    config = config_path_for_repo(root)
    config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, config)
    active = _active_path(root)
    active.write_text(f"{name}\n", encoding="utf-8")
    apply_all(root)


def delete_profile(root: Path, name: str) -> None:
    target = _profile_path(root, name)
    if not target.exists():
        raise catalog_error(
            "PROFILE_NOT_FOUND",
            message=f"Profile not found: {name}",
            name=name,
        )
    target.unlink()
    active = active_profile_name(root)
    if active == name:
        _active_path(root).unlink(missing_ok=True)
