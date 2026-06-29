"""gitmove CLI — local Git exclusions without .gitignore changes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from gitmove import __version__, git
from gitmove.config import config_path_for_repo, resolve_external_base
from gitmove import link as link_mod
from gitmove import skip as skip_mod
from gitmove import worktree as worktree_mod

app = typer.Typer(
    name="gitmove",
    help="Manage local-only Git exclusions: skip-worktree, external links, personal worktrees.",
    no_args_is_help=True,
)
skip_app = typer.Typer(help="skip-worktree: hide local changes to tracked files.")
link_app = typer.Typer(help="Link repo paths to external directories (junction/symlink).")
worktree_app = typer.Typer(help="Personal git worktree management.")
console = Console()


def _root() -> Path:
    try:
        return git.repo_root()
    except git.GitError as exc:
        console.print(f"[red]Not a git repository.[/red] {exc}")
        raise typer.Exit(1) from exc


@app.callback()
def main(
    version: Optional[bool] = typer.Option(None, "--version", "-V", help="Show version."),
) -> None:
    if version:
        console.print(f"gitmove {__version__}")
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
    cfg = skip_mod.load_config(root)

    if external_base:
        cfg.external_base = external_base
    skip_mod.save_config(root, cfg)

    console.print(f"[green]Initialized[/green] {cfg_path}")
    console.print(f"External base: {resolve_external_base(cfg, root)}")
    console.print("\nNext steps:")
    console.print("  gitmove skip add <path>       # mark tracked file as local-only")
    console.print("  gitmove link add <path>         # junction to external directory")
    console.print("  gitmove apply                   # restore all settings after clone")


@app.command("apply")
def apply_cmd() -> None:
    """Apply skip-worktree, links, and worktrees from config (run after clone)."""
    root = _root()
    skip_results = skip_mod.apply_all(root)
    link_results = link_mod.apply_links(root)
    wt_results = worktree_mod.apply_worktrees(root)

    console.print("[bold]skip-worktree[/bold]")
    _print_skip_table(skip_results)

    console.print("\n[bold]links[/bold]")
    _print_link_table(link_results)

    console.print("\n[bold]worktrees[/bold]")
    _print_worktree_table(wt_results)


@app.command("doctor")
def doctor_cmd() -> None:
    """Check configuration vs actual git state."""
    root = _root()
    cfg_path = config_path_for_repo(root)
    if not cfg_path.exists():
        console.print("[yellow]No config found.[/yellow] Run: gitmove init")
        raise typer.Exit(1)

    issues = 0
    for item in skip_mod.list_status(root):
        if item.in_config and item.tracked and not item.skip_active:
            console.print(f"[red]MISS[/red] skip-worktree not active: {item.path}")
            issues += 1
        if item.in_config and not (root / item.path).exists():
            console.print(f"[yellow]WARN[/yellow] configured path missing: {item.path}")

    for item in link_mod.list_links(root):
        if not item.repo_exists:
            console.print(f"[red]MISS[/red] link missing in repo: {item.repo_path}")
            issues += 1
        elif item.is_link and not item.link_ok:
            console.print(f"[yellow]WARN[/yellow] link target mismatch: {item.repo_path}")
        elif not item.is_link and item.repo_exists:
            console.print(f"[yellow]WARN[/yellow] path exists but is not a link: {item.repo_path}")

    for item in worktree_mod.list_worktrees(root):
        if not item.registered:
            console.print(f"[red]MISS[/red] worktree not registered: {item.name} ({item.path})")
            issues += 1

    if issues == 0:
        console.print("[green]All checks passed.[/green]")
    else:
        console.print(f"\n[yellow]{issues} issue(s)[/yellow]. Run: gitmove apply")
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
    link_type: str = typer.Option("junction", "--type", "-t", help="junction or symlink."),
    migrate: bool = typer.Option(False, "--migrate", "-m", help="Move existing directory to external."),
) -> None:
    """Create junction/symlink from repo path to external directory."""
    root = _root()
    try:
        entry = link_mod.add_link(root, path, external, link_type=link_type, migrate=migrate)
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


app.add_typer(skip_app, name="skip")
app.add_typer(link_app, name="link")
app.add_typer(worktree_app, name="worktree")


if __name__ == "__main__":
    app()
