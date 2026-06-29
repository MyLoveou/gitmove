"""PyInstaller entry point for gitmove GUI."""

from __future__ import annotations

import multiprocessing


def _main() -> None:
    from gitmove.gui.app import main

    main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _main()
