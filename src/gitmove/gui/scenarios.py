"""Scenario cards for the GUI「开始」tab."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioCard:
    id: str
    index: str
    title: str
    subtitle: str
    tag: str
    target_tab: str


SCENARIO_CARDS: tuple[ScenarioCard, ...] = (
    ScenarioCard(
        id="skip_tracked",
        index="01",
        title="本地改已追踪文件",
        subtitle="不想提交到远程的小文件",
        tag="Skip-worktree",
        target_tab="Skip-worktree",
    ),
    ScenarioCard(
        id="link_external",
        index="02",
        title="目录放盘外",
        subtitle="未追踪目录放到仓库外",
        tag="外部链接",
        target_tab="外部链接",
    ),
    ScenarioCard(
        id="vendor_upstream",
        index="03",
        title="上游 Git 仓库",
        subtitle="如 .cursor 规范仓",
        tag="Vendor",
        target_tab="Vendor",
    ),
    ScenarioCard(
        id="profile_switch",
        index="04",
        title="公司 / 个人切换",
        subtitle="Profile 切换策略（含 reconcile）",
        tag="Profile",
        target_tab="Profile",
    ),
    ScenarioCard(
        id="sync_reconcile",
        index="05",
        title="远程也改了 skip 文件",
        subtitle="检查并 pull reconcile",
        tag="同步",
        target_tab="同步",
    ),
    ScenarioCard(
        id="worktree_parallel",
        index="06",
        title="多分支并行",
        subtitle="个人 worktree 实验",
        tag="Worktree",
        target_tab="Worktree",
    ),
)


def scenario_ids() -> list[str]:
    return [card.id for card in SCENARIO_CARDS]


def get_scenario(scenario_id: str) -> ScenarioCard | None:
    for card in SCENARIO_CARDS:
        if card.id == scenario_id:
            return card
    return None
