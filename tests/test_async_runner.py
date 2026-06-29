from __future__ import annotations

from gitmove.gui.async_runner import run_in_background


def test_run_in_background_success() -> None:
    done: list[str] = []

    def task() -> str:
        return "ok"

    def on_success(value: str) -> None:
        done.append(value)

    def on_error(exc: BaseException) -> None:
        raise exc

    thread = run_in_background(task, on_success=on_success, on_error=on_error)
    thread.join(timeout=2)
    assert done == ["ok"]


def test_run_in_background_error() -> None:
    errors: list[str] = []

    def task() -> None:
        raise RuntimeError("boom")

    def on_success(_: object) -> None:
        pass

    def on_error(exc: BaseException) -> None:
        errors.append(str(exc))

    thread = run_in_background(task, on_success=on_success, on_error=on_error)
    thread.join(timeout=2)
    assert errors == ["boom"]
