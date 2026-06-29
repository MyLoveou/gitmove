from __future__ import annotations

import os
from unittest import mock

import pytest

from gitmove.platform_util import default_link_type, resolve_link_type


def test_default_link_type_windows() -> None:
    with mock.patch("gitmove.platform_util.os.name", "nt"):
        assert default_link_type() == "junction"


def test_default_link_type_unix() -> None:
    with mock.patch("gitmove.platform_util.os.name", "posix"):
        assert default_link_type() == "symlink"


def test_resolve_link_type_junction_on_unix_falls_back() -> None:
    with mock.patch("gitmove.platform_util.os.name", "posix"):
        assert resolve_link_type("junction") == "symlink"


def test_resolve_link_type_invalid() -> None:
    with pytest.raises(ValueError):
        resolve_link_type("hardlink")


def test_platform_label_linux() -> None:
    with mock.patch("gitmove.platform_util.sys.platform", "linux"):
        from gitmove.platform_util import platform_label

        assert platform_label() == "Linux"
