"""gitmove CLI — local Git exclusions without .gitignore changes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from gitmove import __version__, git
from gitmove.config import config_path_for_repo
from gitmove.config_io import export_config, import_config, import_config_from_repo
from gitmove.doctor import apply_all as apply_all_report, init_repo, run_doctor
from gitmove import link as link_mod
from gitmove.platform_util import default_link_type, resolve_link_type
from gitmove import projects as projects_mod
from gitmove.projects import default_project_chooser, iter_projects, project_status
from gitmove.registry import (
    ProjectEntry,
    RegistryError,
    add_project,
    list_projects,
    remove_project,
    set_default,
    touch_last_used,
)
from gitmove.repo_context import RepoContextError, resolve_repo_root
from gitmove import skip as skip_mod
from gitmove.sync import check_sync, default_chooser, sync_pull
from gitmove import vendor as vendor_mod
from gitmove import worktree as worktree_mod

_CURRENT_REPO_OPT: str | None = None

app = typer.Typer(
    name="gitmove",
    help="Manage local-only Git exclusions: skip-worktree, external links, personal worktrees.",
    invoke_without_command=True,
)
skip_app = typer.Typer(help="skip-worktree: hide local changes to tracked files.")
link_app = typer.Typer(help="Link repo paths to external directories (junction/symlink).")
worktree_app = typer.Typer(help="Personal git worktree management.")
config_app = typer.Typer(help="Import and export gitmove.toml configuration.")
sync_app = typer.Typer(help="Check and pull remote changes for skip-worktree paths.")
projects_app = typer.Typer(help="Manage registered Git repositories.")
projects_sync_app = typer.Typer(help="Sync skip-worktree paths across projects.")
vendor_app = typer.Typer(help="Upstream Git vendor (cache clone + whole-repo link).")
console = Console()


def _root() -> Path:
    try:
        return resolve_repo_root(repo_opt=_CURRENT_REPO_OPT)
    except RepoContextError as exc:
        console.print(f"[red]Not a git repository.[/red] {exc}")
        raise typer.Exit(1) from exc


@app.callback()
def main(
    ctx: typer.Context,
    repo: Optional[str] = typer.Option(
        None,
        "--repo",
        "-C",
        help="Repository path or registered project alias.",
    ),
    version: Optional[bool] = typer.Option(None, "--version", "-V", help="Show version."),
) -> None:
    global _CURRENT_REPO_OPT
    _CURRENT_REPO_OPT = repo
    if version:
        console.print(f"gitmove {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@app.command("init")
def init_cmd(
    external_base: Optional[str] = typer.Option(
        None,
        "--external-base",
        "-e",
        help="Default external directory base (default: ~/gitmove-external/<repo-name>).",
    ),
) -> None:
    """Initialize .git/gitmove.toml in the current repository."""
    root = _root()
    cfg_path = config_path_for_repo(root)
    resolved = init_repo(root, external_base)

    console.print(f"[green]Initialized[/green] {cfg_path}")
    console.print(f"External base: {resolved}")
    console.print(f"Platform link type: {default_link_type()}")
    console.print("\nNext steps:")
    console.print("  gitmove skip add <path>       # mark tracked file as local-only")
    console.print("  gitmove link add <path>         # link to external directory")
    console.print("  gitmove apply                   # restore all settings after clone")
    console.print("  gitmove gui                     # open visual interface")


@app.command("apply")
def apply_cmd() -> None:
    """Apply skip-worktree, links, and worktrees from config (run after clone)."""
    root = _root()
    report = apply_all_report(root)

    console.print("[bold]skip-worktree[/bold]")
    _print_skip_table(report.skip)

    console.print("\n[bold]links[/bold]")
    _print_link_table(report.links)

    console.print("\n[bold]worktrees[/bold]")
    _print_worktree_table(report.worktrees)

    console.print("\n[bold]vendors[/bold]")
    _print_vendor_table(report.vendors)


@app.command("doctor")
def doctor_cmd() -> None:
    """Check configuration vs actual git state."""
    root = _root()
    if not config_path_for_repo(root).exists():
        console.print("[yellow]No config found.[/yellow] Run: gitmove init")
        raise typer.Exit(1)

    report = run_doctor(root)
    for issue in report.issues:
        if issue.level == "error":
            console.print(f"[red]MISS[/red] {issue.message}")
        elif issue.level == "warn":
            console.print(f"[yellow]WARN[/yellow] {issue.message}")
        else:
            console.print(f"[green]OK[/green] {issue.message}")

    if report.ok and report.error_count == 0 and report.warn_count == 0:
        console.print("[green]All checks passed.[/green]")
    elif report.error_count:
        console.print(f"\n[yellow]{report.error_count} issue(s)[/yellow]. Run: gitmove apply")
        raise typer.Exit(1)


@skip_app.command("add")
def skip_add(
    path: str = typer.Argument(..., help="Repo-relative file or directory path."),
) -> None:
    """Add skip-worktree for a path and persist to config."""
    root = _root()
    try:
        result = skip_mod.add_skip(root, path)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if not result.tracked:
        console.print(
            f"[yellow]Note:[/yellow] {result.path} is not tracked yet. "
            "It is saved in config; skip-worktree activates once git tracks it."
        )
    else:
        console.print(f"[green]skip-worktree enabled[/green] for {result.path}")


@skip_app.command("remove")
def skip_remove(path: str = typer.Argument(..., help="Repo-relative path.")) -> None:
    """Remove skip-worktree and drop from config."""
    root = _root()
    result = skip_mod.remove_skip(root, path)
    console.print(f"[green]skip-worktree removed[/green] for {result.path}")


@skip_app.command("list")
def skip_list() -> None:
    """List skip-worktree status."""
    _print_skip_table(skip_mod.list_status(_root()))


@link_app.command("add")
def link_add(
    path: str = typer.Argument(..., help="Repo-relative directory to link externally."),
    external: Optional[str] = typer.Option(None, "--external", "-e", help="External absolute path."),
    link_type: Optional[str] = typer.Option(None, "--type", "-t", help="junction (Windows) or symlink."),
    migrate: bool = typer.Option(False, "--migrate", "-m", help="Move existing directory to external."),
) -> None:
    """Create junction/symlink from repo path to external directory."""
    root = _root()
    try:
        entry = link_mod.add_link(root, path, external, link_type=resolve_link_type(link_type), migrate=migrate)
    except (FileExistsError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Link created[/green] {entry.repo_path} -> {entry.external_path} ({entry.link_type})")


@link_app.command("list")
def link_list() -> None:
    """List configured links."""
    _print_link_table(link_mod.list_links(_root()))


@link_app.command("remove")
def link_remove(
    path: str = typer.Argument(..., help="Repo-relative linked path."),
    delete_external: bool = typer.Option(False, "--delete-external", help="Also delete external data."),
) -> None:
    """Remove a link (keeps external data by default)."""
    root = _root()
    try:
        link_mod.remove_link(root, path, keep_external=not delete_external)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Link removed[/green] for {path}")


@link_app.command("set-base")
def link_set_base(
    base: str = typer.Argument(..., help="External base directory for default link targets."),
) -> None:
    """Set default external base directory in config."""
    resolved = link_mod.set_external_base(_root(), base)
    console.print(f"[green]External base set[/green] to {resolved}")


@worktree_app.command("add")
def worktree_add(
    name: str = typer.Argument(..., help="Logical name for this worktree."),
    path: str = typer.Argument(..., help="Absolute path for the worktree directory."),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to checkout."),
    new_branch: bool = typer.Option(False, "--new-branch", "-n", help="Create a new branch."),
) -> None:
    """Add a personal git worktree."""
    root = _root()
    try:
        status = worktree_mod.add_worktree(root, name, path, branch=branch, create_branch=new_branch)
    except git.GitError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Worktree added[/green] {status.name} at {status.path}")


@worktree_app.command("list")
def worktree_list() -> None:
    """List configured worktrees."""
    _print_worktree_table(worktree_mod.list_worktrees(_root()))


@worktree_app.command("remove")
def worktree_remove(
    name: str = typer.Argument(..., help="Worktree name."),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal."),
) -> None:
    """Remove a worktree."""
    root = _root()
    try:
        worktree_mod.remove_worktree(root, name, force=force)
    except (KeyError, git.GitError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Worktree removed[/green] {name}")


@config_app.command("export")
def config_export_cmd(
    output: Path = typer.Argument(..., help="Destination TOML file."),
) -> None:
    """Export current repository configuration to a TOML file."""
    root = _root()
    cfg_path = config_path_for_repo(root)
    if not cfg_path.exists():
        console.print("[yellow]No config found.[/yellow] Run: gitmove init")
        raise typer.Exit(1)
    from gitmove.config import GitMoveConfig

    cfg = GitMoveConfig.load(cfg_path)
    export_config(cfg, output)
    console.print(f"[green]Exported[/green] {len(cfg.skip_paths)} skip path(s) to {output}")


@config_app.command("import")
def config_import_cmd(
    source: Optional[Path] = typer.Argument(
        None,
        help="TOML file to import. Omit when using --from-repo.",
    ),
    from_repo: Optional[Path] = typer.Option(
        None,
        "--from-repo",
        help="Import from another clone's .git/gitmove.toml.",
    ),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with or replace current config."),
    base_override: Optional[str] = typer.Option(
        None,
        "--base-override",
        help="Set external base and expand ${EXTERNAL_BASE} in imported paths.",
    ),
    apply_after: bool = typer.Option(False, "--apply", help="Apply skip/links/worktrees after import."),
) -> None:
    """Import configuration from a TOML file or another repository."""
    root = _root()
    if from_repo is None and source is None:
        console.print("[red]Provide a TOML file path or --from-repo.[/red]")
        raise typer.Exit(1)
    if from_repo is not None and source is not None:
        console.print("[red]Use either a TOML file or --from-repo, not both.[/red]")
        raise typer.Exit(1)

    try:
        if from_repo is not None:
            result = import_config_from_repo(
                root,
                from_repo,
                merge=merge,
                base_override=base_override,
            )
            console.print(f"[green]Imported[/green] from {from_repo.resolve() / '.git' / 'gitmove.toml'}")
        else:
            assert source is not None
            result = import_config(
                root,
                source,
                merge=merge,
                base_override=base_override,
            )
            console.print(f"[green]Imported[/green] from {source}")
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(
        f"  skip: {len(result.skip_paths)}  links: {len(result.links)}  worktrees: {len(result.worktrees)}"
    )
    if apply_after:
        apply_all_report(root)
        console.print("[green]Applied[/green] imported configuration")


@sync_app.command("check")
def sync_check_cmd(
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch from remote before checking."),
) -> None:
    """List skip-worktree paths with local or remote changes."""
    root = _root()
    if not config_path_for_repo(root).exists():
        console.print("[yellow]No config found.[/yellow] Run: gitmove init")
        raise typer.Exit(1)

    report = check_sync(root, fetch=fetch)
    if report.upstream is None:
        console.print("[yellow]No upstream branch configured.[/yellow]")
        raise typer.Exit(1)

    console.print(f"Upstream: {report.upstream}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Path")
    table.add_column("Local changed")
    table.add_column("Remote changed")
    table.add_column("Skip active")
    for drift in report.drifts:
        if not drift.in_config and not drift.skip_active:
            continue
        table.add_row(
            drift.path,
            "yes" if drift.local_modified else "no",
            "yes" if drift.remote_modified else "no",
            "yes" if drift.skip_active else "no",
        )
    console.print(table)

    attention = report.attention_items
    if attention:
        console.print(f"\n[yellow]{len(attention)} path(s) need attention before pull.[/yellow]")
    else:
        console.print("\n[green]No skip-worktree remote drift detected.[/green]")


@sync_app.command("pull")
def sync_pull_cmd(
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch before sync."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show planned actions without pulling."),
) -> None:
    """Pull remote changes and interactively reconcile skip-worktree paths."""
    root = _root()
    try:
        result = sync_pull(root, fetch=fetch, chooser=default_chooser, dry_run=dry_run)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except git.GitError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[yellow]Dry run — no changes made.[/yellow]")
        return

    if result.skipped:
        console.print(f"[yellow]Skipped[/yellow]: {', '.join(result.skipped)}")
    if result.reapplied:
        console.print(f"[green]Reapplied skip[/green]: {', '.join(result.reapplied)}")
    for error in result.errors:
        console.print(f"[red]Conflict/error[/red]: {error}")
    if result.pulled and not result.errors:
        console.print("[green]Sync pull complete.[/green]")
    elif result.errors:
        raise typer.Exit(1)


def _project_entries_for_batch(all_projects: bool, group: str | None) -> list[ProjectEntry]:
    if all_projects:
        return iter_projects(group=group)
    root = _root()
    for entry in list_projects():
        if entry.path == root.resolve():
            return [entry]
    return [
        ProjectEntry(
            path=root.resolve(),
            alias=root.name,
        )
    ]


def _print_batch_doctor_table(rows: list[projects_mod.ProjectBatchRow]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias")
    table.add_column("Path")
    table.add_column("Status")
    table.add_column("Errors")
    table.add_column("Warns")
    for row in rows:
        table.add_row(
            row.alias,
            str(row.path),
            row.status,
            str(row.error_count),
            str(row.warn_count),
        )
    console.print(table)


@projects_app.command("list")
def projects_list_cmd(
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group."),
) -> None:
    """List registered projects."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias")
    table.add_column("Path")
    table.add_column("Group")
    table.add_column("Init")
    table.add_column("Status")
    for entry in list_projects(group=group):
        status = project_status(entry.path)
        initialized = "yes" if config_path_for_repo(entry.path).exists() else "no"
        table.add_row(
            entry.alias,
            str(entry.path),
            entry.group or "—",
            initialized,
            status,
        )
    console.print(table)


@projects_app.command("add")
def projects_add_cmd(
    path: Optional[Path] = typer.Argument(None, help="Repository path (default: cwd)."),
    alias: Optional[str] = typer.Option(None, "--alias", "-a", help="Unique short name."),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Optional group label."),
) -> None:
    """Register a Git repository in ~/.gitmove/projects.toml."""
    target = path or Path.cwd()
    try:
        entry = add_project(target, alias=alias, group=group)
    except RegistryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Registered[/green] {entry.alias} -> {entry.path}")


@projects_app.command("remove")
def projects_remove_cmd(
    alias_or_path: str = typer.Argument(..., help="Registered alias or absolute path."),
) -> None:
    """Remove a project from the registry (does not delete .git/gitmove.toml)."""
    try:
        remove_project(alias_or_path)
    except RegistryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Removed[/green] {alias_or_path}")


@projects_app.command("set-default")
def projects_set_default_cmd(
    alias: str = typer.Argument(..., help="Registered alias."),
) -> None:
    """Set the default project for commands without -C."""
    try:
        set_default(alias)
    except RegistryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Default project[/green] set to {alias}")


@projects_app.command("doctor")
def projects_doctor_cmd(
    all_projects: bool = typer.Option(False, "--all", help="Run doctor for all registered projects."),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group when using --all."),
) -> None:
    """Run health checks for one or all registered projects."""
    entries = _project_entries_for_batch(all_projects, group)
    rows = projects_mod.batch_doctor(entries)
    _print_batch_doctor_table(rows)
    if projects_mod.batch_exit_code(rows):
        raise typer.Exit(1)


@projects_app.command("apply")
def projects_apply_cmd(
    all_projects: bool = typer.Option(False, "--all", help="Apply config for all registered projects."),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group when using --all."),
) -> None:
    """Apply skip/link/worktree for one or all registered projects."""
    entries = _project_entries_for_batch(all_projects, group)
    rows = projects_mod.batch_apply(entries)
    _print_batch_doctor_table(rows)
    if projects_mod.batch_exit_code(rows):
        raise typer.Exit(1)


@projects_sync_app.command("check")
def projects_sync_check_cmd(
    all_projects: bool = typer.Option(False, "--all", help="Check all registered projects."),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group when using --all."),
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch from remote before checking."),
) -> None:
    """Report skip-worktree drift for one or all registered projects."""
    entries = _project_entries_for_batch(all_projects, group)
    summaries = projects_mod.batch_sync_check(entries, fetch=fetch)
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias")
    table.add_column("Status")
    table.add_column("Upstream")
    table.add_column("Attention")
    table.add_column("Message")
    for item in summaries:
        table.add_row(
            item.alias,
            item.status,
            item.upstream or "—",
            str(item.attention_count),
            item.message or "—",
        )
    console.print(table)


@projects_sync_app.command("pull")
def projects_sync_pull_cmd(
    all_projects: bool = typer.Option(False, "--all", help="Interactive sync for all registered projects."),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group when using --all."),
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch before sync."),
) -> None:
    """Pull and reconcile skip-worktree paths for one or all registered projects."""
    entries = _project_entries_for_batch(all_projects, group)
    project_chooser = default_project_chooser if all_projects else None
    results = projects_mod.batch_sync_pull(
        entries,
        fetch=fetch,
        project_chooser=project_chooser,
        file_chooser=default_chooser,
    )
    had_errors = False
    for item in results:
        if item.message and item.status != "OK":
            console.print(f"[yellow]{item.alias}[/yellow]: {item.message}")
        elif item.message and item.status == "OK" and not item.skipped_project:
            console.print(f"[red]{item.alias}[/red]: {item.message}")
            had_errors = True
        if item.skipped_project:
            console.print(f"[yellow]Skipped project[/yellow] {item.alias}")
        if item.report and item.report.errors:
            had_errors = True
            for error in item.report.errors:
                console.print(f"[red]{item.alias}[/red]: {error}")
        elif item.report and item.report.pulled:
            console.print(f"[green]Synced[/green] {item.alias}")
    if had_errors:
        raise typer.Exit(1)


@vendor_app.command("add")
def vendor_add_cmd(
    repo_path: str = typer.Argument(..., help="Mount path inside the business repository."),
    source_url: str = typer.Option(..., "--from", help="Upstream Git clone URL."),
    name: Optional[str] = typer.Option(None, "--name", help="Vendor name (TOML key)."),
    source_ref: str = typer.Option("main", "--ref", help="Upstream branch/tag."),
    cache: Optional[str] = typer.Option(None, "--cache", help="Local cache directory."),
    link_type: Optional[str] = typer.Option(None, "--type", "-t", help="junction or symlink."),
    migrate: bool = typer.Option(False, "--migrate", "-m", help="Move existing directory into cache."),
) -> None:
    """Add an upstream vendor (clone cache + whole-repo link)."""
    root = _root()
    try:
        entry = vendor_mod.add_vendor(
            root,
            repo_path,
            source_url=source_url,
            name=name,
            source_ref=source_ref,
            cache_path=cache,
            link_type=resolve_link_type(link_type),
            migrate=migrate,
        )
    except (vendor_mod.VendorError, FileExistsError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(
        f"[green]Vendor added[/green] {entry.name}: {entry.repo_path} -> {entry.cache_path}"
    )


@vendor_app.command("list")
def vendor_list_cmd() -> None:
    """List configured vendors."""
    _print_vendor_table(vendor_mod.list_vendors(_root()))


@vendor_app.command("status")
def vendor_status_cmd(
    name_or_path: Optional[str] = typer.Argument(None, help="Vendor name or repo_path."),
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch before status."),
) -> None:
    """Show vendor cache and link status."""
    root = _root()
    entries = vendor_mod.list_vendors(root)
    targets = entries if name_or_path is None else [e for e in entries if e.name == name_or_path or e.repo_path == name_or_path]
    if name_or_path and not targets:
        console.print(f"[red]Vendor not found: {name_or_path}[/red]")
        raise typer.Exit(1)
    for entry in targets:
        result = vendor_mod.vendor_status(root, entry.name, fetch=fetch)
        console.print(f"{entry.name}: {result.message}")


@vendor_app.command("sync")
def vendor_sync_cmd(
    name_or_path: Optional[str] = typer.Argument(None, help="Vendor name or repo_path."),
    all_vendors: bool = typer.Option(False, "--all", help="Sync all vendors."),
    fetch: bool = typer.Option(True, "--fetch/--no-fetch", help="Fetch before sync."),
) -> None:
    """Fast-forward sync vendor cache from upstream."""
    root = _root()
    had_errors = False
    if all_vendors:
        results = vendor_mod.sync_all_vendors(root, fetch=fetch)
        for item in results:
            if item.ok and item.updated:
                console.print(
                    f"[green]{item.name}[/green] {item.old_commit[:7]} -> {item.new_commit[:7]}"
                )
            elif item.ok:
                console.print(f"[green]{item.name}[/green] already up to date")
            else:
                had_errors = True
                console.print(f"[red]{item.name}[/red] {item.message}")
    else:
        if not name_or_path:
            console.print("[red]Provide vendor name/path or use --all.[/red]")
            raise typer.Exit(1)
        try:
            result = vendor_mod.sync_vendor(root, name_or_path, fetch=fetch)
        except vendor_mod.VendorError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        if result.updated:
            old = (result.old_commit or "")[:7]
            new = (result.new_commit or "")[:7]
            console.print(f"[green]Synced[/green] {old} -> {new}")
        else:
            console.print("[green]Already up to date.[/green]")
    if had_errors:
        raise typer.Exit(1)


@vendor_app.command("remove")
def vendor_remove_cmd(
    name_or_path: str = typer.Argument(..., help="Vendor name or repo_path."),
    purge_cache: bool = typer.Option(False, "--purge-cache", help="Delete cache directory."),
    keep_skip: bool = typer.Option(True, "--keep-skip/--no-keep-skip", help="Keep skip-worktree paths."),
) -> None:
    """Remove a vendor link (and optionally cache / skip entries)."""
    try:
        vendor_mod.remove_vendor(
            _root(),
            name_or_path,
            purge_cache=purge_cache,
            keep_skip=keep_skip,
        )
    except vendor_mod.VendorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Vendor removed[/green] {name_or_path}")


@app.command("gui")
def gui_cmd(
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Git repository path."),
) -> None:
    """Launch the cross-platform visual interface."""
    try:
        from gitmove.gui.app import main as gui_main
    except ImportError as exc:
        console.print("[red]GUI dependencies missing.[/red] Run: pip install gitmove")
        raise typer.Exit(1) from exc
    gui_main(repo_path=repo)


def _print_skip_table(items: list) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Path")
    table.add_column("Tracked")
    table.add_column("Skip active")
    table.add_column("In config")
    if not items:
        table.add_row("—", "—", "—", "—")
    for item in items:
        table.add_row(
            item.path,
            "yes" if item.tracked else "no",
            "yes" if item.skip_active else "no",
            "yes" if item.in_config else "no",
        )
    console.print(table)


def _print_link_table(items: list) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Repo path")
    table.add_column("External")
    table.add_column("Type")
    table.add_column("OK")
    if not items:
        table.add_row("—", "—", "—", "—")
    for item in items:
        ok = "yes" if item.is_link and item.link_ok else ("partial" if item.is_link else "no")
        table.add_row(item.repo_path, item.external_path, item.link_type, ok)
    console.print(table)


def _print_worktree_table(items: list) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Path")
    table.add_column("Branch")
    table.add_column("Registered")
    if not items:
        table.add_row("—", "—", "—", "—")
    for item in items:
        table.add_row(
            item.name,
            item.path,
            item.branch or "—",
            "yes" if item.registered else "no",
        )
    console.print(table)


def _print_vendor_table(items: list) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Repo path")
    table.add_column("URL")
    table.add_column("Ref")
    table.add_column("Link OK")
    if not items:
        table.add_row("—", "—", "—", "—", "—")
    for item in items:
        table.add_row(
            item.name,
            item.repo_path,
            item.source_url,
            item.source_ref,
            "yes" if item.link_ok else "no",
        )
    console.print(table)


app.add_typer(skip_app, name="skip")
app.add_typer(link_app, name="link")
app.add_typer(worktree_app, name="worktree")
app.add_typer(config_app, name="config")
app.add_typer(sync_app, name="sync")
projects_app.add_typer(projects_sync_app, name="sync")
app.add_typer(projects_app, name="projects")
app.add_typer(vendor_app, name="vendor")


if __name__ == "__main__":
    app()
