#!/usr/bin/env python3
"""Build Windows setup.exe via Inno Setup (after PyInstaller)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARTIFACTS = ROOT / "artifacts"
ISS = ROOT / "scripts" / "installer" / "gitmove.iss"


def _version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from gitmove import __version__

    return __version__


def _find_iscc() -> Path | None:
    env = os.environ.get("ISCC")
    if env:
        path = Path(env)
        if path.is_file():
            return path

    found = shutil.which("ISCC")
    if found:
        return Path(found)

    for candidate in (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _ensure_executables(*, rebuild: bool) -> None:
    cli = DIST / "gitmove.exe"
    gui = DIST / "gitmove-gui.exe"
    if not rebuild and cli.is_file() and gui.is_file():
        return

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "build.py"),
        "--target",
        "all",
        "--onefile",
        "--no-archive",
    ]
    print(">>> Building PyInstaller executables…")
    subprocess.run(cmd, cwd=ROOT, check=True)

    if not cli.is_file() or not gui.is_file():
        raise FileNotFoundError(f"Expected {cli} and {gui} after PyInstaller build")


def build_installer(*, version: str | None = None, rebuild: bool = False) -> Path:
    if sys.platform != "win32":
        raise RuntimeError("Windows installer requires Windows and Inno Setup 6")

    version = version or _version()
    iscc = _find_iscc()
    if iscc is None:
        raise RuntimeError(
            "Inno Setup compiler (ISCC.exe) not found. "
            "Install from https://jrsoftware.org/isinfo.php "
            "or set ISCC to the full path of ISCC.exe"
        )

    _ensure_executables(rebuild=rebuild)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(iscc),
        f"/DMyAppVersion={version}",
        str(ISS),
    ]
    print(f">>> Compiling installer with {iscc}")
    subprocess.run(cmd, cwd=ROOT, check=True)

    setup = ARTIFACTS / f"gitmove-{version}-windows-x64-setup.exe"
    if not setup.is_file():
        matches = sorted(ARTIFACTS.glob(f"gitmove-{version}-windows-x64-setup*.exe"))
        if not matches:
            raise FileNotFoundError(f"Installer not found under {ARTIFACTS}")
        setup = matches[-1]

    size_kb = setup.stat().st_size // 1024
    print(f"\n>>> Installer: {setup} ({size_kb} KB)")
    return setup


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gitmove Windows setup.exe")
    parser.add_argument("--version", help="Override version label (default: package __version__)")
    parser.add_argument("--rebuild", action="store_true", help="Force PyInstaller rebuild before packaging")
    args = parser.parse_args()
    build_installer(version=args.version, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
