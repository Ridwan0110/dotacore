#!/usr/bin/env python3
"""
DotaCore - Interactive CLI

A modern, interactive console utility to lookup match scoreboards,
download, and decompress Dota 2 match replays directly from Valve CDN servers.
"""

from __future__ import annotations

import os
from dotacore.app import DotaCoreApp


def main() -> None:
    """Launch the DotaCore interactive application."""
    api_key = os.environ.get("OPENDOTA_API_KEY")
    app = DotaCoreApp(api_key=api_key)
    app.start()


if __name__ == "__main__":
    main()
