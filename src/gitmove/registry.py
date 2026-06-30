"""User-level project registry (~/.gitmove/projects.toml)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import tomllib
import tomli_w

REGISTRY_FILENAME = "projects.toml"
ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class RegistryError(ValueError):
    """Invalid registry operation."""


@dataclass
class ProjectEntry:
    path: Path
    alias: str
    group: str | None = None
    notes: str = ""
    last_used: str | None = None


@dataclass
class ProjectsRegistry:
    default_project: str | None = None
    projects: list[ProjectEntry] = field(default_factory=list)


def config_dir() -> Path:
    home_override = os.environ.get("GITMOVE_HOME")
    if home_override:
        return Path(home_override).expanduser().resolve()
    return Path.home() / ".gitmove"


def registry_path() -> Path:
    return config_dir() / REGISTRY_FILENAME


def validate_alias(alias: str) -> None:
    if not ALIAS_PATTERN.match(alias):
        raise RegistryError(
            f"Invalid alias {alias!r}: use 1-64 characters [a-zA-Z0-9_-] only"
        )


def load_registry(path: Path | None = None) -> ProjectsRegistry:
    target = path or registry_path()
    if not target.exists():
        return ProjectsRegistry()

    data = tomllib.loads(target.read_text(encoding="utf-8"))
    reg = ProjectsRegistry()
    settings = data.get("settings", {})
    if isinstance(settings.get("default_project"), str):
        reg.default_project = settings["default_project"]

    for item in data.get("projects", []):
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        raw_alias = item.get("alias")
        if not isinstance(raw_path, str) or not isinstance(raw_alias, str):
            continue
        reg.projects.append(
            ProjectEntry(
                path=Path(raw_path).expanduser().resolve(),
                alias=raw_alias,
                group=item.get("group") if isinstance(item.get("group"), str) else None,
                notes=item.get("notes", "") if isinstance(item.get("notes"), str) else "",
                last_used=item.get("last_used")
                if isinstance(item.get("last_used"), str)
                else None,
            )
        )
    return reg


def save_registry(reg: ProjectsRegistry, path: Path | None = None) -> None:
    target = path or registry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "settings": {"default_project": reg.default_project or ""},
        "projects": [
            {
                "path": str(entry.path).replace("\\", "/"),
                "alias": entry.alias,
                "group": entry.group or "",
                "notes": entry.notes,
                "last_used": entry.last_used or "",
            }
            for entry in reg.projects
        ],
    }
    target.write_text(tomli_w.dumps(payload), encoding="utf-8")


def _find_by_alias(reg: ProjectsRegistry, alias: str) -> ProjectEntry | None:
    for entry in reg.projects:
        if entry.alias == alias:
            return entry
    return None


def _find_by_path(reg: ProjectsRegistry, path: Path) -> ProjectEntry | None:
    resolved = path.expanduser().resolve()
    for entry in reg.projects:
        if entry.path == resolved:
            return entry
    return None


def resolve_alias(alias: str, reg: ProjectsRegistry | None = None) -> Path:
    registry = reg if reg is not None else load_registry()
    entry = _find_by_alias(registry, alias)
    if entry is None:
        raise RegistryError(f"Unknown project alias: {alias}")
    return entry.path


def add_project(
    path: str | Path,
    *,
    alias: str | None = None,
    group: str | None = None,
    notes: str = "",
    reg: ProjectsRegistry | None = None,
    save_path: Path | None = None,
) -> ProjectEntry:
    registry = reg if reg is not None else load_registry()
    resolved = Path(path).expanduser().resolve()
    entry_alias = alias or resolved.name
    validate_alias(entry_alias)

    if _find_by_alias(registry, entry_alias):
        raise RegistryError(f"Alias already registered: {entry_alias}")
    if _find_by_path(registry, resolved):
        raise RegistryError(f"Path already registered: {resolved}")

    entry = ProjectEntry(path=resolved, alias=entry_alias, group=group, notes=notes)
    registry.projects.append(entry)
    save_registry(registry, save_path)
    return entry


def remove_project(
    alias_or_path: str,
    *,
    reg: ProjectsRegistry | None = None,
    save_path: Path | None = None,
) -> None:
    registry = reg if reg is not None else load_registry()
    entry = _find_by_alias(registry, alias_or_path)
    if entry is None:
        candidate = Path(alias_or_path).expanduser().resolve()
        entry = _find_by_path(registry, candidate)
    if entry is None:
        raise RegistryError(f"Project not found: {alias_or_path}")

    registry.projects = [item for item in registry.projects if item.alias != entry.alias]
    if registry.default_project == entry.alias:
        registry.default_project = None
    save_registry(registry, save_path)


def set_default(alias: str, *, reg: ProjectsRegistry | None = None, save_path: Path | None = None) -> None:
    registry = reg if reg is not None else load_registry()
    if _find_by_alias(registry, alias) is None:
        raise RegistryError(f"Unknown project alias: {alias}")
    registry.default_project = alias
    save_registry(registry, save_path)


def touch_last_used(alias: str, *, reg: ProjectsRegistry | None = None, save_path: Path | None = None) -> None:
    registry = reg if reg is not None else load_registry()
    entry = _find_by_alias(registry, alias)
    if entry is None:
        raise RegistryError(f"Unknown project alias: {alias}")
    entry.last_used = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    save_registry(registry, save_path)


def list_projects(*, group: str | None = None, reg: ProjectsRegistry | None = None) -> list[ProjectEntry]:
    registry = reg if reg is not None else load_registry()
    entries = list(registry.projects)
    if group is not None:
        entries = [item for item in entries if item.group == group]
    return entries
