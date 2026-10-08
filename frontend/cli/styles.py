from __future__ import annotations

import os
import sys

# Reconfigure stdout/stderr to UTF-8 on Windows to prevent charmap / cp1252 encoding errors
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Enable VT100 / ANSI escape sequences on Windows console
if os.name == "nt":
    try:
        os.system("")
    except Exception:
        pass


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


def paint(text: str, color: str = "", bold: bool = False) -> str:
    """Colorize text with optional bold styling."""
    prefix = f"{Style.BOLD if bold else ''}{color}"
    return f"{prefix}{text}{Style.RESET}" if prefix else text
