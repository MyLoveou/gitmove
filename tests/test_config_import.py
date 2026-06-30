from __future__ import annotations

from pathlib import Path

import pytest

from gitmove.config import GitMoveConfig, config_path_for_repo
from gitmove.config_io import (
    EXTERNAL_BASE_VAR,
    export_config,
    import_config,
    import_config_from_repo,
    merge_configs,
)


def test_export_and_load_roundtrip(git_repo: Path, tmp_path: Path) -> None:
    cfg = GitMoveConfig(skip_paths=["tracked.txt"], external_base="/tmp/ext")
    out = tmp_path / "export.toml"
    export_config(cfg, out)
    loaded = GitMoveConfig.load(out)
    assert loaded.skip_paths == ["tracked.txt"]
    assert loaded.external_base == "/tmp/ext"


def test_merge_configs_unions_skip_paths() -> None:
    target = GitMoveConfig(skip_paths=["a.txt"])
    incoming = GitMoveConfig(skip_paths=["b.txt", "a.txt"])
    merged = merge_configs(target, incoming)
    assert merged.skip_paths == ["a.txt", "b.txt"]


def test_merge_configs_skips_duplicate_links() -> None:
    from gitmove.config import LinkEntry

    target = GitMoveConfig(
        links=[LinkEntry("tools/a", "/old/a", "junction")],
    )
    incoming = GitMoveConfig(
        links=[LinkEntry("tools/a", "/new/a", "junction"), LinkEntry("tools/b", "/new/b", "junction")],
    )
    merged = merge_configs(target, incoming)
    paths = {link.repo_path: link.external_path for link in merged.links}
    assert paths["tools/a"] == "/old/a"
    assert paths["tools/b"] == "/new/b"


def test_import_replace_overwrites_config(git_repo: Path, tmp_path: Path) -> None:
    dest = config_path_for_repo(git_repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    GitMoveConfig(skip_paths=["old.txt"]).save(dest)

    incoming = tmp_path / "incoming.toml"
    GitMoveConfig(skip_paths=["new.txt"]).save(incoming)

    result = import_config(git_repo, incoming, merge=False)
    assert result.skip_paths == ["new.txt"]
    assert GitMoveConfig.load(dest).skip_paths == ["new.txt"]


def test_import_merge_adds_skip_paths(git_repo: Path, tmp_path: Path) -> None:
    dest = config_path_for_repo(git_repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    GitMoveConfig(skip_paths=["keep.txt"]).save(dest)

    incoming = tmp_path / "incoming.toml"
    GitMoveConfig(skip_paths=["added.txt"]).save(incoming)

    result = import_config(git_repo, incoming, merge=True)
    assert result.skip_paths == ["added.txt", "keep.txt"]


def test_import_base_override_expands_external_base_var(git_repo: Path, tmp_path: Path) -> None:
    from gitmove.config import LinkEntry

    incoming = tmp_path / "template.toml"
    GitMoveConfig(
        skip_paths=["tracked.txt"],
        links=[LinkEntry("tools/personal", f"{EXTERNAL_BASE_VAR}/tools/personal", "junction")],
    ).save(incoming)

    base = git_repo / "personal-root"
    result = import_config(git_repo, incoming, merge=False, base_override=str(base))
    assert result.external_base == str(base.resolve())
    assert result.links[0].external_path == str((base / "tools/personal").resolve())


def test_import_from_repo_reads_gitmove_toml(git_repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    source_cfg = GitMoveConfig(skip_paths=["config.local.json"])
    source_path = other / ".git" / "gitmove.toml"
    source_path.parent.mkdir(parents=True)
    source_cfg.save(source_path)

    dest = config_path_for_repo(git_repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    GitMoveConfig(skip_paths=[]).save(dest)

    result = import_config_from_repo(git_repo, other, merge=True)
    assert "config.local.json" in result.skip_paths


def test_merge_configs_preserves_link_kind_and_settings() -> None:
    from gitmove.config import LinkEntry

    target = GitMoveConfig(
        exclude_linked_paths=False,
        links=[
            LinkEntry(
                "tools/a",
                "/old/a",
                "symlink",
                kind="file",
                migrate_skipped=["x (symlink)"],
            )
        ],
    )
    incoming = GitMoveConfig(
        exclude_linked_paths=True,
        links=[LinkEntry("tools/b", "/new/b", "junction", kind="directory")],
    )
    merged = merge_configs(target, incoming)
    assert merged.exclude_linked_paths is False
    by_path = {link.repo_path: link for link in merged.links}
    assert by_path["tools/a"].kind == "file"
    assert by_path["tools/a"].migrate_skipped == ["x (symlink)"]
    assert by_path["tools/b"].kind == "directory"


def test_import_from_repo_missing_config(tmp_path: Path, git_repo: Path) -> None:
    other = tmp_path / "empty-repo"
    other.mkdir()
    with pytest.raises(FileNotFoundError, match="gitmove.toml"):
        import_config_from_repo(git_repo, other)


def test_import_rejects_escape_paths(git_repo: Path, tmp_path: Path) -> None:
    incoming = tmp_path / "bad.toml"
    GitMoveConfig(skip_paths=["../outside"]).save(incoming)
    with pytest.raises(ValueError, match="stay inside repository"):
        import_config(git_repo, incoming, merge=False)
