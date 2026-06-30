"""Remote sync helpers for skip-worktree paths."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from gitmove import git
from gitmove.config import config_path_for_repo
from gitmove.doctor import apply_all
from gitmove import skip as skip_mod

StrategyChooser = Callable[["SyncDrift"], "SyncStrategy | None"]


class SyncStrategy(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"
    MERGE = "merge"
    SKIP = "skip"


@dataclass
class SyncDrift:
    path: str
    local_modified: bool
    remote_modified: bool
    skip_active: bool
    in_config: bool

    @property
    def needs_attention(self) -> bool:
        return self.remote_modified and self.skip_active

    @property
    def needs_choice(self) -> bool:
        return self.needs_attention and self.local_modified


@dataclass
class SyncCheckReport:
    upstream: str | None
    drifts: list[SyncDrift]

    @property
    def attention_items(self) -> list[SyncDrift]:
        return [item for item in self.drifts if item.needs_attention]

    @property
    def choice_items(self) -> list[SyncDrift]:
        return [item for item in self.drifts if item.needs_choice]


@dataclass
class SyncPullReport:
    pulled: bool
    reapplied: list[str]
    skipped: list[str]
    errors: list[str]


def upstream_ref(root: Path) -> str | None:
    result = git.run_git(
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return None
    ref = result.stdout.strip()
    return ref or None


def _file_at_rev(root: Path, rev: str, path: str) -> str | None:
    result = git.run_git("show", f"{rev}:{path}", cwd=root, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def is_local_modified(root: Path, path: str) -> bool:
    full = root / path
    if not full.is_file():
        return False
    head_content = _file_at_rev(root, "HEAD", path)
    if head_content is None:
        return False
    local_content = full.read_text(encoding="utf-8", errors="replace")
    return local_content != head_content


def is_remote_modified(root: Path, path: str, upstream: str) -> bool:
    head_content = _file_at_rev(root, "HEAD", path)
    remote_content = _file_at_rev(root, upstream, path)
    if remote_content is None and head_content is None:
        return False
    return head_content != remote_content


def check_sync(root: Path, *, fetch: bool = False) -> SyncCheckReport:
    if fetch:
        git.run_git("fetch", cwd=root)

    upstream = upstream_ref(root)
    cfg = skip_mod.load_config(root)
    skip_active, _ = git.ls_files_index(root)
    paths = sorted(set(cfg.skip_paths) | skip_active)

    drifts: list[SyncDrift] = []
    for path in paths:
        remote_modified = bool(upstream and is_remote_modified(root, path, upstream))
        drifts.append(
            SyncDrift(
                path=path,
                local_modified=is_local_modified(root, path),
                remote_modified=remote_modified,
                skip_active=path in skip_active,
                in_config=path in cfg.skip_paths,
            )
        )
    return SyncCheckReport(upstream=upstream, drifts=drifts)


def _unskip_path(root: Path, path: str) -> None:
    skip_mod.remove_skip(root, path, persist=False)


def _read_worktree_text(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8", errors="replace")


def _write_worktree_text(root: Path, path: str, content: str) -> None:
    (root / path).write_text(content, encoding="utf-8")


def _preserve_local_for_pull(root: Path, path: str) -> str | None:
    if not is_local_modified(root, path):
        _unskip_path(root, path)
        _restore_head_worktree(root, path)
        return None
    content = _read_worktree_text(root, path)
    _unskip_path(root, path)
    _restore_head_worktree(root, path)
    return content


def _restore_preserved_local(root: Path, path: str, content: str) -> None:
    _write_worktree_text(root, path, content)
    git.run_git("add", path, cwd=root, check=False)
    _restash_skip_path(root, path)


def _stash_path(root: Path, path: str, message: str) -> None:
    git.run_git("stash", "push", "-m", message, "--", path, cwd=root)


def _restore_head_worktree(root: Path, path: str) -> None:
    git.run_git("restore", "--source=HEAD", "--worktree", "--staged", path, cwd=root, check=False)


def _apply_pre_pull_strategy(root: Path, path: str, strategy: SyncStrategy) -> None:
    _unskip_path(root, path)
    if strategy == SyncStrategy.REMOTE:
        _restore_head_worktree(root, path)
    elif strategy in {SyncStrategy.LOCAL, SyncStrategy.MERGE}:
        if is_local_modified(root, path):
            _stash_path(root, path, f"gitmove-sync:{path}")


def _restash_skip_path(root: Path, path: str) -> None:
    if git.is_tracked(root, path):
        git.update_index_skip(root, path, skip=True)


def _apply_post_pull_strategy(root: Path, path: str, strategy: SyncStrategy) -> str | None:
    if strategy == SyncStrategy.REMOTE:
        _restash_skip_path(root, path)
        return None

    if strategy in {SyncStrategy.LOCAL, SyncStrategy.MERGE}:
        pop = git.run_git("stash", "pop", cwd=root, check=False)
        if pop.returncode != 0:
            return pop.stderr.strip() or pop.stdout.strip() or f"stash pop failed for {path}"
        _restash_skip_path(root, path)
    return None


def sync_pull(
    root: Path,
    *,
    fetch: bool = True,
    chooser: StrategyChooser | None = None,
    dry_run: bool = False,
) -> SyncPullReport:
    if not config_path_for_repo(root).exists():
        raise FileNotFoundError("gitmove is not initialized; run: gitmove init")

    report = check_sync(root, fetch=fetch)
    if report.upstream is None:
        raise git.GitError("No upstream branch configured for current branch")

    actions: dict[str, SyncStrategy] = {}
    skipped: list[str] = []
    errors: list[str] = []

    for drift in report.attention_items:
        strategy = chooser(drift) if chooser else default_chooser(drift)
        if strategy is None or strategy == SyncStrategy.SKIP:
            skipped.append(drift.path)
            continue
        if not drift.local_modified and strategy in {SyncStrategy.LOCAL, SyncStrategy.MERGE}:
            strategy = SyncStrategy.REMOTE
        actions[drift.path] = strategy

    if dry_run:
        return SyncPullReport(pulled=False, reapplied=[], skipped=skipped, errors=[])

    deferred_local: dict[str, str] = {}
    for path in skipped:
        drift = next(item for item in report.attention_items if item.path == path)
        preserved = _preserve_local_for_pull(root, path)
        if preserved is not None:
            deferred_local[path] = preserved

    pre_stash: list[tuple[str, SyncStrategy]] = []
    for path, strategy in actions.items():
        if strategy in {SyncStrategy.LOCAL, SyncStrategy.MERGE} and is_local_modified(root, path):
            pre_stash.append((path, strategy))
        _apply_pre_pull_strategy(root, path, strategy)

    pull = git.run_git("pull", "--ff-only", cwd=root, check=False)
    if pull.returncode != 0:
        for path, strategy in reversed(pre_stash):
            git.run_git("stash", "pop", cwd=root, check=False)
            _restash_skip_path(root, path)
        raise git.GitError(pull.stderr.strip() or pull.stdout.strip() or "git pull failed")

    reapplied: list[str] = []
    for path, strategy in actions.items():
        if strategy in {SyncStrategy.LOCAL, SyncStrategy.MERGE}:
            continue
        error = _apply_post_pull_strategy(root, path, strategy)
        if error:
            errors.append(error)
        else:
            reapplied.append(path)

    for path, strategy in reversed(pre_stash):
        error = _apply_post_pull_strategy(root, path, strategy)
        if error:
            errors.append(error)
        else:
            reapplied.append(path)

    for path, content in deferred_local.items():
        _restore_preserved_local(root, path, content)

    for drift in report.drifts:
        if drift.in_config and drift.path not in actions and drift.path not in skipped:
            if git.is_tracked(root, drift.path):
                git.update_index_skip(root, drift.path, skip=True)

    apply_all(root)
    return SyncPullReport(pulled=True, reapplied=reapplied, skipped=skipped, errors=errors)


def default_chooser(drift: SyncDrift) -> SyncStrategy | None:
    local = "是" if drift.local_modified else "否"
    remote = "是" if drift.remote_modified else "否"
    print(f"\n{drift.path}  本地已改: {local}  远程有更新: {remote}")
    if drift.local_modified:
        print("  [l] 保留本地  [r] 采用远程  [m] 合并 (stash→pull→pop)  [s] 跳过")
    else:
        print("  [r] 采用远程  [s] 跳过（保持当前本地内容）")
    while True:
        choice = input("选择: ").strip().lower()
        if drift.local_modified and choice in {"l", "local"}:
            return SyncStrategy.LOCAL
        if choice in {"r", "remote"}:
            return SyncStrategy.REMOTE
        if drift.local_modified and choice in {"m", "merge"}:
            return SyncStrategy.MERGE
        if choice in {"s", "skip"}:
            return SyncStrategy.SKIP
        print("无效输入，请重新选择")
