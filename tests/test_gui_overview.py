"""Unit tests for GUI overview formatting (T-G3)."""

from __future__ import annotations

from gitmove.doctor import DoctorIssue, DoctorReport
from gitmove.gui.overview import doctor_rows_for_tree, format_doctor_summary


def test_format_doctor_summary_counts() -> None:
    report = DoctorReport(
        issues=[
            DoctorIssue("error", "link", "链接缺失"),
            DoctorIssue("warn", "vendor", "pin drift"),
            DoctorIssue("info", "general", "ok"),
        ]
    )
    summary = format_doctor_summary(report)
    assert "1" in summary and "错误" in summary
    assert "警告" in summary


def test_doctor_rows_sorted_errors_first() -> None:
    report = DoctorReport(
        issues=[
            DoctorIssue("info", "general", "提示"),
            DoctorIssue("error", "skip", "未生效"),
            DoctorIssue("warn", "link", "不一致"),
        ]
    )
    rows = doctor_rows_for_tree(report)
    assert rows[0].level == "error"
    assert rows[1].level == "warn"
    assert rows[2].level == "info"


def test_doctor_rows_include_category_and_message() -> None:
    report = DoctorReport(issues=[DoctorIssue("error", "vendor", "cache 缺失")])
    rows = doctor_rows_for_tree(report)
    assert len(rows) == 1
    assert rows[0].category == "vendor"
    assert "cache" in rows[0].message
