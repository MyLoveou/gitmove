"""Configuration stored inside .git/gitmove.toml (never committed)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

CONFIG_FILENAME = "gitmove.toml"


@dataclass
class LinkEntry:
    repo_path: str
    external_path: str
    link_type: str = "junction"  # junction | symlink


@dataclass
class WorktreeEntry:
    name: str
    path: str
    branch: str | None = None


@dataclass
class GitMoveConfig:
    skip_paths: list[str] = field(default_factory=list)
    external_base: str | None = None
    links: list[LinkEntry] = field(default_factory=list)
    worktrees: list[WorktreeEntry] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> GitMoveConfig:
        if not path.exists():
            return cls()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        cfg = cls()

        skip = data.get("skip-worktree", {})
        if isinstance(skip.get("paths"), list):
            cfg.skip_paths = [normalize_rel(p) for p in skip["paths"]]

        external = data.get("external", {})
        if isinstance(external.get("base"), str):
            cfg.external_base = external["base"]

        links = data.get("links", {})
        if isinstance(links, dict):
            for repo_path, value in links.items():
                if isinstance(value, str):
                    cfg.links.append(LinkEntry(normalize_rel(repo_path), value))
                elif isinstance(value, dict):
                    cfg.links.append(
                        LinkEntry(
                            normalize_rel(repo_path),
                            value.get("path", ""),
                            value.get("type", "junction"),
                        )
                    )

        worktrees = data.get("worktrees", {})
        if isinstance(worktrees, dict):
            for name, value in worktrees.items():
                if isinstance(value, str):
                    cfg.worktrees.append(WorktreeEntry(name=name, path=value))
                elif isinstance(value, dict):
                    cfg.worktrees.append(
                        WorktreeEntry(
                            name=name,
                            path=value.get("path", ""),
                            branch=value.get("branch"),
                        )
                    )
        return cfg

    def save(self, path: Path) -> None:
        payload: dict = {
            "skip-worktree": {"paths": self.skip_paths},
            "external": {"base": self.external_base or ""},
            "links": {
                link.repo_path: {
                    "path": link.external_path,
                    "type": link.link_type,
                }
                for link in self.links
            },
            "worktrees": {
                wt.name: {
                    "path": wt.path,
                    "branch": wt.branch or "",
                }
                for wt in self.worktrees
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(payload), encoding="utf-8")


def config_path_for_repo(root: Path) -> Path:
    return root / ".git" / CONFIG_FILENAME


def normalize_rel(path: str) -> str:
    cleaned = path.replace("\\", "/").strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def resolve_repo_path(root: Path, rel_path: str) -> Path:
    """Resolve a repo-relative path and ensure it stays inside the repository."""
    normalized = normalize_rel(rel_path)
    if not normalized:
        raise ValueError("Path must not be empty")
    if Path(normalized).is_absolute() or ".." in Path(normalized).parts:
        raise ValueError(f"Path must stay inside repository: {rel_path}")

    repo = root.resolve()
    full = repo / normalized
    try:
        full.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository: {rel_path}") from exc
    return full


def resolve_external_base(cfg: GitMoveConfig, root: Path) -> Path:
    if cfg.external_base:
        base = Path(cfg.external_base).expanduser()
        if not base.is_absolute():
            base = (root / base).resolve()
        return base
    return (Path.home() / "gitmove-external" / root.name).resolve()
