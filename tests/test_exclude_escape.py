"""Exclude pattern escaping for special gitignore characters."""

from __future__ import annotations

from gitmove import exclude as exclude_mod


def test_root_level_pattern_gets_leading_slash() -> None:
    assert exclude_mod.to_exclude_pattern("config") == "/config"
    assert exclude_mod.to_exclude_pattern(".env") == "/.env"


def test_nested_pattern_no_extra_prefix() -> None:
    assert exclude_mod.to_exclude_pattern("src/foo/x") == "src/foo/x"


def test_special_characters_escaped() -> None:
    assert exclude_mod.to_exclude_pattern("foo#bar") == r"/foo\#bar"
    assert exclude_mod.to_exclude_pattern("a[b]c") == r"/a\[b\]c"
    assert exclude_mod.to_exclude_pattern("wild*card") == r"/wild\*card"
