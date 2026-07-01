"""Tests for Windows installer packaging metadata."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "scripts" / "installer" / "gitmove.iss"


def test_installer_script_exists_and_references_executables() -> None:
    assert ISS.is_file()
    text = ISS.read_text(encoding="utf-8")
    assert "gitmove.exe" in text
    assert "gitmove-gui.exe" in text
    assert "MyAppVersion" in text
    assert "EnvAddPath" in text


def test_build_installer_version_matches_package() -> None:
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from gitmove import __version__

    spec = importlib.util.spec_from_file_location(
        "build_installer",
        ROOT / "scripts" / "build_installer.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._version() == __version__
