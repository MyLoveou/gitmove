"""Vendor configuration templates (~/.gitmove/templates.toml + built-ins)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomllib

from gitmove.registry import config_dir

BUILTIN_TEMPLATES: dict[str, dict[str, str | bool]] = {
    "cursor-spec": {
        "repo_path": ".cursor",
        "source_url": "https://github.com/MyLoveou/cursor-project-spec",
        "source_ref": "main",
        "auto_skip_tracked": True,
    },
}


@dataclass
class VendorTemplate:
    id: str
    repo_path: str
    source_url: str
    source_ref: str = "main"
    auto_skip_tracked: bool = True
    builtin: bool = False


def templates_path() -> Path:
    return config_dir() / "templates.toml"


def _load_user_templates() -> dict[str, VendorTemplate]:
    path = templates_path()
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    result: dict[str, VendorTemplate] = {}
    for item in data.get("templates", []):
        if not isinstance(item, dict):
            continue
        tid = item.get("id")
        if not isinstance(tid, str):
            continue
        result[tid] = VendorTemplate(
            id=tid,
            repo_path=str(item.get("repo_path", "")),
            source_url=str(item.get("source_url", "")),
            source_ref=str(item.get("source_ref", "main") or "main"),
            auto_skip_tracked=bool(item.get("auto_skip_tracked", True)),
            builtin=False,
        )
    return result


def list_templates() -> list[VendorTemplate]:
    user = _load_user_templates()
    merged: dict[str, VendorTemplate] = {}
    for tid, raw in BUILTIN_TEMPLATES.items():
        merged[tid] = VendorTemplate(
            id=tid,
            repo_path=str(raw["repo_path"]),
            source_url=str(raw["source_url"]),
            source_ref=str(raw.get("source_ref", "main")),
            auto_skip_tracked=bool(raw.get("auto_skip_tracked", True)),
            builtin=True,
        )
    for tid, template in user.items():
        merged[tid] = template  # user overrides builtin
    return sorted(merged.values(), key=lambda item: item.id)


def get_template(template_id: str) -> VendorTemplate | None:
    for item in list_templates():
        if item.id == template_id:
            return item
    return None


def resolve_template(
    template_id: str,
    *,
    repo_path_override: str | None = None,
    source_ref_override: str | None = None,
) -> VendorTemplate:
    from gitmove.errors import catalog_error

    template = get_template(template_id)
    if template is None:
        raise catalog_error("TEMPLATE_NOT_FOUND", message=f"Unknown template: {template_id}")
    return VendorTemplate(
        id=template.id,
        repo_path=repo_path_override or template.repo_path,
        source_url=template.source_url,
        source_ref=source_ref_override or template.source_ref,
        auto_skip_tracked=template.auto_skip_tracked,
        builtin=template.builtin,
    )
