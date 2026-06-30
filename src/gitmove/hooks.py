"""Optional Git hooks integration for automatic gitmove apply."""

from __future__ import annotations

import shlex
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from gitmove.errors import catalog_error

HOOK_MARKER = "# gitmove-managed"
VALID_RUN_CMDS = frozenset({"apply", "doctor", "sync-check"})


@dataclass
class HooksStatus:
    post_merge_installed: bool = False
    post_checkout_installed: bool = False
    post_merge_run: str | None = None
    post_checkout_run: str | None = None


def _hooks_dir(root: Path) -> Path:
    return root / ".git" / "hooks"


def _render_hook(root: Path, run_cmd: str) -> str:
    repo = shlex.quote(str(root.resolve()))
    exe = shlex.quote(str(Path(sys.executable).resolve()))
    if run_cmd == "apply":
        cmd = f"{exe} -m gitmove.cli apply -C {repo}"
    elif run_cmd == "doctor":
        cmd = f"{exe} -m gitmove.cli doctor -C {repo}"
    else:
        cmd = f"{exe} -m gitmove.cli sync check -C {repo}"
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER}\n"
        f"# run={run_cmd}\n"
        f"{cmd} >/dev/null 2>&1 || true\n"
    )


def _parse_hook_run(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# run="):
            return line.split("=", 1)[1].strip()
    return None


def _is_gitmove_hook(path: Path) -> bool:
    if not path.exists():
        return False
    return HOOK_MARKER in path.read_text(encoding="utf-8")


def _write_executable_hook(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_hooks(
    root: Path,
    *,
    post_merge: bool = True,
    post_checkout: bool = False,
    run_cmd: str = "apply",
) -> None:
    if run_cmd not in VALID_RUN_CMDS:
        raise ValueError(f"Invalid run command: {run_cmd}")
    hooks = _hooks_dir(root)
    specs: list[tuple[str, bool]] = [
        ("post-merge", post_merge),
        ("post-checkout", post_checkout),
    ]
    for hook_name, enabled in specs:
        if not enabled:
            continue
        hook_path = hooks / hook_name
        content = _render_hook(root, run_cmd)
        if hook_path.exists() and not _is_gitmove_hook(hook_path):
            raise catalog_error(
                "HOOK_EXISTS",
                message=f"Hook already exists and is not gitmove-managed: {hook_path}",
                hook=str(hook_path),
            )
        if hook_path.exists() and _is_gitmove_hook(hook_path):
            existing = hook_path.read_text(encoding="utf-8")
            if existing == content:
                continue
        _write_executable_hook(hook_path, content)


def uninstall_hooks(root: Path) -> None:
    hooks = _hooks_dir(root)
    for hook_name in ("post-merge", "post-checkout"):
        hook_path = hooks / hook_name
        if _is_gitmove_hook(hook_path):
            hook_path.unlink(missing_ok=True)


def hooks_status(root: Path) -> HooksStatus:
    hooks = _hooks_dir(root)
    status = HooksStatus()
    post_merge = hooks / "post-merge"
    if _is_gitmove_hook(post_merge):
        status.post_merge_installed = True
        status.post_merge_run = _parse_hook_run(post_merge.read_text(encoding="utf-8"))
    post_checkout = hooks / "post-checkout"
    if _is_gitmove_hook(post_checkout):
        status.post_checkout_installed = True
        status.post_checkout_run = _parse_hook_run(
            post_checkout.read_text(encoding="utf-8")
        )
    return status
