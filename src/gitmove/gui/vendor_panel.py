"""Vendor tab row formatting and status labels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitmove import vendor as vendor_mod
from gitmove.skip import load_config


@dataclass(frozen=True)
class VendorTreeRow:
    name: str
    repo_path: str
    source: str
    pin: str
    status: str


def merge_status_label(
    item: vendor_mod.VendorStatus,
    sync: vendor_mod.VendorSyncResult | None,
) -> str:
    if not item.cache_exists:
        return "✗ Cache 缺失"
    if not item.link_ok:
        return "✗ 链接异常"
    if sync is not None:
        if not sync.ok:
            return "✗ 检查失败"
        if sync.pinned_drift:
            return "⚠ Pin 漂移"
        if sync.dirty:
            return "⚠ Cache 有改动"
        if sync.behind > 0:
            return f"⚠ 落后 {sync.behind}"
        return "● 正常"
    if item.link_ok and item.cache_exists:
        return "— 未检查"
    return "✗ 异常"


def status_tone(label: str) -> str:
    if label.startswith("●"):
        return "success"
    if label.startswith("⚠"):
        return "warning"
    if label.startswith("✗"):
        return "error"
    return "muted"


def vendor_tree_rows(
    root: Path,
    *,
    sync_by_name: dict[str, vendor_mod.VendorSyncResult] | None = None,
) -> list[VendorTreeRow]:
    cfg = load_config(root)
    vendors_by_name = {vendor.name: vendor for vendor in cfg.vendors}
    sync_map = sync_by_name or {}
    rows: list[VendorTreeRow] = []
    for item in vendor_mod.list_vendors(root):
        entry = vendors_by_name.get(item.name)
        pin = entry.source_pin if entry and entry.source_pin else "—"
        source = f"{item.source_url} @ {item.source_ref}"
        status = merge_status_label(item, sync_map.get(item.name))
        rows.append(
            VendorTreeRow(
                name=item.name,
                repo_path=item.repo_path,
                source=source,
                pin=pin,
                status=status,
            )
        )
    return rows
