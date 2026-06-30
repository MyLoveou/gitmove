"""Tests for vendor templates."""

from __future__ import annotations

import pytest

from gitmove.errors import GitMoveError
from gitmove import templates as templates_mod


def test_list_templates_includes_cursor_spec() -> None:
    ids = [item.id for item in templates_mod.list_templates()]
    assert "cursor-spec" in ids


def test_resolve_template() -> None:
    tpl = templates_mod.resolve_template("cursor-spec")
    assert tpl.repo_path == ".cursor"
    assert "cursor-project-spec" in tpl.source_url


def test_unknown_template_raises() -> None:
    with pytest.raises(GitMoveError) as exc:
        templates_mod.resolve_template("no-such-template")
    assert exc.value.code == "TEMPLATE_NOT_FOUND"


def test_resolve_template_ref_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    path = templates_mod.templates_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '[[templates]]\nid = "dev-spec"\nrepo_path = ".cursor"\n'
        'source_url = "https://example.com/spec.git"\nsource_ref = "dev"\n',
        encoding="utf-8",
    )
    tpl = templates_mod.resolve_template("dev-spec", source_ref_override="main")
    assert tpl.source_ref == "main"


def test_load_user_templates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITMOVE_HOME", str(tmp_path))
    path = templates_mod.templates_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '[[templates]]\nid = "custom"\nrepo_path = "tools"\nsource_url = "https://example.com/x.git"\n',
        encoding="utf-8",
    )
    ids = [t.id for t in templates_mod.list_templates()]
    assert "custom" in ids
