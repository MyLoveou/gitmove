"""Sync linked and vendor paths into `.git/info/exclude` managed section."""

from __future__ import annotations

from pathlib import Path

from gitmove.config import normalize_rel
from gitmove.skip import load_config

MANAGED_MARKER_START = "# gitmove: link excludes (managed — do not edit below)"
MANAGED_MARKER_END = "# gitmove: end link excludes"

_ESCAPE_CHARS = "#*?[]\\"


def to_exclude_pattern(repo_path: str) -> str:
    """Convert a repo-relative path to a gitignore pattern."""
    normalized = normalize_rel(repo_path)
    if "/" not in normalized:
        prefix = "/"
    else:
        prefix = ""
    escaped = "".join(f"\\{ch}" if ch in _ESCAPE_CHARS else ch for ch in normalized)
    return f"{prefix}{escaped}"


def _exclude_file(root: Path) -> Path:
    return root / ".git" / "info" / "exclude"


def _split_managed(content: str) -> tuple[str, str | None]:
    start = content.find(MANAGED_MARKER_START)
    if start == -1:
        return content.rstrip("\n"), None
    user_part = content[:start].rstrip("\n")
    end = content.find(MANAGED_MARKER_END, start)
    if end == -1:
        return user_part, content[start:].rstrip("\n")
    return user_part, content[start : end + len(MANAGED_MARKER_END)].rstrip("\n")


def _collect_patterns(root: Path) -> list[str]:
    cfg = load_config(root)
    paths = {link.repo_path for link in cfg.links}
    paths.update(vendor.repo_path for vendor in cfg.vendors)
    return sorted(to_exclude_pattern(p) for p in paths)


def _build_managed_section(patterns: list[str]) -> str:
    lines = [MANAGED_MARKER_START, *patterns, MANAGED_MARKER_END]
    return "\n".join(lines)


def _remove_managed_section(root: Path) -> None:
    path = _exclude_file(root)
    if not path.exists():
        return
    user_part, _ = _split_managed(path.read_text(encoding="utf-8"))
    if user_part:
        path.write_text(user_part + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)


def sync_link_excludes(root: Path) -> None:
    """Rewrite the managed exclude section from current link/vendor config."""
    cfg = load_config(root)
    path = _exclude_file(root)
    if not cfg.exclude_linked_paths:
        _remove_managed_section(root)
        return

    patterns = _collect_patterns(root)
    user_part = ""
    if path.exists():
        user_part, _ = _split_managed(path.read_text(encoding="utf-8"))

    parts: list[str] = []
    if user_part:
        parts.append(user_part)
    if patterns:
        parts.append(_build_managed_section(patterns))
    elif path.exists():
        # No patterns: drop managed section, keep user content.
        if user_part:
            path.write_text(user_part + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
