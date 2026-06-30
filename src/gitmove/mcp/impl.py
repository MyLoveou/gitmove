"""MCP tool implementations mapping to gitmove business modules."""

from __future__ import annotations

from dataclasses import asdict

from gitmove import doctor as doctor_mod
from gitmove import link as link_mod
from gitmove import projects as projects_mod
from gitmove import skip as skip_mod
from gitmove import sync as sync_mod
from gitmove import templates as templates_mod
from gitmove import vendor as vendor_mod
from gitmove import worktree as worktree_mod
from gitmove.config import config_path_for_repo
from gitmove.api.response import failure, success
from gitmove.errors import CATALOG, GitMoveError, catalog_error, error_to_dict, wrap_exception
from gitmove.mcp.helpers import check_confirm, resolve_repo, run_repo_tool, run_tool, serialize
from gitmove.registry import list_projects
from gitmove.repo_context import RepoContextError
from gitmove.sync import SyncConflictBlocked

# --- read tools ---


def doctor_impl(repo: str | None = None, alias: str | None = None) -> str:
    def run(root):
        report = doctor_mod.run_doctor(root)
        return {
            "ok": report.ok,
            "error_count": report.error_count,
            "warn_count": report.warn_count,
            "issues": [asdict(issue) for issue in report.issues],
        }

    return run_repo_tool("gitmove_doctor", repo, alias, run)


def list_projects_impl(group: str | None = None) -> str:
    return run_tool(
        "gitmove_list_projects",
        lambda: [
            {
                "alias": entry.alias,
                "path": str(entry.path),
                "group": entry.group,
                "last_used": entry.last_used,
            }
            for entry in list_projects(group=group)
        ],
    )


def explain_error_impl(code: str) -> str:
    tool = "gitmove_explain_error"
    template = CATALOG.get(code)
    if template is None:
        return failure(
            tool=tool,
            err=catalog_error("UNKNOWN_ERROR_CODE", message=f"未知错误码: {code}", code=code),
        )
    err = GitMoveError(
        code=template.code,
        message=template.message,
        cause=template.cause,
        steps=list(template.steps),
        doc_anchor=template.doc_anchor,
    )
    return run_tool(tool, lambda: error_to_dict(err))


def skip_list_impl(repo: str | None = None, alias: str | None = None) -> str:
    return run_repo_tool("gitmove_skip_list", repo, alias, skip_mod.list_status)


def link_list_impl(repo: str | None = None, alias: str | None = None) -> str:
    return run_repo_tool("gitmove_link_list", repo, alias, link_mod.list_links)


def vendor_list_impl(repo: str | None = None, alias: str | None = None) -> str:
    return run_repo_tool("gitmove_vendor_list", repo, alias, vendor_mod.list_vendors)


def worktree_list_impl(repo: str | None = None, alias: str | None = None) -> str:
    return run_repo_tool("gitmove_worktree_list", repo, alias, worktree_mod.list_worktrees)


def repo_summary_impl(repo: str | None = None, alias: str | None = None) -> str:
    def run(root):
        cfg_path = config_path_for_repo(root)
        if not cfg_path.exists():
            return {"initialized": False}
        cfg = skip_mod.load_config(root)
        return {
            "initialized": True,
            "config_path": str(cfg_path),
            "skip_count": len(cfg.skip_paths),
            "link_count": len(cfg.links),
            "vendor_count": len(cfg.vendors),
            "worktree_count": len(cfg.worktrees),
            "skip_paths": list(cfg.skip_paths),
            "links": [serialize(link) for link in cfg.links],
            "vendors": [
                {"name": v.name, "repo_path": v.repo_path, "source_ref": v.source_ref}
                for v in cfg.vendors
            ],
        }

    return run_repo_tool("gitmove_repo_summary", repo, alias, run)


def vendor_status_impl(
    repo: str | None = None,
    alias: str | None = None,
    name: str | None = None,
    fetch: bool = True,
) -> str:
    def run(root):
        if name:
            return vendor_mod.vendor_status(root, name, fetch=fetch)
        return [
            vendor_mod.vendor_status(root, entry.name, fetch=fetch)
            for entry in skip_mod.load_config(root).vendors
        ]

    return run_repo_tool("gitmove_vendor_status", repo, alias, run)


def vendor_template_list_impl() -> str:
    return run_tool(
        "gitmove_vendor_template_list",
        lambda: [
            {
                "id": item.id,
                "repo_path": item.repo_path,
                "source_url": item.source_url,
                "source_ref": item.source_ref,
                "builtin": item.builtin,
            }
            for item in templates_mod.list_templates()
        ],
    )


def sync_check_impl(
    repo: str | None = None,
    alias: str | None = None,
    fetch: bool = False,
) -> str:
    def run(root):
        report = sync_mod.check_sync(root, fetch=fetch)
        return {
            "upstream": report.upstream,
            "attention_count": len(report.attention_items),
            "drifts": [serialize(d) for d in report.drifts],
        }

    return run_repo_tool("gitmove_sync_check", repo, alias, run)


def project_health_impl(group: str | None = None) -> str:
    return run_tool(
        "gitmove_project_health",
        lambda: serialize(projects_mod.batch_doctor(projects_mod.iter_projects(group=group))),
    )


# --- write tools ---


def apply_impl(repo: str | None = None, alias: str | None = None, confirm: bool = False) -> str:
    if blocked := check_confirm("gitmove_apply", confirm):
        return blocked

    def run(root):
        report = doctor_mod.apply_all(root)
        return {
            "skip": len(report.skip),
            "links": len(report.links),
            "worktrees": len(report.worktrees),
            "vendors": len(report.vendors),
        }

    return run_repo_tool("gitmove_apply", repo, alias, run)


def init_impl(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    external_base: str | None = None,
) -> str:
    if blocked := check_confirm("gitmove_init", confirm):
        return blocked

    def run(root):
        path = doctor_mod.init_repo(root, external_base=external_base)
        return {"config_path": str(path)}

    return run_repo_tool("gitmove_init", repo, alias, run)


def skip_add_impl(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_skip_add", confirm):
        return blocked
    return run_repo_tool("gitmove_skip_add", repo, alias, lambda root: skip_mod.add_skip(root, path))


def skip_remove_impl(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_skip_remove", confirm):
        return blocked
    return run_repo_tool("gitmove_skip_remove", repo, alias, lambda root: skip_mod.remove_skip(root, path))


def link_add_impl(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    external: str | None = None,
    link_type: str | None = None,
    migrate: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_link_add", confirm):
        return blocked
    from gitmove.platform_util import resolve_link_type

    return run_repo_tool(
        "gitmove_link_add",
        repo,
        alias,
        lambda root: link_mod.add_link(
            root,
            path,
            external,
            link_type=resolve_link_type(link_type),
            migrate=migrate,
        ),
    )


def link_remove_impl(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    delete_external: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_link_remove", confirm):
        return blocked

    def run(root):
        link_mod.remove_link(root, path, keep_external=not delete_external)
        return {"removed": path}

    return run_repo_tool("gitmove_link_remove", repo, alias, run)


def link_set_base_impl(
    base: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_link_set_base", confirm):
        return blocked
    return run_repo_tool("gitmove_link_set_base", repo, alias, lambda root: link_mod.set_external_base(root, base))


def vendor_add_impl(
    repo_path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    source_url: str | None = None,
    name: str | None = None,
    source_ref: str | None = None,
    template: str | None = None,
    migrate: bool = False,
    shallow: bool = True,
    include_path: str | None = None,
) -> str:
    if blocked := check_confirm("gitmove_vendor_add", confirm):
        return blocked
    resolved_url = source_url
    resolved_ref = source_ref
    if template:
        tpl = templates_mod.resolve_template(
            template,
            repo_path_override=repo_path,
            source_ref_override=source_ref,
        )
        resolved_url = resolved_url or tpl.source_url
        resolved_ref = source_ref if source_ref is not None else tpl.source_ref
    if not resolved_url:
        raise catalog_error("VALIDATION_ERROR", message="需要提供 source_url 或 template")
    include_paths = [include_path] if include_path else None

    def run(root):
        return vendor_mod.add_vendor(
            root,
            repo_path,
            source_url=resolved_url,
            name=name,
            source_ref=resolved_ref or "main",
            migrate=migrate,
            shallow=shallow,
            include_paths=include_paths,
        )

    return run_repo_tool("gitmove_vendor_add", repo, alias, run)


def vendor_sync_impl(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    name: str | None = None,
    fetch: bool = True,
) -> str:
    if blocked := check_confirm("gitmove_vendor_sync", confirm):
        return blocked

    def run(root):
        if name:
            return vendor_mod.sync_vendor(root, name, fetch=fetch)
        return vendor_mod.sync_all_vendors(root, fetch=fetch)

    return run_repo_tool("gitmove_vendor_sync", repo, alias, run)


def vendor_remove_impl(
    name: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    keep_skip: bool = True,
) -> str:
    if blocked := check_confirm("gitmove_vendor_remove", confirm):
        return blocked

    def run(root):
        vendor_mod.remove_vendor(root, name, keep_skip=keep_skip, purge_cache=False)
        return {"removed": name}

    return run_repo_tool("gitmove_vendor_remove", repo, alias, run)


def worktree_add_impl(
    name: str,
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    branch: str | None = None,
    new_branch: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_worktree_add", confirm):
        return blocked
    return run_repo_tool(
        "gitmove_worktree_add",
        repo,
        alias,
        lambda root: worktree_mod.add_worktree(
            root, name, path, branch=branch, create_branch=new_branch
        ),
    )


def worktree_remove_impl(
    name: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    force: bool = False,
) -> str:
    if blocked := check_confirm("gitmove_worktree_remove", confirm):
        return blocked

    def run(root):
        worktree_mod.remove_worktree(root, name, force=force)
        return {"removed": name}

    return run_repo_tool("gitmove_worktree_remove", repo, alias, run)


def sync_pull_impl(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    fetch: bool = True,
    dry_run: bool = False,
) -> str:
    tool = "gitmove_sync_pull"
    if blocked := check_confirm(tool, confirm):
        return blocked
    try:
        root = resolve_repo(repo, alias)
    except RepoContextError as exc:
        return failure(tool=tool, err=GitMoveError("REPO_NOT_GIT", str(exc)))
    try:
        result = sync_mod.sync_pull_abort_on_conflict(root, fetch=fetch, dry_run=dry_run)
        return success(tool=tool, repo=str(root), data=serialize(result))
    except SyncConflictBlocked as exc:
        conflicts = [serialize(d) for d in exc.conflicts]
        return failure(
            tool=tool,
            err=catalog_error(
                "SYNC_CONFLICT_BLOCKED",
                message=f"检测到 {len(conflicts)} 个 skip 路径冲突，已中止 pull，未修改仓库",
                conflicts=conflicts,
            ),
            repo=str(root),
        )
    except Exception as exc:  # noqa: BLE001
        return failure(tool=tool, err=wrap_exception(exc), repo=str(root))


def projects_apply_all_impl(group: str | None = None, confirm: bool = False) -> str:
    if blocked := check_confirm("gitmove_projects_apply_all", confirm):
        return blocked
    return run_tool(
        "gitmove_projects_apply_all",
        lambda: projects_mod.batch_apply(projects_mod.iter_projects(group=group)),
    )
