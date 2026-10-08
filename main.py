#!/usr/bin/env python3
"""
DotaCore - Application Launcher

A modern utility to lookup match scoreboards, download, and decompress Dota 2
match replays directly from Valve CDN servers.
Supports plug-and-play frontends (CLI, Web, GUI, etc.).
"""

from __future__ import annotations

import argparse
import os
import sys

from frontend import launch_ui, list_uis


def main() -> None:
    """Launch the DotaCore application with plug-and-play frontend selection."""
    parser = argparse.ArgumentParser(description="DotaCore Replay & Scoreboard Client")
    parser.add_argument(
        "--ui",
        choices=list_uis(),
        default=os.environ.get("DOTACORE_UI", "cli"),
        help="Frontend interface to launch (default: cli)",
    )
    args, _ = parser.parse_known_args()

    api_key = os.environ.get("OPENDOTA_API_KEY")
    launch_ui(name=args.ui, api_key=api_key)


if __name__ == "__main__":
    main()
