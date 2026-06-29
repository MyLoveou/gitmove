#!/usr/bin/env python3
"""Cross-platform PyInstaller build for gitmove CLI and GUI."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ARTIFACTS = ROOT / "artifacts"

# Keep frozen bundles lean — avoid pulling optional heavy deps from dev environments.
EXCLUDES = [
    "IPython",
    "ipykernel",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "notebook",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "torch",
    "tensorflow",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "sphinx",
    "docutils",
    "jedi",
    "parso",
    "zmq",
    "black",
    "pytest",
    "setuptools",
    "pkg_resources",
]

CLI_HIDDEN = [
    "gitmove",
    "gitmove.cli",
    "gitmove.doctor",
    "gitmove.skip",
    "gitmove.link",
    "gitmove.worktree",
    "gitmove.config",
    "gitmove.git",
    "gitmove.platform_util",
    "typer",
    "typer.core",
    "click",
    "shellingham",
    "rich",
    "rich.console",
    "rich.table",
    "rich.markup",
    "rich.text",
    "rich.style",
    "rich.color",
    "rich.segment",
    "rich.padding",
    "rich.box",
    "rich._cell_widths",
    "rich._export_format",
    "rich._extension",
    "rich._loop",
    "rich._null_file",
    "rich._pick",
    "rich._ratio",
    "rich._spinners",
    "rich._stack",
    "rich._timer",
    "rich._win32_console",
    "rich._windows",
    "rich._wrap",
    "rich.abc",
    "rich.align",
    "rich.bar",
    "rich.cells",
    "rich.columns",
    "rich.constrain",
    "rich.containers",
    "rich.control",
    "rich.default_styles",
    "rich.emoji",
    "rich.errors",
    "rich.file_proxy",
    "rich.filesize",
    "rich.highlighter",
    "rich.jupyter",
    "rich.layout",
    "rich.live",
    "rich.live_render",
    "rich.logging",
    "rich.measure",
    "rich.panel",
    "rich.pretty",
    "rich.progress",
    "rich.progress_bar",
    "rich.prompt",
    "rich.protocol",
    "rich.region",
    "rich.repr",
    "rich.rule",
    "rich.scope",
    "rich.screen",
    "rich.spinner",
    "rich.status",
    "rich.syntax",
    "rich.theme",
    "rich.traceback",
    "rich.tree",
    "pygments",
    "pygments.lexers",
    "pygments.formatters",
    "pygments.styles",
    "markdown_it",
    "mdurl",
]

GUI_HIDDEN = CLI_HIDDEN + [
    "gitmove.gui.app",
    "customtkinter",
    "PIL",
    "PIL._tkinter_finder",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
]


def _version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from gitmove import __version__

    return __version__


def _platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        arch = "x64"
    elif machine in {"arm64", "aarch64"}:
        arch = "arm64"
    else:
        arch = machine
    return f"{system}-{arch}"


def _sep() -> str:
    return ";" if sys.platform == "win32" else ":"


def _collect_customtkinter() -> tuple[list[tuple[str, str]], list[tuple[str, str, str]], list[str]]:
    from PyInstaller.utils.hooks import collect_all

    return collect_all("customtkinter")


def _build(name: str, entry: Path, *, windowed: bool, onefile: bool, gui: bool) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / name),
        "--specpath",
        str(BUILD / "spec"),
        "--paths",
        str(ROOT / "src"),
    ]

    cmd.append("--windowed" if windowed else "--console")
    cmd.append("--onefile" if onefile else "--onedir")

    for mod in EXCLUDES:
        cmd.extend(["--exclude-module", mod])

    if not gui:
        for mod in ("customtkinter", "tkinter", "PIL", "darkdetect"):
            cmd.extend(["--exclude-module", mod])

    hidden = GUI_HIDDEN if gui else CLI_HIDDEN
    for mod in hidden:
        cmd.extend(["--hidden-import", mod])

    if gui:
        datas, binaries, extra_hidden = _collect_customtkinter()
        for src, dest in datas:
            cmd.extend(["--add-data", f"{src}{_sep()}{dest}"])
        for src, dest, _typ in binaries:
            cmd.extend(["--add-binary", f"{src}{_sep()}{dest}"])
        for mod in extra_hidden:
            cmd.extend(["--hidden-import", mod])

    cmd.append(str(entry))
    print(f"\n>>> Building {name} ({'gui' if gui else 'cli'}, {'onefile' if onefile else 'onedir'})")
    subprocess.run(cmd, cwd=ROOT, check=True)

    if onefile:
        ext = ".exe" if sys.platform == "win32" else ""
        return DIST / f"{name}{ext}"
    return DIST / name


def _archive(version: str, targets: list[Path]) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    tag = f"gitmove-{version}-{_platform_tag()}"

    if sys.platform == "win32":
        archive_path = ARTIFACTS / f"{tag}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for target in targets:
                if target.is_file():
                    zf.write(target, arcname=target.name)
                elif target.is_dir():
                    for file in target.rglob("*"):
                        if file.is_file():
                            zf.write(file, arcname=str(Path(target.name) / file.relative_to(target)))
    else:
        archive_path = ARTIFACTS / f"{tag}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tf:
            for target in targets:
                if target.is_file():
                    tf.add(target, arcname=target.name)
                elif target.is_dir():
                    tf.add(target, arcname=target.name)

    print(f"\n>>> Archive: {archive_path} ({archive_path.stat().st_size // 1024} KB)")
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gitmove executables with PyInstaller")
    parser.add_argument("--target", choices=["all", "cli", "gui"], default="all")
    parser.add_argument("--onefile", action="store_true", default=True)
    parser.add_argument("--onedir", action="store_true", help="Build directory bundles instead of single files")
    parser.add_argument("--no-archive", action="store_true", help="Skip creating zip/tar.gz artifact")
    args = parser.parse_args()

    onefile = not args.onedir
    version = _version()
    built: list[Path] = []

    if args.target in {"all", "cli"}:
        built.append(
            _build("gitmove", ROOT / "scripts" / "entry_cli.py", windowed=False, onefile=onefile, gui=False)
        )

    if args.target in {"all", "gui"}:
        built.append(
            _build("gitmove-gui", ROOT / "scripts" / "entry_gui.py", windowed=True, onefile=onefile, gui=True)
        )

    if not args.no_archive:
        _archive(version, built)

    print("\nBuild complete:")
    for path in built:
        size = path.stat().st_size // 1024 if path.exists() else 0
        print(f"  {path} ({size} KB)")


if __name__ == "__main__":
    main()
