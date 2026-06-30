"""stdio MCP server for gitmove."""

from __future__ import annotations

import asyncio
import os

from mcp.server.fastmcp import FastMCP

from gitmove.mcp import impl

mcp = FastMCP("gitmove")

os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")
os.environ.setdefault("GCM_INTERACTIVE", "Never")


def _thread(fn, *args, **kwargs):
    return asyncio.to_thread(fn, *args, **kwargs)


# --- read ---


@mcp.tool()
async def gitmove_doctor(repo: str | None = None, alias: str | None = None) -> str:
    """Run gitmove health check for a repository path or projects alias."""
    return await _thread(impl.doctor_impl, repo, alias)


@mcp.tool()
async def gitmove_list_projects(group: str | None = None) -> str:
    """List registered projects from ~/.gitmove/projects.toml."""
    return await _thread(impl.list_projects_impl, group)


@mcp.tool()
async def gitmove_explain_error(code: str) -> str:
    """Look up a gitmove error code and return remediation steps."""
    return await _thread(impl.explain_error_impl, code)


@mcp.tool()
async def gitmove_skip_list(repo: str | None = None, alias: str | None = None) -> str:
    """List skip-worktree (freeze) status for all configured paths."""
    return await _thread(impl.skip_list_impl, repo, alias)


@mcp.tool()
async def gitmove_link_list(repo: str | None = None, alias: str | None = None) -> str:
    """List configured external directory links."""
    return await _thread(impl.link_list_impl, repo, alias)


@mcp.tool()
async def gitmove_vendor_list(repo: str | None = None, alias: str | None = None) -> str:
    """List configured vendors."""
    return await _thread(impl.vendor_list_impl, repo, alias)


@mcp.tool()
async def gitmove_worktree_list(repo: str | None = None, alias: str | None = None) -> str:
    """List configured personal worktrees."""
    return await _thread(impl.worktree_list_impl, repo, alias)


@mcp.tool()
async def gitmove_repo_summary(repo: str | None = None, alias: str | None = None) -> str:
    """Summarize gitmove.toml configuration (skip/link/vendor/worktree counts)."""
    return await _thread(impl.repo_summary_impl, repo, alias)


@mcp.tool()
async def gitmove_vendor_status(
    repo: str | None = None,
    alias: str | None = None,
    name: str | None = None,
    fetch: bool = True,
) -> str:
    """Check vendor upstream status; omit name to check all vendors."""
    return await _thread(impl.vendor_status_impl, repo, alias, name, fetch)


@mcp.tool()
async def gitmove_vendor_template_list() -> str:
    """List built-in and user vendor templates."""
    return await _thread(impl.vendor_template_list_impl)


@mcp.tool()
async def gitmove_sync_check(
    repo: str | None = None,
    alias: str | None = None,
    fetch: bool = False,
) -> str:
    """Check skip-worktree paths for local/remote drift before pull."""
    return await _thread(impl.sync_check_impl, repo, alias, fetch)


@mcp.tool()
async def gitmove_project_health(group: str | None = None) -> str:
    """Batch doctor for all registered projects."""
    return await _thread(impl.project_health_impl, group)


# --- write (confirm=true + GITMOVE_MCP_ALLOW_WRITE=1) ---


@mcp.tool()
async def gitmove_init(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    external_base: str | None = None,
) -> str:
    """Initialize .git/gitmove.toml for a repository."""
    return await _thread(impl.init_impl, repo, alias, confirm, external_base)


@mcp.tool()
async def gitmove_apply(repo: str | None = None, alias: str | None = None, confirm: bool = False) -> str:
    """Apply skip/link/vendor/worktree configuration."""
    return await _thread(impl.apply_impl, repo, alias, confirm)


@mcp.tool()
async def gitmove_skip_add(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    """Freeze a tracked file or directory via skip-worktree (gitmove skip add)."""
    return await _thread(impl.skip_add_impl, path, repo, alias, confirm)


@mcp.tool()
async def gitmove_skip_remove(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    """Unfreeze a path (gitmove skip remove)."""
    return await _thread(impl.skip_remove_impl, path, repo, alias, confirm)


@mcp.tool()
async def gitmove_link_add(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    external: str | None = None,
    link_type: str | None = None,
    migrate: bool = False,
) -> str:
    """Create junction/symlink from repo path to external directory."""
    return await _thread(impl.link_add_impl, path, repo, alias, confirm, external, link_type, migrate)


@mcp.tool()
async def gitmove_link_remove(
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    delete_external: bool = False,
) -> str:
    """Remove an external link (keeps external data by default)."""
    return await _thread(impl.link_remove_impl, path, repo, alias, confirm, delete_external)


@mcp.tool()
async def gitmove_link_set_base(
    base: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
) -> str:
    """Set default external base directory in gitmove config."""
    return await _thread(impl.link_set_base_impl, base, repo, alias, confirm)


@mcp.tool()
async def gitmove_vendor_add(
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
    """Add upstream vendor (clone cache + link). Use source_url or template."""
    return await _thread(
        impl.vendor_add_impl,
        repo_path,
        repo,
        alias,
        confirm,
        source_url,
        name,
        source_ref,
        template,
        migrate,
        shallow,
        include_path,
    )


@mcp.tool()
async def gitmove_vendor_sync(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    name: str | None = None,
    fetch: bool = True,
) -> str:
    """Sync vendor cache from upstream; omit name to sync all."""
    return await _thread(impl.vendor_sync_impl, repo, alias, confirm, name, fetch)


@mcp.tool()
async def gitmove_vendor_remove(
    name: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    keep_skip: bool = True,
) -> str:
    """Remove vendor link (does not purge cache)."""
    return await _thread(impl.vendor_remove_impl, name, repo, alias, confirm, keep_skip)


@mcp.tool()
async def gitmove_worktree_add(
    name: str,
    path: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    branch: str | None = None,
    new_branch: bool = False,
) -> str:
    """Add a personal git worktree."""
    return await _thread(impl.worktree_add_impl, name, path, repo, alias, confirm, branch, new_branch)


@mcp.tool()
async def gitmove_worktree_remove(
    name: str,
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    force: bool = False,
) -> str:
    """Remove a configured worktree."""
    return await _thread(impl.worktree_remove_impl, name, repo, alias, confirm, force)


@mcp.tool()
async def gitmove_sync_pull(
    repo: str | None = None,
    alias: str | None = None,
    confirm: bool = False,
    fetch: bool = True,
    dry_run: bool = False,
) -> str:
    """Pull when skip paths are clear; abort without changes if remote drifts need manual resolution."""
    return await _thread(impl.sync_pull_impl, repo, alias, confirm, fetch, dry_run)


@mcp.tool()
async def gitmove_projects_apply_all(group: str | None = None, confirm: bool = False) -> str:
    """Apply gitmove config for all registered projects."""
    return await _thread(impl.projects_apply_all_impl, group, confirm)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
