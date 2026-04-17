#!/usr/bin/env python3
"""Backward-compatible entrypoint for canvas_quiz_downloader/main.py."""

from canvas_quiz_downloader.main import main


if __name__ == "__main__":
    raise SystemExit(main())
