"""Unit tests for Vendor add form (T-V1, T-V2)."""

from __future__ import annotations

from gitmove.gui.vendor_forms import (
    VendorAddForm,
    add_vendor_kwargs,
    cursor_preset,
    format_cli_preview,
    submit_vendor_add,
    validate_vendor_form,
)


def test_cursor_preset_fills_cursor_defaults() -> None:
    form = cursor_preset()
    assert form.repo_path == ".cursor"
    assert form.name == "personal-cursor"
    assert form.migrate is True
    assert form.auto_skip_tracked is True


def test_validate_rejects_empty_repo_path() -> None:
    form = VendorAddForm(source_url="https://github.com/a/b.git", name="v1")
    errors = validate_vendor_form(form, existing_names=set())
    assert any("路径" in err for err in errors)


def test_validate_rejects_invalid_name() -> None:
    form = VendorAddForm(
        repo_path=".cursor",
        name="bad name!",
        source_url="https://github.com/a/b.git",
    )
    errors = validate_vendor_form(form, existing_names=set())
    assert any("名称" in err for err in errors)


def test_validate_rejects_duplicate_name() -> None:
    form = VendorAddForm(
        repo_path=".cursor",
        name="existing",
        source_url="https://github.com/a/b.git",
    )
    errors = validate_vendor_form(form, existing_names={"existing"})
    assert any("已存在" in err for err in errors)


def test_validate_accepts_valid_form() -> None:
    form = VendorAddForm(
        repo_path=".cursor",
        name="personal-cursor",
        source_url="https://github.com/org/spec.git",
        source_ref="main",
        source_pin="v1.0.0",
        migrate=True,
    )
    assert validate_vendor_form(form, existing_names=set()) == []


def test_add_vendor_kwargs_omits_empty_optionals() -> None:
    form = VendorAddForm(
        repo_path=".cursor",
        name="personal-cursor",
        source_url="https://github.com/org/spec.git",
        source_ref="main",
        migrate=True,
    )
    kwargs = add_vendor_kwargs(form)
    assert kwargs["source_url"] == "https://github.com/org/spec.git"
    assert kwargs["migrate"] is True
    assert kwargs["source_pin"] is None
    assert kwargs["cache_path"] is None


def test_format_cli_preview_includes_required_flags() -> None:
    form = cursor_preset()
    form.source_url = "https://github.com/org/spec.git"
    form.source_ref = "main"
    preview = format_cli_preview(form)
    assert "gitmove vendor add" in preview
    assert ".cursor" in preview
    assert "--from" in preview
    assert "--migrate" in preview


def test_submit_vendor_add_calls_add_vendor(git_repo, monkeypatch) -> None:
    from unittest.mock import MagicMock

    captured: dict = {}

    def fake_add(root, repo_path, **kwargs):
        captured["repo_path"] = repo_path
        captured.update(kwargs)
        entry = MagicMock()
        entry.name = kwargs.get("name")
        return entry

    monkeypatch.setattr("gitmove.gui.vendor_forms.vendor_mod.add_vendor", fake_add)
    form = VendorAddForm(
        repo_path=".cursor",
        name="personal-cursor",
        source_url="https://github.com/org/spec.git",
        migrate=True,
    )
    submit_vendor_add(git_repo, form)
    assert captured["repo_path"] == ".cursor"
    assert captured["migrate"] is True
