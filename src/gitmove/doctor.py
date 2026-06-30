"""Health check and aggregated apply results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gitmove.config import config_path_for_repo
from gitmove import link as link_mod
from gitmove import skip as skip_mod
from gitmove import vendor as vendor_mod
from gitmove import worktree as worktree_mod


from gitmove.errors import RemediationStep, remediation_for_doctor


@dataclass
class DoctorIssue:
    level: str  # error | warn | info
    category: str
    message: str
    code: str | None = None
    remediation: list[RemediationStep] | None = None


@dataclass
class DoctorReport:
    issues: list[DoctorIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warn")

    @property
    def ok(self) -> bool:
        return self.error_count == 0


@dataclass
class ApplyReport:
    skip: list[skip_mod.SkipStatus]
    links: list[link_mod.LinkStatus]
    worktrees: list[worktree_mod.WorktreeStatus]
    vendors: list[vendor_mod.VendorStatus]


def run_doctor(
    root: Path,
    *,
    skip_items: list[skip_mod.SkipStatus] | None = None,
    link_items: list[link_mod.LinkStatus] | None = None,
    wt_items: list[worktree_mod.WorktreeStatus] | None = None,
) -> DoctorReport:
    report = DoctorReport()
    cfg_path = config_path_for_repo(root)
    if not cfg_path.exists():
        code, steps = remediation_for_doctor("config", "尚未初始化，请先执行 init")
        report.issues.append(
            DoctorIssue("info", "config", "尚未初始化，请先执行 init", code=code, remediation=steps)
        )
        return report

    def _issue(level: str, category: str, message: str) -> DoctorIssue:
        code, steps = remediation_for_doctor(category, message)
        return DoctorIssue(level, category, message, code=code, remediation=steps or None)

    for item in skip_items if skip_items is not None else skip_mod.list_status(root):
        if item.in_config and item.tracked and not item.skip_active:
            report.issues.append(
                _issue("error", "skip", f"skip-worktree 未生效: {item.path}")
            )
        if item.in_config and not (root / item.path).exists():
            report.issues.append(
                DoctorIssue("warn", "skip", f"配置路径不存在: {item.path}")
            )

    for item in link_items if link_items is not None else link_mod.list_links(root):
        if not item.repo_exists:
            report.issues.append(
                _issue("error", "link", f"仓库内链接缺失: {item.repo_path}")
            )
        elif item.is_link and not item.link_ok:
            report.issues.append(
                DoctorIssue("warn", "link", f"链接目标不一致: {item.repo_path}")
            )
        elif not item.is_link and item.repo_exists:
            report.issues.append(
                DoctorIssue("warn", "link", f"路径存在但不是链接: {item.repo_path}")
            )

    for item in wt_items if wt_items is not None else worktree_mod.list_worktrees(root):
        if not item.registered:
            report.issues.append(
                DoctorIssue(
                    "error",
                    "worktree",
                    f"worktree 未注册: {item.name} ({item.path})",
                )
            )

    for level, category, message in vendor_mod.check_vendors_for_doctor(root, fetch_behind=True):
        code, steps = remediation_for_doctor(category, message)
        report.issues.append(DoctorIssue(level, category, message, code=code, remediation=steps or None))

    if not report.issues:
        report.issues.append(DoctorIssue("info", "general", "所有检查通过"))
    return report


def apply_all(root: Path) -> ApplyReport:
    return ApplyReport(
        skip=skip_mod.apply_all(root),
        links=link_mod.apply_links(root),
        worktrees=worktree_mod.apply_worktrees(root),
        vendors=vendor_mod.apply_vendors(root),
    )


def init_repo(root: Path, external_base: str | None = None) -> Path:
    from gitmove.config import resolve_external_base

    cfg = skip_mod.load_config(root)
    if external_base:
        cfg.external_base = external_base
    skip_mod.save_config(root, cfg)
    return resolve_external_base(cfg, root)
