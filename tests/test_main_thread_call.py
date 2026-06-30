"""Tests for main-thread marshalling from worker threads."""

from __future__ import annotations

from unittest import mock

from gitmove.gui.async_runner import call_on_main_thread


def test_call_on_main_thread_runs_fn_via_after() -> None:
    parent = mock.Mock()

    def after(_ms: int, fn) -> None:
        fn()

    parent.after = after
    assert call_on_main_thread(parent, lambda: 42) == 42
