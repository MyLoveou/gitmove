"""Overview tab formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass

from gitmove.doctor import DoctorReport

_LEVEL_ORDER = {"error": 0, "warn": 1, "info": 2}
_LEVEL_LABEL = {"error": "ERR", "warn": "WARN", "info": "INFO"}


@dataclass(frozen=True)
class OverviewRow:
    level: str
    level_label: str
    category: str
    message: str


def format_doctor_summary(report: DoctorReport) -> str:
    errors, warns, infos = doctor_counts(report)
    return f"{errors} 错误   {warns} 警告   {infos} 提示"


def doctor_counts(report: DoctorReport) -> tuple[int, int, int]:
    errors = report.error_count
    warns = report.warn_count
    infos = sum(1 for issue in report.issues if issue.level == "info")
    return errors, warns, infos


def doctor_rows_for_tree(report: DoctorReport) -> list[OverviewRow]:
    rows = [
        OverviewRow(
            level=issue.level,
            level_label=_LEVEL_LABEL.get(issue.level, issue.level.upper()),
            category=issue.category,
            message=issue.message,
        )
        for issue in report.issues
    ]
    return sorted(rows, key=lambda row: (_LEVEL_ORDER.get(row.level, 9), row.category, row.message))
