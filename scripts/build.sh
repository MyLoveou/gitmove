#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-all}"

cd "$ROOT"
python -m pip install -e ".[build]" -q
python scripts/build.py --target "$TARGET" --onefile
