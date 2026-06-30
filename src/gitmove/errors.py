"""Structured errors with remediation steps for CLI and GUI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel


@dataclass
class RemediationStep:
    title: str
    detail: str = ""
    command: str | None = None
    gui_action: str | None = None  # apply | open_cache | repair | init


@dataclass
class GitMoveError(Exception):
    code: str
    message: str
    cause: str = ""
    steps: list[RemediationStep] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    doc_anchor: str | None = None

    def __str__(self) -> str:
        return self.message


def step(title: str, *, detail: str = "", command: str | None = None, gui_action: str | None = None) -> RemediationStep:
    return RemediationStep(title=title, detail=detail, command=command, gui_action=gui_action)


def _catalog() -> dict[str, GitMoveError]:
    """Template errors (context merged at raise time)."""
    return {
        "REPO_NOT_GIT": GitMoveError(
            code="REPO_NOT_GIT",
            message="所选目录不是 Git 仓库",
            cause="gitmove 需要在 Git 仓库根目录或已注册项目路径上操作。",
            steps=[
                step("选择有效仓库", command="git init  # 新建仓库", gui_action="pick_repo"),
                step("或注册已有仓库", command="gitmove projects add /path/to/repo --alias my-app"),
            ],
            doc_anchor="repo-not-git",
        ),
        "REPO_NOT_INIT": GitMoveError(
            code="REPO_NOT_INIT",
            message="尚未初始化 gitmove 配置",
            cause="当前仓库缺少 .git/gitmove.toml。",
            steps=[step("初始化配置", command="gitmove init", gui_action="init")],
            doc_anchor="quick-start",
        ),
        "REPO_CONTEXT_ALIAS_MISSING": GitMoveError(
            code="REPO_CONTEXT_ALIAS_MISSING",
            message="项目别名未注册",
            cause="projects 注册表中找不到该别名。",
            steps=[
                step("查看已注册项目", command="gitmove projects list"),
                step("添加项目", command="gitmove projects add /path/to/repo --alias <name>"),
            ],
        ),
        "PROJECT_PATH_MISSING": GitMoveError(
            code="PROJECT_PATH_MISSING",
            message="注册的项目路径不存在",
            cause="仓库可能已移动或删除。",
            steps=[
                step("修复路径", command="gitmove projects repair", gui_action="repair"),
                step("或移除后重新添加", command="gitmove projects remove <alias>"),
            ],
        ),
        "PROJECTS_ALIAS_CONFLICT": GitMoveError(
            code="PROJECTS_ALIAS_CONFLICT",
            message="项目别名已存在",
            cause="注册表中已有相同 alias。",
            steps=[step("使用其他别名", command="gitmove projects add . --alias other-name")],
        ),
        "SKIP_NOT_ACTIVE": GitMoveError(
            code="SKIP_NOT_ACTIVE",
            message="skip-worktree 未生效",
            cause="配置中有路径但 Git 索引未标记 skip。",
            steps=[step("应用配置", command="gitmove apply", gui_action="apply")],
        ),
        "LINK_MISSING": GitMoveError(
            code="LINK_MISSING",
            message="外部链接缺失",
            cause="仓库内应存在的 junction/symlink 未创建或已删除。",
            steps=[step("重建链接", command="gitmove apply", gui_action="apply")],
        ),
        "LINK_TARGET_MISMATCH": GitMoveError(
            code="LINK_TARGET_MISMATCH",
            message="链接目标不一致",
            cause="链接存在但指向的路径与配置不符。",
            steps=[
                step("尝试重新应用", command="gitmove apply", gui_action="apply"),
                step("仍失败则移除后重建", command="gitmove link remove <path>"),
            ],
        ),
        "LINK_VENDOR_CONFLICT": GitMoveError(
            code="LINK_VENDOR_CONFLICT",
            message="路径已由 vendor 管理",
            cause="同一 repo_path 不能同时配置 link 与 vendor。",
            steps=[step("查看 vendor", command="gitmove vendor list")],
        ),
        "WORKTREE_NOT_REGISTERED": GitMoveError(
            code="WORKTREE_NOT_REGISTERED",
            message="worktree 未注册",
            cause="配置的 worktree 在 git 中不存在。",
            steps=[step("重新应用", command="gitmove apply", gui_action="apply")],
        ),
        "VENDOR_CACHE_MISSING": GitMoveError(
            code="VENDOR_CACHE_MISSING",
            message="vendor cache 缺失",
            cause="上游 clone 缓存目录不存在。",
            steps=[step("重建 vendor", command="gitmove apply", gui_action="apply")],
        ),
        "VENDOR_CACHE_DIRTY": GitMoveError(
            code="VENDOR_CACHE_DIRTY",
            message="vendor cache 有未提交改动",
            cause="sync 前 cache 工作区须干净。",
            steps=[
                step("进入 cache 查看", command="cd <cache> && git status", gui_action="open_cache"),
                step("提交或丢弃改动后再 sync", command="gitmove vendor sync <name>"),
            ],
        ),
        "VENDOR_FF_BLOCKED": GitMoveError(
            code="VENDOR_FF_BLOCKED",
            message="vendor sync 无法 fast-forward",
            cause="cache 存在非 FF 历史或本地提交。",
            steps=[
                step("检查 cache", command="cd <cache> && git status && git log --oneline -3", gui_action="open_cache"),
                step("若可丢弃本地改动", command="cd <cache> && git reset --hard origin/<ref>"),
                step("重新同步", command="gitmove vendor sync <name>"),
            ],
            doc_anchor="vendor-sync-失败",
        ),
        "VENDOR_CLONE_FAILED": GitMoveError(
            code="VENDOR_CLONE_FAILED",
            message="vendor clone 失败",
            cause="无法从上游 URL clone（网络、URL 或凭据问题）。",
            steps=[
                step("检查 URL 与网络", command="git ls-remote <url>"),
                step("重试 add", command="gitmove vendor add <path> --from <url>"),
            ],
        ),
        "VENDOR_PATH_EXISTS": GitMoveError(
            code="VENDOR_PATH_EXISTS",
            message="挂载路径已存在且非链接",
            cause="需要 --migrate 将现有目录内容迁入 cache。",
            steps=[
                step("迁移并添加", command="gitmove vendor add <path> --from <url> --migrate"),
            ],
        ),
        "VENDOR_LINK_BROKEN": GitMoveError(
            code="VENDOR_LINK_BROKEN",
            message="vendor 链接断裂",
            steps=[step("重建链接", command="gitmove apply", gui_action="apply")],
        ),
        "VENDOR_TRACKED_NOT_SKIP": GitMoveError(
            code="VENDOR_TRACKED_NOT_SKIP",
            message="vendor 追踪路径未 skip",
            steps=[step("应用 skip", command="gitmove apply", gui_action="apply")],
        ),
        "VENDOR_NOT_FOUND": GitMoveError(
            code="VENDOR_NOT_FOUND",
            message="未找到 vendor",
            steps=[step("列出 vendor", command="gitmove vendor list")],
        ),
        "VENDOR_PIN_NOT_FOUND": GitMoveError(
            code="VENDOR_PIN_NOT_FOUND",
            message="vendor pin 在 cache 中不存在",
            steps=[
                step("检查 pin 名称或 SHA", command="gitmove vendor status <name> --fetch"),
                step("更新 pin", command="gitmove vendor add ... --pin <tag|sha>"),
            ],
        ),
        "HOOK_EXISTS": GitMoveError(
            code="HOOK_EXISTS",
            message="Git hook 已存在且非 gitmove 管理",
            steps=[
                step("备份现有 hook 后手动合并", command="mv .git/hooks/post-merge .git/hooks/post-merge.bak"),
                step("重新安装", command="gitmove hooks install"),
            ],
        ),
        "PROFILE_NOT_FOUND": GitMoveError(
            code="PROFILE_NOT_FOUND",
            message="配置 profile 不存在",
            steps=[step("列出 profile", command="gitmove profile list")],
        ),
        "PROFILE_INVALID_NAME": GitMoveError(
            code="PROFILE_INVALID_NAME",
            message="profile 名称无效",
            steps=[step("使用字母数字、下划线或连字符", detail="1-64 字符")],
        ),
        "PROFILE_DRY_RUN_FAILED": GitMoveError(
            code="PROFILE_DRY_RUN_FAILED",
            message="profile 切换预检未通过 doctor",
            steps=[step("查看 doctor 详情", command="gitmove doctor")],
        ),
        "CONFIG_NOT_FOUND": GitMoveError(
            code="CONFIG_NOT_FOUND",
            message="当前仓库无 gitmove 配置",
            steps=[step("初始化", command="gitmove init")],
        ),
        "PROJECTS_UPDATE_FF_FAILED": GitMoveError(
            code="PROJECTS_UPDATE_FF_FAILED",
            message="git pull --ff-only 失败",
            cause="远程存在非 fast-forward 变更，无法自动快进合并。",
            steps=[
                step("进入仓库手动处理", command="cd <repo> && git status && git pull"),
                step("完成后再运行 gitmove sync", command="gitmove sync check"),
            ],
        ),
        "TEMPLATE_NOT_FOUND": GitMoveError(
            code="TEMPLATE_NOT_FOUND",
            message="vendor 模板不存在",
            steps=[step("列出模板", command="gitmove vendor template list")],
        ),
        "INCLUDE_PATH_NOT_IN_CACHE": GitMoveError(
            code="INCLUDE_PATH_NOT_IN_CACHE",
            message="include_paths 在上游 cache 中不存在",
            steps=[step("检查上游目录结构", command="ls <cache>/<include_path>")],
        ),
        "SYNC_NO_UPSTREAM": GitMoveError(
            code="SYNC_NO_UPSTREAM",
            message="当前分支未设置 upstream",
            steps=[step("设置 upstream", command="git branch -u origin/<branch>")],
        ),
        "SYNC_CONFLICT_BLOCKED": GitMoveError(
            code="SYNC_CONFLICT_BLOCKED",
            message="skip 路径存在需人工处理的远程变更",
            cause="MCP 无法交互选择保留本地/采用远程/合并策略，已中止 pull 且未修改 skip 状态。",
            steps=[
                step("查看冲突详情", command="gitmove sync check --fetch"),
                step("在 CLI 或 GUI 中逐项处理", command="gitmove sync pull"),
            ],
            doc_anchor="sync-pull",
        ),
        "GIT_COMMAND_FAILED": GitMoveError(
            code="GIT_COMMAND_FAILED",
            message="Git 命令失败",
            cause="底层 git 子进程返回错误。",
            steps=[
                step("检查 git 是否在 PATH", command="git --version"),
                step("检查网络与凭据（远程操作）"),
            ],
        ),
        "CONFIG_IMPORT_INVALID": GitMoveError(
            code="CONFIG_IMPORT_INVALID",
            message="配置导入失败",
            cause="TOML 无效或路径不合法。",
            steps=[step("重新导出对比", command="gitmove config export ./backup.toml")],
        ),
    }


CATALOG: dict[str, GitMoveError] = _catalog()


def catalog_error(code: str, **context: Any) -> GitMoveError:
    template = CATALOG.get(code)
    if template is None:
        return GitMoveError(code=code, message=context.get("message", code), cause=str(context.get("detail", "")))
    err = GitMoveError(
        code=template.code,
        message=context.get("message", template.message),
        cause=context.get("cause", template.cause),
        steps=list(template.steps),
        context=dict(context),
        doc_anchor=template.doc_anchor,
    )
    return _substitute_context(err)


def _substitute_context(err: GitMoveError) -> GitMoveError:
    mapping = {k: str(v) for k, v in err.context.items()}
    new_steps: list[RemediationStep] = []
    for item in err.steps:
        cmd = item.command
        if cmd:
            for key, val in mapping.items():
                cmd = cmd.replace(f"<{key}>", val)
        new_steps.append(
            RemediationStep(
                title=item.title,
                detail=item.detail,
                command=cmd,
                gui_action=item.gui_action,
            )
        )
    err.steps = new_steps
    if err.cause:
        for key, val in mapping.items():
            err.cause = err.cause.replace(f"<{key}>", val)
    return err


def wrap_git_error(exc: Exception, *, detail: str = "") -> GitMoveError:
    return catalog_error(
        "GIT_COMMAND_FAILED",
        message=str(exc),
        cause=detail or CATALOG["GIT_COMMAND_FAILED"].cause,
        detail=str(exc),
    )


def wrap_vendor_error(exc: Exception, *, code: str | None = None, **context: Any) -> GitMoveError:
    text = str(exc)
    if code:
        return catalog_error(code, message=text, **context)
    if "fast-forward" in text.lower() or "ff-only" in text.lower():
        return catalog_error("VENDOR_FF_BLOCKED", message=text, **context)
    if "uncommitted" in text.lower() or "dirty" in text.lower():
        return catalog_error("VENDOR_CACHE_DIRTY", message=text, **context)
    if "Cache missing" in text:
        return catalog_error("VENDOR_CACHE_MISSING", message=text, **context)
    if "not found" in text.lower():
        return catalog_error("VENDOR_NOT_FOUND", message=text, **context)
    if "exists and is not a link" in text:
        return catalog_error("VENDOR_PATH_EXISTS", message=text, **context)
    if "clone" in text.lower():
        return catalog_error("VENDOR_CLONE_FAILED", message=text, **context)
    return GitMoveError(code="VENDOR_ERROR", message=text, cause=text)


def wrap_registry_error(exc: Exception) -> GitMoveError:
    text = str(exc)
    if "Unknown project alias" in text:
        return catalog_error("REPO_CONTEXT_ALIAS_MISSING", message=text)
    if "Alias already registered" in text:
        return catalog_error("PROJECTS_ALIAS_CONFLICT", message=text)
    if "Project not found" in text:
        return catalog_error("REPO_CONTEXT_ALIAS_MISSING", message=text)
    return GitMoveError(code="REGISTRY_ERROR", message=text)


def wrap_exception(exc: BaseException) -> GitMoveError:
    if isinstance(exc, GitMoveError):
        return exc
    from gitmove import git
    from gitmove.registry import RegistryError
    from gitmove import vendor as vendor_mod

    if isinstance(exc, vendor_mod.VendorError):
        return wrap_vendor_error(exc)
    if isinstance(exc, RegistryError):
        return wrap_registry_error(exc)
    if isinstance(exc, git.GitError):
        return wrap_git_error(exc)
    if isinstance(exc, FileNotFoundError):
        if "initialized" in str(exc).lower() or "gitmove.toml" in str(exc):
            return catalog_error("REPO_NOT_INIT", message=str(exc))
        return GitMoveError(code="FILE_NOT_FOUND", message=str(exc))
    if isinstance(exc, FileExistsError):
        if "migrate" in str(exc).lower():
            return catalog_error("VENDOR_PATH_EXISTS", message=str(exc))
        return GitMoveError(code="FILE_EXISTS", message=str(exc))
    if isinstance(exc, ValueError):
        return GitMoveError(code="VALIDATION_ERROR", message=str(exc))
    return GitMoveError(code="UNKNOWN_ERROR", message=str(exc))


def remediation_for_doctor(category: str, message: str, *, path: str | None = None) -> tuple[str | None, list[RemediationStep]]:
    if "skip-worktree 未生效" in message or "未 skip" in message:
        return "SKIP_NOT_ACTIVE", CATALOG["SKIP_NOT_ACTIVE"].steps
    if category == "link":
        if "链接缺失" in message:
            return "LINK_MISSING", CATALOG["LINK_MISSING"].steps
        if "目标不一致" in message:
            return "LINK_TARGET_MISMATCH", CATALOG["LINK_TARGET_MISMATCH"].steps
    if category == "worktree":
        return "WORKTREE_NOT_REGISTERED", CATALOG["WORKTREE_NOT_REGISTERED"].steps
    if category == "vendor":
        if "cache 缺失" in message:
            return "VENDOR_CACHE_MISSING", CATALOG["VENDOR_CACHE_MISSING"].steps
        if "链接缺失" in message or "链接目标" in message:
            return "VENDOR_LINK_BROKEN", CATALOG["VENDOR_LINK_BROKEN"].steps
        if "未 skip" in message:
            return "VENDOR_TRACKED_NOT_SKIP", CATALOG["VENDOR_TRACKED_NOT_SKIP"].steps
        if "pin drift" in message:
            return "VENDOR_FF_BLOCKED", CATALOG["VENDOR_FF_BLOCKED"].steps
        if "pin not found" in message or "Pin ref not found" in message:
            return "VENDOR_PIN_NOT_FOUND", CATALOG["VENDOR_PIN_NOT_FOUND"].steps
        if "落后上游" in message:
            return "VENDOR_FF_BLOCKED", CATALOG["VENDOR_FF_BLOCKED"].steps
    if category == "config" and "尚未初始化" in message:
        return "REPO_NOT_INIT", CATALOG["REPO_NOT_INIT"].steps
    return None, []


def error_to_dict(err: GitMoveError) -> dict[str, Any]:
    return {
        "ok": False,
        "code": err.code,
        "message": err.message,
        "cause": err.cause,
        "steps": [asdict(s) for s in err.steps],
        "doc_anchor": err.doc_anchor,
        "context": err.context,
    }


def print_error(console: Console, err: GitMoveError) -> None:
    lines = [f"[bold red]✗ {err.message}[/bold red]  [{err.code}]"]
    if err.cause:
        lines.append("")
        lines.append("[bold]原因[/bold]")
        lines.append(err.cause)
    if err.steps:
        lines.append("")
        lines.append("[bold]建议操作[/bold]")
        for index, item in enumerate(err.steps, start=1):
            lines.append(f"  {index}. {item.title}")
            if item.detail:
                lines.append(f"     {item.detail}")
            if item.command:
                lines.append(f"     [cyan]{item.command}[/cyan]")
    if err.doc_anchor:
        lines.append("")
        lines.append(f"[dim]文档: docs/guides/user-manual.md#{err.doc_anchor}[/dim]")
    console.print(Panel("\n".join(lines), border_style="red", title="gitmove"))
