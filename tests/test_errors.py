"""Tests for structured errors and remediation."""

from __future__ import annotations

import pytest

from gitmove.errors import (
    CATALOG,
    GitMoveError,
    catalog_error,
    print_error,
    remediation_for_doctor,
    wrap_exception,
    wrap_vendor_error,
)
from gitmove import vendor as vendor_mod
from gitmove.registry import RegistryError


def test_catalog_has_minimum_codes() -> None:
    assert len(CATALOG) >= 20
    assert "PROJECTS_UPDATE_FF_FAILED" in CATALOG


def test_catalog_error_substitutes_context() -> None:
    err = catalog_error("VENDOR_FF_BLOCKED", name="cursor-spec", ref="main", cache="/tmp/cache")
    assert "cursor-spec" in (err.steps[-1].command or "")


def test_wrap_vendor_ff() -> None:
    err = wrap_vendor_error(vendor_mod.VendorError("merge --ff-only failed"))
    assert err.code == "VENDOR_FF_BLOCKED"


def test_wrap_registry_alias() -> None:
    err = wrap_exception(RegistryError("Unknown project alias: foo"))
    assert err.code == "REPO_CONTEXT_ALIAS_MISSING"


def test_remediation_for_skip_doctor() -> None:
    code, steps = remediation_for_doctor("skip", "skip-worktree 未生效: config.local.json")
    assert code == "SKIP_NOT_ACTIVE"
    assert steps[0].command == "gitmove apply"


def test_gitmove_error_is_exception() -> None:
    err = catalog_error("REPO_NOT_INIT")
    with pytest.raises(GitMoveError):
        raise err


def test_print_error_smoke(capsys) -> None:
    from rich.console import Console

    console = Console(force_terminal=True, width=120)
    print_error(console, catalog_error("VENDOR_PATH_EXISTS"))
    # no raise


def test_wrap_exception_gitmove_passthrough() -> None:
    err = catalog_error("REPO_NOT_INIT")
    assert wrap_exception(err) is err


def test_wrap_exception_file_not_found_init() -> None:
    err = wrap_exception(FileNotFoundError("gitmove is not initialized; run: gitmove init"))
    assert err.code == "REPO_NOT_INIT"


def test_wrap_exception_value_error() -> None:
    err = wrap_exception(ValueError("bad path"))
    assert err.code == "VALIDATION_ERROR"


def test_remediation_link_missing() -> None:
    code, steps = remediation_for_doctor("link", "仓库内链接缺失: tools")
    assert code == "LINK_MISSING"


def test_wrap_vendor_cache_missing() -> None:
    err = wrap_vendor_error(vendor_mod.VendorError("Cache missing for vendor x"))
    assert err.code == "VENDOR_CACHE_MISSING"


def test_wrap_vendor_path_exists() -> None:
    err = wrap_vendor_error(vendor_mod.VendorError("tools exists and is not a link"))
    assert err.code == "VENDOR_PATH_EXISTS"


def test_remediation_vendor_cache() -> None:
    code, steps = remediation_for_doctor("vendor", "vendor cache 缺失: foo (/tmp/c)")
    assert code == "VENDOR_CACHE_MISSING"


def test_remediation_vendor_pin_drift() -> None:
    code, steps = remediation_for_doctor("vendor", "vendor tools pin drift: HEAD != v1.0.0")
    assert code == "VENDOR_FF_BLOCKED"
    assert steps


def test_remediation_vendor_pin_not_found() -> None:
    code, steps = remediation_for_doctor("vendor", "vendor tools pin not found: missing-tag")
    assert code == "VENDOR_PIN_NOT_FOUND"
    assert steps


def test_catalog_unknown_code() -> None:
    err = catalog_error("NOT_A_REAL_CODE", message="custom")
    assert err.code == "NOT_A_REAL_CODE"


def test_error_to_dict_keys() -> None:
    from gitmove.errors import error_to_dict

    data = error_to_dict(catalog_error("SKIP_NOT_ACTIVE"))
    assert data["ok"] is False
    assert data["code"] == "SKIP_NOT_ACTIVE"
    assert data["steps"]
