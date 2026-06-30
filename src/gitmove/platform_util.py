"""Cross-platform helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def platform_label() -> str:
    if sys.platform == "win32":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return "Linux"


def default_link_type() -> str:
    """Windows prefers junction (no admin); macOS/Linux use symlink."""
    return "junction" if os.name == "nt" else "symlink"


def subprocess_no_window_kwargs() -> dict[str, int]:
    """Hide console windows for child processes on Windows (GUI / frozen exe)."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def open_path_in_file_manager(path: str | Path) -> None:
    """Open a file or directory in the system file manager."""
    target = Path(path)
    if sys.platform == "win32":
        os.startfile(target)  # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=False)
        return
    subprocess.run(["xdg-open", str(target)], check=False)


def resolve_link_type(link_type: str | None = None) -> str:
    if link_type:
        normalized = link_type.lower()
        if normalized not in {"junction", "symlink"}:
            raise ValueError(f"Unknown link type: {link_type}")
        if normalized == "junction" and os.name != "nt":
            return "symlink"
        return normalized
    return default_link_type()
