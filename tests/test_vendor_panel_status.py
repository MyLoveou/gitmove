"""Unit tests for Vendor status labels (T-V3)."""

from __future__ import annotations

from gitmove import vendor as vendor_mod
from gitmove.gui.vendor_panel import (
    merge_status_label,
    status_tone,
    vendor_tree_rows,
)


def test_merge_status_label_ok_from_list() -> None:
    item = vendor_mod.VendorStatus(
        name="v",
        repo_path=".cursor",
        source_url="https://example.com/a.git",
        source_ref="main",
        cache_path=vendor_mod.default_cache_path("v"),
        link_ok=True,
        cache_exists=True,
    )
    assert merge_status_label(item, None) == "— 未检查"


def test_merge_status_label_ok_when_sync_clean() -> None:
    item = vendor_mod.VendorStatus(
        name="v",
        repo_path=".cursor",
        source_url="https://example.com/a.git",
        source_ref="main",
        cache_path=vendor_mod.default_cache_path("v"),
        link_ok=True,
        cache_exists=True,
    )
    sync = vendor_mod.VendorSyncResult(name="v", ok=True, behind=0)
    assert merge_status_label(item, sync) == "● 正常"


def test_merge_status_label_behind_from_sync() -> None:
    item = vendor_mod.VendorStatus(
        name="v",
        repo_path=".cursor",
        source_url="https://example.com/a.git",
        source_ref="main",
        cache_path=vendor_mod.default_cache_path("v"),
        link_ok=True,
        cache_exists=True,
    )
    sync = vendor_mod.VendorSyncResult(name="v", ok=True, behind=2)
    assert "落后" in merge_status_label(item, sync)


def test_merge_status_label_link_broken() -> None:
    item = vendor_mod.VendorStatus(
        name="v",
        repo_path=".cursor",
        source_url="https://example.com/a.git",
        source_ref="main",
        cache_path=vendor_mod.default_cache_path("v"),
        link_ok=False,
        cache_exists=True,
    )
    assert "链接" in merge_status_label(item, None)


def test_status_tone_maps_semantics() -> None:
    assert status_tone("● 正常") == "success"
    assert status_tone("⚠ 落后 2") == "warning"
    assert status_tone("✗ 链接异常") == "error"
    assert status_tone("— 未检查") == "muted"


def test_vendor_tree_rows_includes_status(git_repo, monkeypatch) -> None:
    from gitmove.config import VendorEntry
    from gitmove.skip import load_config, save_config

    cfg = load_config(git_repo)
    cfg.vendors.append(
        VendorEntry(
            name="test-v",
            repo_path="tools",
            source_url="https://example.com/t.git",
            source_ref="main",
        )
    )
    save_config(git_repo, cfg)

    def fake_list(_root):
        return [
            vendor_mod.VendorStatus(
                name="test-v",
                repo_path="tools",
                source_url="https://example.com/t.git",
                source_ref="main",
                cache_path=vendor_mod.default_cache_path("test-v"),
                link_ok=True,
                cache_exists=True,
            )
        ]

    monkeypatch.setattr(vendor_mod, "list_vendors", fake_list)
    rows = vendor_tree_rows(git_repo)
    assert len(rows) == 1
    assert rows[0].name == "test-v"
    assert rows[0].status == "— 未检查"
