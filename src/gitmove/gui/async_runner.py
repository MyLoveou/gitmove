"""Thread helper used by tests and optional callers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def run_in_background(
    task: Callable[[], T],
    *,
    on_success: Callable[[T], None],
    on_error: Callable[[BaseException], None],
    on_finished: Callable[[], None] | None = None,
) -> threading.Thread:
    """Run task in a daemon thread. Callbacks execute on the worker thread."""

    def worker() -> None:
        try:
            result = task()
        except BaseException as exc:  # noqa: BLE001 — propagate to caller
            on_error(exc)
        else:
            on_success(result)
        finally:
            if on_finished:
                on_finished()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread
