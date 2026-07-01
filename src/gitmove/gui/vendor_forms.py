"""Vendor add form validation and CLI mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gitmove import vendor as vendor_mod
from gitmove.config import VendorEntry


@dataclass
class VendorAddForm:
    repo_path: str = ""
    name: str = ""
    source_url: str = ""
    source_ref: str = "main"
    source_pin: str = ""
    migrate: bool = False
    auto_skip_tracked: bool = True
    shallow: bool = True
    cache_path: str = ""
    include_path: str = ""


def cursor_preset() -> VendorAddForm:
    return VendorAddForm(
        repo_path=".cursor",
        name="personal-cursor",
        migrate=True,
        auto_skip_tracked=True,
    )


def validate_vendor_form(form: VendorAddForm, *, existing_names: set[str]) -> list[str]:
    errors: list[str] = []
    repo_path = form.repo_path.strip()
    if not repo_path:
        errors.append("请输入仓库内挂载路径")
    elif ".." in repo_path.replace("\\", "/"):
        errors.append("挂载路径不能包含 ..")

    name = form.name.strip()
    if not name:
        errors.append("请输入 Vendor 名称")
    elif not vendor_mod.VENDOR_NAME_PATTERN.match(name):
        errors.append("Vendor 名称仅允许字母、数字、下划线与连字符")
    elif name in existing_names:
        errors.append(f"Vendor 名称已存在: {name}")

    url = form.source_url.strip()
    if not url:
        errors.append("请输入上游 Git URL")
    elif not (url.startswith("http://") or url.startswith("https://") or url.startswith("git@")):
        errors.append("上游 URL 格式无效")

    if not form.source_ref.strip():
        errors.append("请输入分支或 tag")

    return errors


def add_vendor_kwargs(form: VendorAddForm) -> dict[str, Any]:
    include_paths = [form.include_path.strip()] if form.include_path.strip() else None
    pin = form.source_pin.strip() or None
    cache = form.cache_path.strip() or None
    return {
        "source_url": form.source_url.strip(),
        "name": form.name.strip(),
        "source_ref": form.source_ref.strip(),
        "source_pin": pin,
        "cache_path": cache,
        "migrate": form.migrate,
        "auto_skip_tracked": form.auto_skip_tracked,
        "shallow": form.shallow,
        "include_paths": include_paths,
    }


def format_cli_preview(form: VendorAddForm) -> str:
    parts = [
        "gitmove vendor add",
        form.repo_path.strip() or "<path>",
        f"--from {form.source_url.strip() or '<url>'}",
        f"--ref {form.source_ref.strip() or 'main'}",
        f"--name {form.name.strip() or '<name>'}",
    ]
    if form.source_pin.strip():
        parts.append(f"--pin {form.source_pin.strip()}")
    if form.migrate:
        parts.append("--migrate")
    if not form.shallow:
        parts.append("--no-shallow")
    if form.cache_path.strip():
        parts.append(f"--cache {form.cache_path.strip()}")
    if form.include_path.strip():
        parts.append(f"--include-path {form.include_path.strip()}")
    return " ".join(parts)


def submit_vendor_add(root: Path, form: VendorAddForm) -> VendorEntry:
    kwargs = add_vendor_kwargs(form)
    return vendor_mod.add_vendor(root, form.repo_path.strip(), **kwargs)


def existing_vendor_names(root: Path) -> set[str]:
    from gitmove.skip import load_config

    return {entry.name for entry in load_config(root).vendors}
