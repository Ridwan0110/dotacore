"""CLI frontend implementation for DotaCore."""

from __future__ import annotations

from .app import CLIApp, run_cli
from .styles import Style, paint
from .ui import TerminalUI

__all__ = [
    "CLIApp",
    "Style",
    "TerminalUI",
    "paint",
    "run_cli",
]
