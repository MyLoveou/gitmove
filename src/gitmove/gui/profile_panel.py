"""Profile tab row formatting."""

from __future__ import annotations

from pathlib import Path

from gitmove import profile as profile_mod


def profile_list_rows(root: Path) -> list[tuple[str, str]]:
    """Return rows of (name, status) where status is 当前/—."""
    active = profile_mod.active_profile_name(root)
    return [(name, "当前" if name == active else "—") for name in profile_mod.list_profiles(root)]
