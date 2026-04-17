#!/usr/bin/env python3
"""Compatibility launcher for the Canvas quiz downloader package."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> int:
    """Execute package entrypoint while supporting direct script execution."""
    script = Path(__file__).resolve().parent / "canvas_quiz_downloader" / "main.py"
    if not script.exists():
        raise SystemExit("Missing canvas_quiz_downloader/main.py")

    # Preserve CLI arguments for downstream argparse.
    sys.argv = [str(script), *sys.argv[1:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
