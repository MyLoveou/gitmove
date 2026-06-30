"""Thread helper used by tests and optional callers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def call_on_main_thread(parent: Any, fn: Callable[[], T]) -> T:
    """Run fn on the Tk main loop from a worker thread and block until done."""

    box: dict[str, T | BaseException | None] = {"value": None, "error": None}
    done = threading.Event()

    def run() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — propagate to worker
            box["error"] = exc
        finally:
            done.set()

    parent.after(0, run)
    done.wait()
    if box["error"] is not None:
        raise box["error"]
    return box["value"]  # type: ignore[return-value]


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
